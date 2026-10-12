#!/usr/bin/env python3
"""Observe Claude Code events without making permission or execution decisions.

No Bluetooth, network, transcript reads, prompt logging, or subprocesses here.
One bounded lock serializes events; atomic snapshots feed the existing daemon.
Tool IDs keep parallel completions from clearing another tool's activity.
"""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time

EVENTS = (
    "SessionStart", "SessionEnd", "Setup", "UserPromptSubmit", "UserPromptExpansion",
    "PreToolUse", "PostToolUse", "PostToolUseFailure", "PostToolBatch",
    "PermissionRequest", "PermissionDenied", "Notification", "MessageDisplay",
    "SubagentStart", "SubagentStop", "TaskCreated", "TaskCompleted", "TeammateIdle",
    "Stop", "StopFailure", "InstructionsLoaded", "ConfigChange", "CwdChanged",
    "DirectoryAdded", "PreCompact", "PostCompact", "PreModelSwitch", "PostModelSwitch",
    "Elicitation", "ElicitationResult", "WorktreeRemove",
)
# WorktreeCreate is deliberately excluded: registering it replaces git worktree
# creation, and an observer must never take over that operation. FileChanged
# requires an explicit watch list; do not install a broad filesystem watcher.

ACTIVE = {"thinking", "working", "compacting", "reading", "searching", "writing",
          "terminal", "testing", "building", "installing", "reviewing", "planning",
          "delegating", "connecting", "responding"}
ALERTS = {"alerting", "alert-permission", "alert-question", "alert-plan"}


def safe_id(value):
    if not isinstance(value, str) or not value:
        return "manual"
    if re.fullmatch(r"[a-zA-Z0-9_-]{1,120}", value):
        return value
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def command_state(command):
    """Classify executable tokens, never descriptions or arbitrary substrings."""
    try:
        tokens = shlex.split(command)
    except (ValueError, TypeError):
        return "terminal"
    # Match each simple command. Unknown wrappers remain honestly 'terminal'.
    segments, segment = [], []
    for token in tokens + [";"]:
        if token in (";", "&&", "||", "|"):
            if segment:
                segments.append(segment)
            segment = []
        else:
            segment.append(token)
    states = []
    for words in segments:
        while words and re.match(r"^[A-Za-z_][A-Za-z_0-9]*=", words[0]):
            words = words[1:]
        if not words:
            continue
        exe = Path(words[0]).name
        args = words[1:]
        action = next((a for a in args if not a.startswith("-")), "")
        if exe in {"pytest", "jest", "vitest", "mocha", "bats"}:
            states.append("testing")
        elif exe in {"python", "python3"} and args[:2] in (["-m", "pytest"], ["-m", "unittest"]):
            states.append("testing")
        elif exe in {"npm", "pnpm", "yarn", "bun", "cargo", "go", "uv", "pip", "pip3", "brew", "make", "cmake", "gradle", "mvn", "dotnet"}:
            if action in {"run", "exec", "x"}:
                action = next((a for a in args[1:] if not a.startswith("-")), "")
            if action in {"test", "check", "lint", "typecheck", "pytest", "vitest", "jest"} or action.startswith("test:"):
                states.append("testing")
            elif action in {"build", "compile", "package", "publish"} or "--build" in args:
                states.append("building")
            elif action in {"install", "add", "ci", "sync", "update", "upgrade"}:
                states.append("installing")
            else:
                states.append("terminal")
        elif exe == "git" and action in {"diff", "show", "log", "status", "blame"}:
            states.append("reviewing")
        elif exe in {"rg", "grep", "find", "fd"}:
            states.append("searching")
        elif exe in {"cat", "head", "tail", "less", "wc"}:
            states.append("reading")
        elif exe in {"curl", "wget", "ssh", "scp"}:
            states.append("connecting")
        elif exe != "cd":
            states.append("terminal")
    # A compound command has one display: choose its substantive final stage.
    return states[-1] if states else "terminal"


