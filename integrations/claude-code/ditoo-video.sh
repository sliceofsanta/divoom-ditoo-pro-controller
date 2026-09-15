#!/usr/bin/env bash
#
# Play a video on the 16x16 panel: a local file, or a URL yt-dlp can resolve.
#
#   ditoo-video.sh [--seconds N] [--audio] <file-or-url>
#
# Three things this handles that the bare `video` command does not.
#
# 1. The daemon holds the only RFCOMM connection, so playback has to take it.
#    The LaunchAgent has KeepAlive, which means a plain kill just respawns it --
#    it has to be booted out and bootstrapped back. This does that, and puts it
#    back however the script exits, including Ctrl-C.
# 2. A URL is resolved to a VIDEO-ONLY stream. Not just muted: the audio track
#    is never fetched, so there is nothing to leak to the speaker.
# 3. mpv is told to mute anyway, belt and braces, because the video path will
#    otherwise hunt for the Ditoo's audio sink and play through it.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNDIR="${DITOO_RUNDIR:-$HOME/.claude/ditoo}"
AGENT="$HOME/Library/LaunchAgents/com.sliceofsanta.ditoo.plist"
LABEL="com.sliceofsanta.ditoo"

SECONDS_LIMIT=""
WANT_AUDIO=0

while [ $# -gt 0 ]; do
  case "$1" in
    --seconds) SECONDS_LIMIT="${2:-}"; shift 2 ;;
    --audio)   WANT_AUDIO=1; shift ;;
    -h|--help) sed -n '3,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --)        shift; break ;;
    -*)        printf 'unknown option: %s\n' "$1" >&2; exit 2 ;;
    *)         break ;;
  esac
done

SOURCE="${1:-}"
[ -n "$SOURCE" ] || { printf 'usage: %s [--seconds N] [--audio] <file-or-url>\n' "$(basename "$0")" >&2; exit 2; }
case "$SECONDS_LIMIT" in
  '') : ;;
  *[!0-9]*|0) printf -- '--seconds wants a whole number of seconds\n' >&2; exit 2 ;;
esac

resolve_bin() {
  local c
  for c in "${DITOO_BIN:-}" \
           "$(command -v divoom-ditoo-pro-controller 2>/dev/null)" \
           "$HERE/../../target/release/divoom-ditoo-pro-controller" \
           "$HERE/../../target/debug/divoom-ditoo-pro-controller"; do
    [ -n "$c" ] && [ -x "$c" ] && printf '%s' "$c" && return 0
  done
  return 1
}
BIN="$(resolve_bin)" || { printf 'controller not found; build with --features video\n' >&2; exit 1; }

# The video subcommand only exists when the binary was built with it.
if ! "$BIN" video --help >/dev/null 2>&1; then
  printf 'this build has no `video` command. Rebuild:\n' >&2
  printf '  LIBRARY_PATH=/opt/homebrew/lib cargo build --release \\\n' >&2
  printf '    --no-default-features --features video,all-image-formats\n' >&2
  exit 1
fi

# --- take the panel --------------------------------------------------------

DAEMON_WAS_UP=0
release_panel() {
  [ "$DAEMON_WAS_UP" -eq 1 ] || return 0
  DAEMON_WAS_UP=0
  if [ -f "$AGENT" ]; then
    launchctl bootstrap "gui/$(id -u)" "$AGENT" >/dev/null 2>&1
  fi
}
trap 'release_panel' EXIT INT TERM

if pgrep -f 'divoom-ditoo-pro-controller daemon' >/dev/null 2>&1; then
  DAEMON_WAS_UP=1
  printf 'stopping the status daemon to borrow the connection...\n' >&2
  if [ -f "$AGENT" ]; then
    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1
  else
    kill "$(cat "$RUNDIR/daemon.pid" 2>/dev/null)" 2>/dev/null
  fi
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -f 'divoom-ditoo-pro-controller daemon' >/dev/null 2>&1 || break
    sleep 1
  done
fi

# --- resolve the source ----------------------------------------------------

TARGET="$SOURCE"
if [ ! -f "$SOURCE" ]; then
  command -v yt-dlp >/dev/null 2>&1 || {
    printf 'not a file, and yt-dlp is not installed: %s\n' "$SOURCE" >&2
    exit 1
  }
  printf 'resolving stream...\n' >&2
  # Video-only, smallest that still looks like something at 16x16. Downscaling
  # 4K to 256 pixels wastes bandwidth and decode for no visible gain.
  SELECT='bv*[height<=480][ext=mp4]/bv*[height<=480]/bv*/b'
  [ "$WANT_AUDIO" -eq 1 ] && SELECT='b[height<=480]/b'
  TARGET="$(yt-dlp -f "$SELECT" -g "$SOURCE" 2>/dev/null | head -1)"
  [ -n "$TARGET" ] || { printf 'could not resolve a stream from %s\n' "$SOURCE" >&2; exit 1; }
fi

# --- play ------------------------------------------------------------------

MUTE="mute=yes"
[ "$WANT_AUDIO" -eq 1 ] && MUTE="mute=no"

printf 'playing%s (Ctrl-C to stop)\n' \
  "$([ -n "$SECONDS_LIMIT" ] && printf ' for %ss' "$SECONDS_LIMIT")" >&2

if [ -n "${DITOO_DEVICE:-}" ]; then
  "$BIN" --device "$DITOO_DEVICE" video "$TARGET" --mpv-option "$MUTE" >/dev/null 2>&1 &
else
  "$BIN" video "$TARGET" --mpv-option "$MUTE" >/dev/null 2>&1 &
fi
PLAYER=$!

if [ -n "$SECONDS_LIMIT" ]; then
  # Poll rather than sleep-then-kill, so a video that ends early is noticed.
  waited=0
  while [ "$waited" -lt "$SECONDS_LIMIT" ]; do
    kill -0 "$PLAYER" 2>/dev/null || break
    sleep 1
    waited=$((waited + 1))
  done
  kill "$PLAYER" 2>/dev/null
  sleep 1
  kill -9 "$PLAYER" 2>/dev/null
else
  wait "$PLAYER"
fi

printf 'done; giving the panel back\n' >&2
