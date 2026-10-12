#!/usr/bin/env python3
"""Install observational Ditoo hooks without replacing unrelated Claude settings."""
import argparse
import copy
import datetime
import json
from pathlib import Path
import re
import shlex
import sys

from ditoo_hook import EVENTS, atomic_write


def is_ditoo(hook):
    command = hook.get("command", "")
    return bool(re.search(r"(?:^|[/\s])(?:ditoo-state\.sh|ditoo_hook\.py)(?:['\"]?\s|['\"]?$)", command))


def updated_settings(original, hook_path, python=sys.executable):
    result = copy.deepcopy(original)
    hooks = result.setdefault("hooks", {})
    for event, groups in list(hooks.items()):
        kept = []
        for group in groups:
            group["hooks"] = [h for h in group.get("hooks", []) if not is_ditoo(h)]
            if group["hooks"]:
                kept.append(group)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    command = shlex.quote(str(python)) + " " + shlex.quote(str(hook_path))
    for event in EVENTS:
        # Synchronous file-only dispatch prevents async Pre/Post hooks from
        # racing one another. No permissions, decisions or stdout are produced.
        hooks.setdefault(event, []).append({"hooks": [{
            "type": "command", "command": command, "timeout": 2,
        }]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, default=Path.home()/".claude/settings.json")
    parser.add_argument("--hook-path", type=Path, default=Path(__file__).resolve().with_name("ditoo_hook.py"))
    parser.add_argument("--apply", action="store_true", help="write settings; default is a dry run")
    args = parser.parse_args()
    if not args.hook_path.is_file():
        parser.error("hook script does not exist")
    original = json.loads(args.settings.read_text()) if args.settings.exists() else {}
    result = updated_settings(original, args.hook_path.resolve())
    old_count = sum(is_ditoo(h) for groups in original.get("hooks", {}).values()
                    for g in groups for h in g.get("hooks", []))
    print(f"Replace {old_count} Ditoo handlers with {len(EVENTS)} event observers.")
    print("Preserve every non-Ditoo hook and all other settings.")
    print("Observe: " + ", ".join(EVENTS))
    if not args.apply:
        print("Dry run only. Use --apply to save; restart Claude Code afterward.")
        return
    if result == original:
        print("Already up to date.")
        return
    if args.settings.exists():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = args.settings.with_name(args.settings.name + ".before-ditoo-" + stamp)
        atomic_write(backup, args.settings.read_text())
        print(f"Backup: {backup}")
    atomic_write(args.settings, json.dumps(result, indent=2) + "\n")
    print(f"Updated {args.settings}. Restart Claude Code to load the new hooks.")


if __name__ == "__main__":
    main()