def tool_state(payload):
    name = payload.get("tool_name", "")
    data = payload.get("tool_input") or {}
    if not isinstance(data, dict):
        data = {}
    if name == "AskUserQuestion":
        return "alert-question"
    if name == "ExitPlanMode":
        return "alert-plan"
    if name in {"EnterPlanMode", "TodoWrite", "TaskCreate", "TaskUpdate"}:
        return "planning"
    if name in {"Read", "NotebookRead", "TaskGet", "TaskList", "TaskOutput"}:
        return "reading"
    if name in {"Grep", "Glob", "WebSearch", "ToolSearch"}:
        return "searching"
    if name in {"Edit", "Write", "NotebookEdit", "MultiEdit"}:
        return "writing"
    if name in {"Agent", "Task"}:
        return "delegating"
    if name in {"Bash", "PowerShell"}:
        return command_state(data.get("command", ""))
    if name in {"WebFetch"} or str(name).startswith("mcp__"):
        return "connecting"
    if name == "Skill":
        return "reading"
    return "working"


def score(state):
    if state in ALERTS:
        return 100
    if state == "error":
        return 90
    if state == "compacting":
        return 70
    if state in ACTIVE:
        return 50 if state in {"thinking", "responding"} else 60
    return {"success": 40, "done": 40, "cancelled": 35, "starting": 30,
            "configuring": 30, "taskdone": 30, "chilling": 10}.get(state, 5)


def actor_state(actor):
    choices = [(v.get("blocked", v["state"]), v["at"]) for v in actor.get("tools", {}).values()]
    if actor.get("alert"):
        choices.append((actor["alert"], actor.get("at", 0)))
    choices.append((actor.get("state", "chilling"), actor.get("at", 0)))
    return max(choices, key=lambda x: (score(x[0]), x[1]))


def background_snapshot(model, payload, now):
    """Stop snapshots describe in-flight work, not completed task history.

    Never retain descriptions, commands, transcripts or scheduled prompts.
    An absent/malformed array means unknown, not 'everything finished'.
    """
    if payload.get("hook_event_name") not in {"Stop", "SubagentStop"}:
        return
    tasks = payload.get("background_tasks")
    if not isinstance(tasks, list) or any(
        not isinstance(task, dict) or not isinstance(task.get("id"), str)
        or not task["id"] or not isinstance(task.get("status"), str) for task in tasks
    ):
        return
    snapshot = {}
    for task in tasks:
        if task["status"] in {"completed", "failed", "killed", "cancelled"}:
            continue
        key = safe_id(task["id"])
        if payload.get("hook_event_name") == "SubagentStop" and key == safe_id(payload.get("agent_id")):
            continue
        snapshot[key] = {"state": "working", "at": now}
    model["background_tasks"] = snapshot
    if snapshot:
        model["team_turn"] = True


def session_state(model):
    """A session summary, never a most-recent-agent/tool animation contest."""
    actors = model.get("actors", {})
    states = {who: actor_state(actor)[0] for who, actor in actors.items()}
    alerts = [state for state in states.values() if state in ALERTS]
    if alerts:
        # Keep the current reason while it remains true, so another agent's
        # question cannot reset the original permission alert's escalation.
        return model.get("display") if model.get("display") in alerts else alerts[0]
    main = actors.get("main", {})
    if main.get("fatal_error"):
        return "error"
    live_agents = any(who != "main" and state not in {"success", "done", "cancelled", "chilling"}
                      for who, state in states.items())
    if live_agents or model.get("background_tasks"):
        model["team_turn"] = True
        return "delegating"
    # Keep the same team scene while the parent integrates the results. Tool
    # errors remain in the rail instead of hijacking a productive team's face.
    if model.get("team_turn"):
        if states.get("main") in {"success", "done"}:
            unresolved = model.get("finished_errors") or any(a.get("rail_error") for a in actors.values())
            return "error" if unresolved else "success"
        if states.get("main") in {"cancelled", "chilling"}:
            return states["main"]
        return "delegating"
    choices = [actor_state(a) for a in actors.values()]
    return max(choices, key=lambda x: (score(x[0]), x[1]))[0] if choices else "thinking"


