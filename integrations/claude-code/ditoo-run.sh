#!/usr/bin/env bash
#
# Run any command with the Ditoo panel reporting on it.
#
#   ditoo-run.sh cargo test
#   ditoo-run.sh npm run build
#   ditoo-run.sh ./deploy.sh staging
#
# Shows `working` while it runs, then `success` or `error` from the exit code,
# and hands the panel back to whatever else is driving it. The command's own
# output and exit status pass straight through, so this can wrap anything --
# including inside a pipeline or a Makefile.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE="$HERE/ditoo-state.sh"
RUNDIR="${DITOO_RUNDIR:-$HOME/.claude/ditoo}"
SESSIONS="$RUNDIR/sessions"

if [ $# -eq 0 ]; then
  printf 'usage: %s <command> [args...]\n' "$(basename "${BASH_SOURCE[0]}")" >&2
  exit 2
fi

# Its own slot in the merge, keyed by pid, so several wrapped commands can run
# at once and none of them clobbers a Claude Code session's state.
SLOT="run-$$"
mkdir -p "$SESSIONS" 2>/dev/null

cleanup() {
  rm -f "$SESSIONS/$SLOT" 2>/dev/null
}
# Release the slot however we exit, including on Ctrl-C -- a wrapper that dies
# holding "working" would keep the panel busy over a command that has stopped.
trap 'cleanup; exit 130' INT TERM
trap cleanup EXIT

printf 'working\n' > "$SESSIONS/$SLOT" 2>/dev/null

"$@"
status=$?

if [ "$status" -eq 0 ]; then
  # :now -- a build that passes in four seconds still passed. The
  # earned-celebration rule is for Claude turns, not for verdicts.
  printf 'success:now\n' > "$SESSIONS/$SLOT" 2>/dev/null
else
  printf 'error:now\n' > "$SESSIONS/$SLOT" 2>/dev/null
fi

# Hold the verdict long enough to be seen. The daemon fades success and error
# back to idle on its own, but only while something is still asking for them.
sleep "${DITOO_VERDICT_SECONDS:-6}"

exit "$status"
