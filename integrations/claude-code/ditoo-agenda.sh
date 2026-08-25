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
# Prefer the .app bundle: macOS will not show a Calendar prompt for a bare CLI
# binary launched from a non-GUI parent, and the Calendars pane has no "add
# application" button -- an app can only appear there by asking. The bundle
# holds the grant, so the bundled executable is the one that can read events.
HELPER=""
for candidate in "${DITOO_AGENDA_BIN:-}" \
                 "$HOME/Library/Application Support/ditoo/DitooAgenda.app/Contents/MacOS/DitooAgenda" \
                 "$HERE/macos/DitooAgenda.app/Contents/MacOS/DitooAgenda" \
                 "$HERE/macos/ditoo-next-event"; do
  [ -n "$candidate" ] && [ -x "$candidate" ] && HELPER="$candidate" && break
done

mkdir -p "$RUNDIR" 2>/dev/null

if [ -z "$HELPER" ]; then
  rm -f "$RUNDIR/agenda"
  exit 0
fi

# The bundled build writes $RUNDIR/agenda itself and prints nothing; the older
# bare binary prints the number. Handle both, and let any failure clear the
# file so a stale countdown never lingers on the panel.
case "$HELPER" in
  *DitooAgenda)
    # Launched with `open`, NOT by running the executable directly. TCC grants
    # the BUNDLE; invoking the inner binary from a shell attributes the request
    # to whatever spawned the shell instead, which has no calendar grant and is
    # refused. `open` returns immediately, so the file lands a moment later --
    # fine for something that refreshes on a timer.
    APP_BUNDLE="${HELPER%/Contents/MacOS/DitooAgenda}"
    open -a "$APP_BUNDLE" >/dev/null 2>&1 || true
    ;;
  *)
    minutes="$("$HELPER" 2>/dev/null)"
    if [ $? -eq 0 ] && [ -n "$minutes" ]; then
      printf '%s\n' "$minutes" > "$RUNDIR/agenda"
    else
      rm -f "$RUNDIR/agenda"
    fi
    ;;
esac
exit 0