def transition(model, payload, now):
    """Pure event reducer. Returns whether this event has observable meaning."""
    event = payload.get("hook_event_name")
    if event not in EVENTS:
        return False
    actors = model.setdefault("actors", {})
    who = safe_id(payload.get("agent_id")) if payload.get("agent_id") else "main"
    background_snapshot(model, payload, now)
    if event == "MessageDisplay" and who not in actors:
        return False
    if event == "SubagentStop" and who not in actors:
        # Claude's internal helper agents can stop without an observed launch.
        # Do not invent a completed worker for those events.
        return "background_tasks" in payload
    # SubagentStart/Stop's agent_id names the subject, not the emitter.
    actor = actors.setdefault(who, {"state": "thinking", "tools": {}, "at": now})
    tools = actor.setdefault("tools", {})
    tool_id = safe_id(payload.get("tool_use_id") or payload.get("tool_name"))
    if not payload.get("tool_use_id") and payload.get("tool_name"):
        matches = [(key, item["at"]) for key, item in tools.items()
                   if item.get("name") == payload["tool_name"]]
        if matches:
            tool_id = max(matches, key=lambda pair: pair[1])[0]
    state = None
    if event == "SessionStart":
        state = "starting"
    elif event == "UserPromptSubmit":
        # A new parent turn must not erase agents still running in background.
        actor.update(tools={}, alert=None, rail_error=False, fatal_error=False)
        model["finished_agents"] = []
        model["finished_errors"] = []
        model["team_turn"] = any(k != "main" for k in actors) or bool(model.get("background_tasks"))
        state = "thinking"
    elif event == "PreToolUse":
        actor["fatal_error"] = False
        if actor.get("alert_source", "notification") == "notification":
            actor["alert"] = None
        actor["state"] = "thinking"
        tools[tool_id] = {"state": tool_state(payload), "at": now,
                          "name": str(payload.get("tool_name", ""))[:160]}
    elif event in {"PostToolUse", "PostToolUseFailure", "PermissionDenied"}:
        tools.pop(tool_id, None)
        if actor.get("alert_source", "notification") in {"notification", "tool:" + str(payload.get("tool_name", ""))}:
            actor["alert"] = None
        if event == "PostToolUseFailure":
            state = "cancelled" if payload.get("is_interrupt") else "error"
            actor["rail_error"] = not payload.get("is_interrupt", False)
        elif event == "PermissionDenied":
            state = "cancelled"
        else:
            # Errors end when the next action succeeds; successful individual
            # tools are NOT a successful whole turn.
            state = "thinking"
            actor["rail_error"] = False
            response = payload.get("tool_response")
            if payload.get("tool_name") in {"Agent", "Task"} and isinstance(response, dict):
                agent_id = response.get("agentId")
                if response.get("status") == "async_launched" and isinstance(agent_id, str) and agent_id:
                    agent_id = safe_id(agent_id)
                    if agent_id not in model.get("finished_agents", []):
                        actors.setdefault(agent_id, {"state": "delegating", "tools": {}, "at": now})
                        model["team_turn"] = True
    elif event == "PermissionRequest":
        blocked = "alert-plan" if payload.get("tool_name") == "ExitPlanMode" else "alert-permission"
        if tool_id in tools:
            tools[tool_id]["blocked"] = blocked
        else:
            actor["alert"] = blocked
            actor["alert_source"] = "tool:" + str(payload.get("tool_name", ""))
    elif event == "Elicitation":
        actor["alert"] = "alert-question"
        actor["alert_source"] = "elicitation"
    elif event == "ElicitationResult":
        actor["alert"] = None
        state = "connecting" if payload.get("action") == "accept" else "cancelled"
    elif event == "Notification":
        kind = payload.get("notification_type", "")
        if kind == "permission_prompt":
            actor["alert"] = "alert-permission"
            actor["alert_source"] = "notification"
        elif kind in {"elicitation_dialog", "elicitation_url_dialog", "agent_needs_input"}:
            actor["alert"] = "alert-question"
            actor["alert_source"] = "elicitation" if kind.startswith("elicitation_") else "notification"
        elif kind == "idle_prompt":
            actor["alert"] = "alerting"
            actor["alert_source"] = "notification"
        elif kind in {"elicitation_complete", "elicitation_response"}:
            actor["alert"] = None
            state = "thinking"
        else:
            return False  # auth/task-complete notifications are not blockers
    elif event == "SubagentStart":
        model["team_turn"] = True
        for field in ("finished_agents", "finished_errors"):
            model[field] = [key for key in model.get(field, []) if key != who]
        actor.update(tools={}, alert=None, rail_error=False, fatal_error=False)
        state = "delegating"
    elif event == "SubagentStop":
        if actor.get("rail_error") or actor_state(actor)[0] == "error":
            errors = model.setdefault("finished_errors", [])
            if who not in errors:
                errors.append(who)
        actors.pop(who, None)
        model.get("background_tasks", {}).pop(who, None)
        finished = model.setdefault("finished_agents", [])
        if who not in finished:
            finished.append(who)
        return True
    elif event == "PreCompact":
        state = "compacting"
    elif event in {"PostCompact", "PostToolBatch", "PostModelSwitch"}:
        if actor.get("state") != "error":
            state = "thinking"
    elif event == "MessageDisplay":
        if actor.get("state") not in {"success", "done", "chilling", "error"}:
            state = "responding"
        else:
            return False  # late async display batches must not undo Stop
    elif event == "Stop":
        actor.update(tools={}, alert=None)
        state = "success"
    elif event == "StopFailure":
        actor.update(tools={}, alert=None)
        actor["rail_error"] = True
        actor["fatal_error"] = True
        state = "error"
    elif event == "TeammateIdle":
        return False  # another teammate's idle event must not clear our work
    elif event in {"TaskCreated", "UserPromptExpansion"}:
        state = "planning"
    elif event == "TaskCompleted":
        state = "taskdone"
    elif event == "InstructionsLoaded":
        if tools or actor.get("alert"):
            return False
        state = "configuring"  # brief context loading, not an indefinitely running tool
    elif event in {"Setup", "ConfigChange", "CwdChanged", "DirectoryAdded", "PreModelSwitch", "WorktreeRemove"}:
        if tools or actor.get("alert"):
            return False
        state = "configuring"
    elif event == "SessionEnd":
        return True
    if state:
        actor["state"] = state
    actor["at"] = now
    return True


