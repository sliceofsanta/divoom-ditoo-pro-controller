#!/usr/bin/env bash
#
# Put anything that can be checked from a shell onto the panel.
#
#   ditoo-watch.sh [options] -- <command>...
#
# The status faces only ever knew about Claude Code, which left the panel dark
# for most of what you actually wait on: a CI run, a deploy, a queue draining,
# a long build in another window. This polls a command and reports its verdict
# the same way a Claude session does, so those things become glanceable without
# each one needing its own integration.
#
#   --interval N   seconds between polls (default 30)
#   --name NAME    what to call this watch (default: derived from the command)
#   --count        show the first integer the command prints, instead of
#                  pass/fail. Zero is green, anything else red.
#   --once         check once and exit
#
# Examples:
#   ditoo-watch.sh --name ci --interval 60 -- \
#     gh run list -R me/repo -L1 --json conclusion -q '.[0].conclusion=="success"'
#   ditoo-watch.sh --name tests --count -- sh -c 'grep -c FAIL out.txt'
#
# It reports through ditoo-state.sh rather than talking to the device, so it
# shares the daemon's held connection and takes part in the same merge: a watch
# is just another voice, and something that needs YOU still outranks it.

set -uo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE="$SELF_DIR/ditoo-state.sh"

INTERVAL=30
NAME=""
MODE=verdict
ONCE=0

usage() {
  sed -n '3,27p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-2}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --interval) INTERVAL="${2:-}"; shift 2 ;;
    --name)     NAME="${2:-}"; shift 2 ;;
    --count)    MODE=count; shift ;;
    --once)     ONCE=1; shift ;;
    -h|--help)  usage 0 ;;
    --)         shift; break ;;
    *)          printf 'unknown option: %s\n\n' "$1" >&2; usage 2 ;;
  esac
done

[ $# -gt 0 ] || { printf 'nothing to watch: give a command after --\n\n' >&2; usage 2; }
[ -x "$STATE" ] || { printf 'cannot find ditoo-state.sh next to this script\n' >&2; exit 1; }
case "$INTERVAL" in
  ''|*[!0-9]*) printf -- '--interval wants whole seconds, got %s\n' "$INTERVAL" >&2; exit 2 ;;
esac
[ "$INTERVAL" -gt 0 ] || { printf -- '--interval must be at least 1\n' >&2; exit 2; }

# Name the watch so it gets its own slot in the merge. Without this every watch
# and every non-hook caller would collide in the single "manual" slot and
# overwrite each other -- two watches would show whichever polled last rather
# than whichever has worse news.
if [ -z "$NAME" ]; then
  NAME="$(basename "$1")"
fi
# Same character rule the session id uses: anything else could escape the
# sessions directory.
case "$NAME" in
  ''|*[!a-zA-Z0-9_-]* ) NAME="$(printf '%s' "$NAME" | tr -c 'a-zA-Z0-9_-' '-')" ;;
esac
SESSION="watch-$NAME"
export DITOO_SESSION="$SESSION"

# Ctrl-C means "stop telling me about this", so the watch stops voting. Leaving
# the last verdict behind would pin news that nobody is checking any more onto
# a panel that now has no way to update it -- and verdicts deliberately outlive
# staleness, so nothing else would clear it either.
cleanup() {
  rm -f "${DITOO_RUNDIR:-$HOME/.claude/ditoo}/sessions/$SESSION" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

report() {
  # ":now" marks an explicit verdict: this is a real result, not a Claude turn
  # that has to earn its celebration by taking long enough to be worth one.
  "$STATE" "$1" >/dev/null 2>&1
}

printf 'watching (%s) every %ss -- Ctrl-C to stop\n' "$SESSION" "$INTERVAL" >&2

last=""
while :; do
  out="$("$@" 2>/dev/null)"
  rc=$?

  if [ "$MODE" = count ]; then
    # First integer anywhere in the output. A command that prints nothing
    # countable has not told us anything, so say nothing rather than guess.
    n="$(printf '%s' "$out" | tr -c '0-9' ' ' | tr -s ' ' | sed 's/^ //' | cut -d' ' -f1)"
    if [ -n "$n" ]; then
      "$STATE" number "$n" >/dev/null 2>&1
      now="number:$n"
    else
      now="$last"
    fi
  elif [ "$rc" -eq 0 ]; then
    report 'success:now'; now=ok
  else
    report 'error:now'; now="fail($rc)"
  fi

  if [ "$now" != "$last" ]; then
    printf '%s  %s\n' "$(date '+%H:%M:%S')" "$now" >&2
    last="$now"
  fi

  [ "$ONCE" -eq 1 ] && break
  sleep "$INTERVAL"
done
