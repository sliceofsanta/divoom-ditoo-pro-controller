#!/usr/bin/env bash
#
# Write the minutes until the next calendar event where the daemon can see it,
# so an otherwise-idle panel shows a countdown.
#
# Run it from cron or a LaunchAgent every minute:
#   * * * * * /path/to/ditoo-agenda.sh
#
# Needs Calendar access granted to ditoo-next-event (System Settings >
# Privacy & Security > Calendars). Without it this writes nothing and the panel
# simply shows the normal idle face -- the countdown is additive, never a
# prerequisite.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNDIR="${DITOO_RUNDIR:-$HOME/.claude/ditoo}"
HELPER="${DITOO_AGENDA_BIN:-$HERE/macos/ditoo-next-event}"

mkdir -p "$RUNDIR" 2>/dev/null

if [ ! -x "$HELPER" ]; then
  rm -f "$RUNDIR/agenda"
  exit 0
fi

minutes="$("$HELPER" 2>/dev/null)"
status=$?

# exit 0 with a number: a meeting is coming. Anything else (no events, no
# calendar access) clears the file so a stale countdown never lingers.
if [ "$status" -eq 0 ] && [ -n "$minutes" ]; then
  printf '%s\n' "$minutes" > "$RUNDIR/agenda"
else
  rm -f "$RUNDIR/agenda"
fi
exit 0
