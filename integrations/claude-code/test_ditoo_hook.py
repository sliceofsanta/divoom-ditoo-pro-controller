"""Offline regression tests: no real hook settings, daemon or Bluetooth writes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from ditoo_hook import EVENTS, actor_state, command_state, handle, safe_id, tool_state, publish_agent_strip, refresh_existing

spec = importlib.util.spec_from_file_location("installer", Path(__file__).with_name("install-hooks.py"))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def event(self, event, **fields):
        handle(dict(session_id="test", hook_event_name=event, **fields), self.root)
        p = self.root/"sessions/test"
        return p.read_text().strip() if p.exists() else None

    def test_tool_families(self):
        cases = {"Read":"reading", "Grep":"searching", "Glob":"searching",
                 "Write":"writing", "Edit":"writing", "WebSearch":"searching",
                 "Agent":"delegating", "EnterPlanMode":"planning", "ExitPlanMode":"alert-plan",
                 "AskUserQuestion":"alert-question", "mcp__server__tool":"connecting", "new_tool":"working"}
        for tool, state in cases.items():
            self.assertEqual(tool_state({"tool_name":tool}), state)

    def test_lifecycle_coverage(self):
        cases = [("SessionStart","starting"),("UserPromptSubmit","thinking"),
                 ("PreCompact","compacting"),("PostCompact","thinking"),
                 ("UserPromptExpansion","planning"),("TaskCreated","planning"),
                 ("TaskCompleted","taskdone"),("InstructionsLoaded","configuring"),
                 ("ConfigChange","configuring"),("CwdChanged","configuring"),
                 ("DirectoryAdded","configuring"),("Setup","configuring"),
                 ("PreModelSwitch","configuring"),("PostModelSwitch","thinking"),
                 ("PostToolBatch","thinking"),("StopFailure","error")]
        for event,state in cases:
            self.assertEqual(self.event(event),state,event)
        self.event("UserPromptSubmit")
        self.assertEqual(self.event("Elicitation"),"alert-question")
        self.assertEqual(self.event("ElicitationResult",action="accept"),"connecting")

    def test_late_display_after_end_does_not_recreate_session(self):
        self.event("SessionStart")
        self.event("SessionEnd")
        self.assertIsNone(self.event("MessageDisplay",delta="late batch"))

    def test_commands_not_descriptions(self):
        cases = {"npm test":"testing", "cd app && pnpm run test:unit":"testing",
                 "cargo build --release":"building", "uv sync":"installing",
                 "git diff --stat":"reviewing", "python3 -m pytest -q":"testing",
                 "echo 'npm test'":"terminal", "curl https://example.com":"connecting",
                 "echo 'rm -rf /'":"terminal", "npm install":"installing",
                 "FOO=bar pytest":"testing", "bad 'quote":"terminal"}
        for cmd, state in cases.items():
            self.assertEqual(command_state(cmd), state, cmd)

    def test_parallel_completion_leaves_other_tool_active(self):
        self.event("PreToolUse",tool_name="Read",tool_use_id="a")
        self.event("PreToolUse",tool_name="Write",tool_use_id="b")
        self.assertEqual(self.event("PostToolUse",tool_name="Write",tool_use_id="b"),"reading")
        self.assertEqual(self.event("PostToolUse",tool_name="Read",tool_use_id="a"),"thinking")

    def test_permission_wait_survives_unrelated_tool_completion(self):
        self.event("PreToolUse",tool_name="Write",tool_use_id="a")
        self.event("PermissionRequest",tool_name="Write",tool_use_id="a")
        self.event("PreToolUse",tool_name="Read",tool_use_id="b")
        self.assertEqual(self.event("PostToolUse",tool_name="Read",tool_use_id="b"),"alert-permission")
        self.assertEqual(self.event("PostToolUse",tool_name="Write",tool_use_id="a"),"thinking")

    def test_permission_without_id_matches_its_tool_name(self):
        self.event("PreToolUse",tool_name="Write",tool_use_id="a")
        self.event("PermissionRequest",tool_name="Write")
        self.event("PreToolUse",tool_name="Read",tool_use_id="b")
        self.assertEqual(self.event("PostToolUse",tool_name="Read",tool_use_id="b"),"alert-permission")
        self.assertEqual(self.event("PostToolUse",tool_name="Write",tool_use_id="a"),"thinking")

    def test_agents_do_not_clear_parent_alert(self):
        self.event("PermissionRequest",tool_name="Write")
        self.event("SubagentStart",agent_id="agent1")
        self.event("PreToolUse",agent_id="agent1",tool_name="Read",tool_use_id="a")
        self.assertEqual(self.event("SubagentStop",agent_id="agent1"),"alert-permission")
        self.assertEqual((self.root/"fanout").read_text(),"1/1\n")

    def test_elicitation_wait_survives_unrelated_tool(self):
        self.event("Elicitation")
        self.event("PreToolUse",tool_name="Read",tool_use_id="b")
        self.assertEqual(self.event("PostToolUse",tool_name="Read",tool_use_id="b"),"alert-question")
        self.assertEqual(self.event("ElicitationResult",action="accept"),"connecting")

    def test_stop_then_late_display_is_not_busy_again(self):
        self.event("UserPromptSubmit")
        self.assertEqual(self.event("MessageDisplay",delta="secret reply"),"responding")
        self.event("Stop")
        self.assertEqual(self.event("MessageDisplay",delta="late text"),"success")

    def test_end_releases_slot_and_fallback(self):
        self.event("PreToolUse",tool_name="Write")
        self.assertIsNone(self.event("SessionEnd"))
        self.assertEqual((self.root/"desired").read_text(),"chilling\n")

    def test_failure_recovery_and_interrupt(self):
        self.assertEqual(self.event("PostToolUseFailure",tool_name="Bash"),"error")
        self.assertEqual(self.event("PreToolUse",tool_name="Read"),"reading")
        self.assertEqual(self.event("PostToolUseFailure",tool_name="Read",is_interrupt=True),"cancelled")

    def test_passive_notifications_do_not_request_input(self):
        self.event("PreToolUse",tool_name="Read")
        self.assertEqual(self.event("Notification",notification_type="auth_success"),"reading")

    def test_metadata_does_not_clobber_action(self):
        self.event("PreToolUse",tool_name="Write")
        self.assertEqual(self.event("InstructionsLoaded"),"writing")
        self.assertEqual(self.event("ConfigChange"),"writing")

    def test_no_private_content_or_path_traversal(self):
        self.event("PreToolUse",tool_name="Bash",tool_input={"command":"echo TOPSECRET"})
        self.assertNotIn("TOPSECRET",(self.root/"hook-state/test.json").read_text())
        self.assertNotIn("/",safe_id("../../outside"))

    def test_concurrent_agents_are_counted(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda n:self.event("SubagentStart",agent_id=f"agent{n}"),range(8)))
        self.assertEqual((self.root/"fanout").read_text(),"0/8\n")

    def test_agent_slots_stay_put_through_joins_and_completions(self):
        self.event("UserPromptSubmit")
        self.event("SubagentStart", agent_id="a")
        slots = json.loads((self.root/"agent-slots.json").read_text())
        self.event("SubagentStart", agent_id="b")
        self.event("SubagentStop", agent_id="a")
        after = json.loads((self.root/"agent-slots.json").read_text())
        self.assertEqual(slots["test/a"], after["test/a"])
        self.assertIn(f'{after["test/a"]} done ', (self.root/"agent-strip").read_text())
        self.event("UserPromptSubmit")
        next_turn = json.loads((self.root/"agent-slots.json").read_text())
        self.assertNotIn("test/a", next_turn)
        self.assertEqual(after["test/b"], next_turn["test/b"])
        self.event("SessionEnd")
        self.assertEqual((self.root/"agent-strip").read_text(), "v1\n")

    def test_strip_failure_is_latched_until_success_and_survives_stop(self):
        self.event("SubagentStart", agent_id="a")
        self.event("PostToolUseFailure", agent_id="a", tool_name="Bash")
        self.event("PreToolUse", agent_id="a", tool_name="Read")
        self.assertIn(" error ", (self.root/"agent-strip").read_text())
        self.event("PostToolUse", agent_id="a", tool_name="Read")
        self.assertNotIn(" error ", (self.root/"agent-strip").read_text())
        self.event("PostToolUseFailure", agent_id="a", tool_name="Bash")
        self.event("SubagentStop", agent_id="a")
        self.assertIn(" error ", (self.root/"agent-strip").read_text())

    def test_strip_overflow_and_expiry(self):
        for i in range(10):
            self.event("SubagentStart", agent_id=f"a{i}")
        slots = json.loads((self.root/"agent-slots.json").read_text())
        self.assertEqual(len(set(slots.values())), 7)
        self.assertEqual(sum(line.startswith("7 ") for line in (self.root/"agent-strip").read_text().splitlines()), 3)
        publish_agent_strip(self.root, [("old", {"updated":0,"actors":{"main":{"state":"thinking"}}})], 901)
        self.assertEqual((self.root/"agent-strip").read_text(), "v1\n")

    def test_parallel_session_is_a_stable_team_not_the_latest_tool(self):
        self.event("UserPromptSubmit")
        self.assertEqual(self.event("SubagentStart", agent_id="a"), "delegating")
        self.event("SubagentStart", agent_id="b")
        observed = []
        for i in range(30):
            who = "a" if i % 2 else "b"
            tool = ("Read", "Write", "Bash")[i % 3]
            observed.append(self.event("PreToolUse", agent_id=who, tool_name=tool, tool_use_id=str(i)))
            observed.append(self.event("PostToolUse", agent_id=who, tool_name=tool, tool_use_id=str(i)))
        self.assertEqual(set(observed), {"delegating"})
        self.assertEqual(self.event("PostToolUseFailure", agent_id="a", tool_name="Bash"), "delegating")
        self.assertIn(" error ", (self.root/"agent-strip").read_text())
        self.assertEqual(self.event("PostToolUse", agent_id="a", tool_name="Read"), "delegating")
        self.assertEqual(self.event("SubagentStop", agent_id="a"), "delegating")
        self.assertEqual(self.event("SubagentStop", agent_id="b"), "delegating")
        self.assertEqual(self.event("PreToolUse", tool_name="Write"), "delegating")
        self.assertEqual(self.event("Stop", background_tasks=[]), "success")

    def test_parent_stop_is_not_completion_while_background_agent_runs(self):
        self.event("UserPromptSubmit")
        self.event("SubagentStart", agent_id="a")
        self.assertEqual(self.event("Stop"), "delegating")
        self.assertEqual(self.event("SubagentStop", agent_id="a"), "success")

    def test_snapshot_covers_background_shell_and_deduplicates_agent(self):
        self.event("UserPromptSubmit")
        self.event("SubagentStart", agent_id="a")
        tasks = [{"id":"a", "type":"subagent", "status":"running", "description":"PRIVATE"},
                 {"id":"shell1", "type":"shell", "status":"running", "command":"PRIVATE"}]
        self.assertEqual(self.event("Stop", background_tasks=tasks), "delegating")
        strip = (self.root/"agent-strip").read_text()
        self.assertEqual(len(strip.splitlines()), 4)  # version + main + agent + shell
        self.assertNotIn("PRIVATE", (self.root/"hook-state/test.json").read_text())
        self.assertEqual(self.event("SubagentStop", agent_id="a", background_tasks=tasks[1:]), "delegating")
        self.assertEqual(self.event("Stop", background_tasks=[]), "success")

    def test_missing_or_malformed_snapshot_does_not_invent_completion(self):
        self.event("Stop", background_tasks=[{"id":"shell1", "status":"running"}])
        self.assertEqual(self.event("Stop"), "delegating")
        self.assertEqual(self.event("Stop", background_tasks=[{}]), "delegating")
        self.assertEqual(self.event("Stop", background_tasks=None), "delegating")
        self.assertEqual(self.event("Stop", background_tasks=[]), "success")

    def test_attention_stays_stable_and_fatal_parent_error_interrupts_team(self):
        self.event("SubagentStart", agent_id="a")
        self.event("SubagentStart", agent_id="b")
        self.assertEqual(self.event("PermissionRequest", agent_id="a", tool_name="Write"), "alert-permission")
        self.assertEqual(self.event("Elicitation", agent_id="b"), "alert-permission")
        self.assertEqual(self.event("PostToolUse", agent_id="a", tool_name="Write"), "alert-question")
        self.assertEqual(self.event("ElicitationResult", agent_id="b", action="accept"), "delegating")
        self.assertEqual(self.event("StopFailure"), "error")
        self.assertEqual(self.event("PreToolUse", agent_id="a", tool_name="Read"), "error")
        self.assertEqual(self.event("PreToolUse", tool_name="Read"), "delegating")

    def test_resumed_agent_and_late_messages_do_not_double_count(self):
        self.event("SubagentStart", agent_id="a")
        self.event("SubagentStop", agent_id="a")
        self.event("MessageDisplay", agent_id="a")
        self.assertEqual((self.root/"fanout").read_text(), "1/1\n")
        self.event("SubagentStart", agent_id="a")
        self.assertEqual((self.root/"fanout").read_text(), "0/1\n")

    def test_async_agent_launch_response_is_not_a_finished_tool_only(self):
        self.event("UserPromptSubmit")
        self.assertEqual(self.event("PostToolUse", tool_name="Agent", tool_response={
            "status":"async_launched", "agentId":"a", "prompt":"PRIVATE"}), "delegating")
        self.assertEqual(self.event("Stop"), "delegating")
        self.assertEqual(self.event("SubagentStop", agent_id="a"), "success")

    def test_new_workers_can_reuse_finished_slots_without_moving_live_workers(self):
        self.event("UserPromptSubmit")
        for i in range(6):
            self.event("SubagentStart", agent_id=f"a{i}")
        before = json.loads((self.root/"agent-slots.json").read_text())
        self.event("SubagentStop", agent_id="a0")
        self.event("SubagentStart", agent_id="new")
        after = json.loads((self.root/"agent-slots.json").read_text())
        self.assertEqual(after["test/new"], before["test/a0"])
        for i in range(1,6):
            self.assertEqual(before[f"test/a{i}"], after[f"test/a{i}"])

    def test_failed_finished_worker_prevents_a_false_team_success(self):
        self.event("UserPromptSubmit")
        self.event("SubagentStart", agent_id="a")
        self.event("PostToolUseFailure", agent_id="a", tool_name="Bash")
        self.event("SubagentStop", agent_id="a")
        self.assertEqual(self.event("Stop", background_tasks=[]), "error")
        self.assertEqual(self.event("UserPromptSubmit"), "thinking")

    def test_internal_unobserved_stop_does_not_create_phantom_worker(self):
        self.event("UserPromptSubmit")
        self.assertEqual(self.event("SubagentStop", agent_id="internal"), "thinking")
        self.assertFalse((self.root/"fanout").exists())

    def test_upgrade_refresh_preserves_evidence_and_session_age(self):
        self.event("UserPromptSubmit")
        self.event("SubagentStart", agent_id="a")
        path = self.root/"hook-state/test.json"
        model = json.loads(path.read_text())
        model.pop("team_turn")
        model["display"] = "reading"
        path.write_text(json.dumps(model))
        session = self.root/"sessions/test"
        session.write_text("reading\n")
        before = session.stat().st_mtime_ns
        self.assertEqual(refresh_existing(self.root), 1)
        self.assertEqual(session.read_text(), "delegating\n")
        self.assertEqual(session.stat().st_mtime_ns, before)
        after = json.loads(path.read_text())
        self.assertEqual(after["updated"], model["updated"])
        self.assertEqual(after["actors"], model["actors"])

    def test_installer_preserves_unrelated_hooks_and_is_idempotent(self):
        original={"permissions":{"defaultMode":"default"},"hooks":{
            "PreToolUse":[{"matcher":"Bash","hooks":[
                {"type":"command","command":"/repo/ditoo-state.sh working","async":True},
                {"type":"command","command":"/other/security-check.sh"}]}]}}
        updated=installer.updated_settings(original,Path('/installed/ditoo_hook.py'),'/usr/bin/python3')
        self.assertEqual(updated["permissions"],original["permissions"])
        self.assertEqual(updated["hooks"]["PreToolUse"][0]["hooks"],[{"type":"command","command":"/other/security-check.sh"}])
        self.assertEqual(installer.updated_settings(updated,Path('/installed/ditoo_hook.py'),'/usr/bin/python3'),updated)
        self.assertNotIn("WorktreeCreate",updated["hooks"])
        self.assertEqual(len(EVENTS),len(set(EVENTS)))


if __name__ == "__main__":
    unittest.main()