def publish_agent_strip(rundir, models, now):
    """Stable seven-slot roster, plus one overflow light; no task text exported.

    Slot ownership survives joins/completions and is released at the next turn,
    session end, or the same 15-minute stale cutoff used by the observer.
    """
    current = {}
    for sid, model in models:
        expires = int(model.get("updated", 0) + 900)
        if expires <= now:
            continue
        for who, actor in model.get("actors", {}).items():
            state = actor_state(actor)[0]
            status = ("waiting" if state in ALERTS else
                      "error" if actor.get("rail_error") or state == "error" else
                      "done" if state in {"success", "done", "chilling", "cancelled"} else "running")
            current[sid + "/" + who] = (status, expires)
        for who in model.get("finished_agents", []):
            current[sid + "/" + who] = (
                "error" if who in model.get("finished_errors", []) else "done", expires)
        for who in model.get("background_tasks", {}):
            # Same-ID agent snapshots and lifecycle events describe one worker.
            current.setdefault(sid + "/" + who, ("running", expires))
    registry = rundir / "agent-slots.json"
    try:
        previous = json.loads(registry.read_text())
        if not isinstance(previous, dict):
            previous = {}
    except (OSError, ValueError):
        previous = {}
    slots = {}
    for key, slot in previous.items():
        if key in current and type(slot) is int and 0 <= slot < 7 and slot not in slots.values():
            slots[key] = slot
    for key in current:
        if key not in slots:
            free = next((i for i in range(7) if i not in slots.values()), None)
            if free is None and current[key][0] != "done":
                # A long session may finish hundreds of agents. Preserve live
                # positions, but let new workers reuse finished workers' seats.
                retired = next((old for old in slots if current[old][0] == "done"
                                and not old.endswith("/main")), None)
                if retired is not None:
                    free = slots.pop(retired)
            if free is not None:
                slots[key] = free
    lines = ["v1"]
    for key, (status, expires) in current.items():
        # Multiple records in slot seven are deliberately aggregated by the
        # renderer, retaining the most urgent unexpired status.
        lines.append(f"{slots.get(key, 7)} {status} {expires}")
    atomic_write(registry, json.dumps(slots, separators=(",", ":")))
    atomic_write(rundir / "agent-strip", "\n".join(lines) + "\n")


def handle(payload, rundir):
    if not isinstance(payload, dict) or payload.get("hook_event_name") not in EVENTS:
        return
    sid = safe_id(payload.get("session_id"))
    event = payload["hook_event_name"]
    rundir.mkdir(parents=True, exist_ok=True)
    metadata = rundir / "hook-state"
    metadata.mkdir(exist_ok=True)
    with (metadata / "events.lock").open("a") as lock:
        deadline = time.monotonic() + 0.5
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    return
                time.sleep(0.005)
        file = metadata / (sid + ".json")
        try:
            model = json.loads(file.read_text())
            if not isinstance(model, dict):
                model = {}
        except (OSError, ValueError):
            model = {}
        now = time.time()
        if now - model.get("updated", now) > 900:
            model = {}
        if event == "SessionEnd":
            for path in (file, rundir / "sessions" / sid,
                         rundir / ("fanout." + sid + ".start"), rundir / ("fanout." + sid + ".done")):
                path.unlink(missing_ok=True)
            # Clear the fallback too; the daemon still prioritizes other slots.
            atomic_write(rundir / "desired", "chilling\n")
        else:
            if not transition(model, payload, now):
                return
            model["updated"] = now
            state = session_state(model)
            model["display"] = state
            # Store only identifiers/states: never command, prompt, output or delta.
            atomic_write(file, json.dumps(model, separators=(",", ":")))
            atomic_write(rundir / "sessions" / sid, state + "\n")
            atomic_write(rundir / "desired", state + "\n")
            if event == "UserPromptSubmit":
                (rundir / "last-prompt").touch()
        started = finished = 0
        models = []
        for saved in metadata.glob("*.json"):
            try:
                data = json.loads(saved.read_text())
                if now - data.get("updated", 0) > 900:
                    continue
                models.append((saved.stem, data))
                done = len(data.get("finished_agents", []))
                running = sum(k != "main" for k in data.get("actors", {}))
                started += running + done
                finished += done
            except (ValueError, OSError, TypeError):
                continue
        if started:
            atomic_write(rundir / "fanout", f"{finished}/{started}\n")
        else:
            (rundir / "fanout").unlink(missing_ok=True)
        publish_agent_strip(rundir, models, now)


def refresh_existing(rundir):
    """Re-summarize fresh observations after upgrade without inventing events.

    Preserve timestamps: refreshing presentation is not evidence of new work.
    Uses the same event lock, so a real hook cannot be overwritten mid-update.
    """
    metadata = rundir / "hook-state"
    if not metadata.is_dir():
        return 0
    with (metadata / "events.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        models = []
        now = time.time()
        for file in metadata.glob("*.json"):
            try:
                model = json.loads(file.read_text())
                session = rundir / "sessions" / file.stem
                if now - model.get("updated", 0) > 900 or not session.is_file():
                    continue
                stamp = session.stat()
                model["display"] = session_state(model)
                atomic_write(file, json.dumps(model, separators=(",", ":")))
                atomic_write(session, model["display"] + "\n")
                os.utime(session, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                models.append((file.stem, model))
            except (ValueError, OSError, TypeError):
                continue
        publish_agent_strip(rundir, models, now)
        return len(models)


def main():
    try:
        rundir = Path(os.environ.get("DITOO_RUNDIR", str(Path.home() / ".claude/ditoo")))
        if sys.argv[1:] == ["--refresh"]:
            refresh_existing(rundir)
            return 0
        raw = sys.stdin.buffer.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            return 0
        payload = json.loads(raw)
        handle(payload, rundir)
    except Exception:
        # An observational hook must never block, approve, or alter Claude's work.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
