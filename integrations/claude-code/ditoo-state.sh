#!/usr/bin/env bash
#
# Show a Claude Code status face on a Divoom Ditoo Pro.
#
#   ditoo-state.sh thinking|working|alerting|success|error|compacting|chilling|off
#   ditoo-state.sh draw <image>   # show any image until the next state change
#   ditoo-state.sh status      # what is going on right now
#
# Designed to be called from Claude Code hooks, which means two hard rules:
#
#   1. It must return almost instantly. PreToolUse fires on every single tool
#      call, and a hook that blocks for a Bluetooth round-trip would make the
#      whole session feel sluggish. The actual send happens in a detached
#      worker; this script just records intent and returns.
#   2. It must never fail in a way that disrupts Claude Code. Every path exits
#      0; problems go to the log, not to the user's terminal.
#
# Concurrency: state changes coalesce. The desired state is a file; a single
# worker holds a lock and keeps applying until desired == applied, so a burst
# of hook calls collapses into one (or at most two) device writes, and the
# newest state always wins.

set -uo pipefail

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SELF")"

FACES_DIR="${DITOO_FACES_DIR:-$SCRIPT_DIR/faces}"
RUNDIR="${DITOO_RUNDIR:-$HOME/.claude/ditoo}"
DESIRED="$RUNDIR/desired"
APPLIED="$RUNDIR/applied"
LOCK="$RUNDIR/lock"
LOG="$RUNDIR/log"
PIDFILE="$RUNDIR/daemon.pid"
SESSIONS="$RUNDIR/sessions"

# Lock older than this is assumed to belong to a dead worker.
STALE_LOCK_SECONDS="${DITOO_STALE_LOCK_SECONDS:-90}"
# Safety net so a pathological desired/applied flap cannot spin forever.
MAX_WORKER_ITERATIONS=12

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG" 2>/dev/null
}

# Resolve the controller binary: explicit override, then PATH, then the usual
# cargo output directories relative to this checkout.
resolve_bin() {
  if [ -n "${DITOO_BIN:-}" ]; then
    # Validate rather than trusting it: a typo here should produce a clear
    # error, not an opaque "command not found" from the worker.
    if [ ! -x "$DITOO_BIN" ]; then
      return 1
    fi
    printf '%s' "$DITOO_BIN"
    return 0
  fi
  local found
  found="$(command -v divoom-ditoo-pro-controller 2>/dev/null)"
  if [ -n "$found" ]; then
    printf '%s' "$found"
    return 0
  fi
  local candidate
  for candidate in \
    "$SCRIPT_DIR/../../target/release/divoom-ditoo-pro-controller" \
    "$SCRIPT_DIR/../../target/debug/divoom-ditoo-pro-controller"; do
    if [ -x "$candidate" ]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

file_mtime() {
  # BSD (macOS) and GNU stat disagree; try both.
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || printf '0'
}

read_state_file() {
  cat "$1" 2>/dev/null || printf ''
}

# Lines in a file, or 0 if it does not exist.
#
# The existence check is not decoration: bash applies `< missing` BEFORE the
# `2>/dev/null` on the same command, so the redirect failure reaches the real
# stderr and a hook that is supposed to be silent starts printing at the user.
count_lines() {
  if [ ! -f "$1" ]; then
    printf '0'
    return 0
  fi
  local n
  n="$(wc -l <"$1" 2>/dev/null | tr -d ' ')"
  printf '%s' "${n:-0}"
}

# Claude Code puts the session id on stdin. Several sessions can drive one
# panel, so each writes its own state file and the daemon merges them --
# without this they overwrite each other and the display shows whichever
# session moved last rather than the one that needs you.
#
# Extracted with grep rather than a JSON parser on purpose: this runs on every
# hook, and spawning python here would cost more than the rest of the script.
session_id() {
  local raw=""
  if [ ! -t 0 ]; then
    raw="$(head -c 4096 2>/dev/null)"
  fi
  local id
  id="$(printf '%s' "$raw" \
    | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | head -1 | sed 's/.*"\([^"]*\)"$/\1/')"
  # Anything outside this set would let a crafted id escape $SESSIONS.
  case "$id" in
    "" ) printf 'manual' ;;
    *[!a-zA-Z0-9_-]* ) printf 'manual' ;;
    * ) printf '%s' "$id" ;;
  esac
}

# Classify a Notification into the kind of interruption it actually is, so the
# panel can say whether this needs a keystroke or twenty minutes of reading.
#
# Claude Code puts the notification text on stdin alongside the session id.
# Matching is on the message because there is no field that states the kind --
# so it is deliberately conservative: anything unrecognised falls back to the
# plain alert rather than guessing wrong and teaching you to distrust it.
classify_alert() {
  local message="$1"
  local lowered
  lowered="$(printf '%s' "$message" | tr '[:upper:]' '[:lower:]')"
  case "$lowered" in
    *permission*|*approve*|*allow*|*"needs your"*e*mission*)
      printf 'alert-permission' ;;
    *plan*|*review*|*"exit plan"*)
      printf 'alert-plan' ;;
    *question*|*"waiting for your"*|*asked*|*clarif*)
      printf 'alert-question' ;;
    *)
      printf 'alerting' ;;
  esac
}

# True when a daemon holds the connection. A pid file whose process is gone is
# stale (killed daemon, reboot) and is cleared so we fall back to one-shot
# sends rather than silently doing nothing.
daemon_running() {
  [ -f "$PIDFILE" ] || return 1
  local pid
  pid="$(cat "$PIDFILE" 2>/dev/null)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  log "clearing stale daemon pid file (pid ${pid:-unknown} is gone)"
  rm -f "$PIDFILE"
  return 1
}

# --- the worker ------------------------------------------------------------

# Run the controller, adding --device only when one is configured.
# Written without arrays: macOS ships bash 3.2, where expanding an empty array
# under `set -u` is an error.
#
# The controller defaults to debug logging, which is ~11 lines per invocation --
# far too chatty for a file that grows all day. Default it to warn; set
# DITOO_RUST_LOG=debug when diagnosing a device problem.
run_bin() {
  local bin="$1"
  shift
  if [ -n "${DITOO_DEVICE:-}" ]; then
    RUST_LOG="${DITOO_RUST_LOG:-warn}" "$bin" --device "$DITOO_DEVICE" "$@" >>"$LOG" 2>&1
  else
    RUST_LOG="${DITOO_RUST_LOG:-warn}" "$bin" "$@" >>"$LOG" 2>&1
  fi
}

# Keep the log from growing without bound.
rotate_log() {
  [ -f "$LOG" ] || return 0
  local lines
  lines="$(wc -l <"$LOG" 2>/dev/null | tr -d ' ')"
  [ -z "$lines" ] && return 0
  if [ "$lines" -gt "${DITOO_LOG_MAX_LINES:-500}" ]; then
    tail -n 200 "$LOG" >"$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null
  fi
}

apply_state() {
  local state="$1" bin="$2"

  if [ "$state" = "off" ] && [ -n "${DITOO_OFF_CLOCK_ID:-}" ]; then
    # Restore a clock face rather than blanking the display.
    run_bin "$bin" clock set "$DITOO_OFF_CLOCK_ID"
    return $?
  fi

  # Prefer the animated GIF; the PNG is a single-frame fallback for anyone who
  # drops in their own still image.
  local face=""
  local candidate
  for candidate in "$RUNDIR/$state.gif" "$RUNDIR/$state.png" \
                   "$FACES_DIR/$state.gif" "$FACES_DIR/$state.png"; do
    if [ -f "$candidate" ]; then
      face="$candidate"
      break
    fi
  done
  if [ -z "$face" ]; then
    log "ERROR no face image for state '$state' in $FACES_DIR (tried .gif, .png)"
    return 1
  fi
  run_bin "$bin" image "$face"
}

run_worker() {
  # Release the lock however we exit.
  trap 'rmdir "$LOCK" 2>/dev/null' EXIT
  rotate_log

  local bin
  if ! bin="$(resolve_bin)"; then
    log "ERROR controller binary not found (build it, or set DITOO_BIN)"
    return 0
  fi

  local iteration=0 want have
  while [ "$iteration" -lt "$MAX_WORKER_ITERATIONS" ]; do
    iteration=$((iteration + 1))
    want="$(read_state_file "$DESIRED")"
    [ -z "$want" ] && break
    have="$(read_state_file "$APPLIED")"
    [ "$want" = "$have" ] && break

    if apply_state "$want" "$bin"; then
      printf '%s\n' "$want" >"$APPLIED"
      log "applied $want"
    else
      # Leave APPLIED alone so the next hook call retries rather than
      # believing a failed write succeeded.
      log "FAILED to apply $want (device off or out of range?)"
      break
    fi
  done
  return 0
}

# --- entry point -----------------------------------------------------------

mkdir -p "$RUNDIR" 2>/dev/null

case "${1:-}" in
  --worker)
    run_worker
    exit 0
    ;;
  end)
    # A session that has finished must stop voting. Without this its last state
    # sits in the merge until it ages out, so a window closed while "working"
    # keeps the panel busy for a quarter of an hour after the work stopped.
    rm -f "$SESSIONS/$(session_id)" 2>/dev/null
    exit 0
    ;;
  draw)
    # Show an arbitrary image. Copied into the run directory rather than the
    # faces directory, which belongs to whoever drew the faces; the daemon
    # searches the run directory first so this wins without overwriting
    # anything.
    src="${2:-}"
    if [ -z "$src" ] || [ ! -f "$src" ]; then
      printf 'usage: %s draw <image file>\n' "$(basename "$SELF")" >&2
      exit 2
    fi
    mkdir -p "$RUNDIR" 2>/dev/null
    rm -f "$RUNDIR/custom.gif" "$RUNDIR/custom.png"
    case "$src" in
      *.gif|*.GIF) cp "$src" "$RUNDIR/custom.gif" ;;
      *)           cp "$src" "$RUNDIR/custom.png" ;;
    esac
    mkdir -p "$SESSIONS" 2>/dev/null
    printf 'custom\n' > "$SESSIONS/$(session_id)"
    printf 'custom\n' > "$DESIRED"
    if ! daemon_running; then
      # No daemon: fall through to the usual one-shot worker.
      if mkdir "$LOCK" 2>/dev/null; then
        nohup "$SELF" --worker >/dev/null 2>&1 &
      fi
    fi
    exit 0
    ;;
  start)
    if daemon_running; then
      printf 'daemon already running (pid %s)\n' "$(cat "$PIDFILE")"
      exit 0
    fi
    if ! BIN="$(resolve_bin)"; then
      printf 'controller binary not found (build it, or set DITOO_BIN)\n' >&2
      exit 1
    fi
    printf '%s\n' "${DITOO_START_STATE:-chilling}" >"$DESIRED"
    rm -f "$APPLIED"
    rotate_log
    if [ -n "${DITOO_DEVICE:-}" ]; then
      nohup "$BIN" --device "$DITOO_DEVICE" daemon "$DESIRED" "$FACES_DIR" >>"$LOG" 2>&1 &
    else
      nohup "$BIN" daemon "$DESIRED" "$FACES_DIR" >>"$LOG" 2>&1 &
    fi
    # The daemon writes the pid file itself; wait briefly so `start` only
    # reports success once it has actually claimed it.
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
      if daemon_running; then
        printf 'daemon started (pid %s)\n' "$(cat "$PIDFILE")"
        exit 0
      fi
      sleep 1
    done
    printf 'daemon did not start; see %s\n' "$LOG" >&2
    exit 1
    ;;
  stop)
    if ! daemon_running; then
      printf 'no daemon running\n'
      exit 0
    fi
    pid="$(cat "$PIDFILE")"
    kill "$pid" 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    rm -f "$PIDFILE"
    printf 'daemon stopped\n'
    exit 0
    ;;
  status)
    if daemon_running; then
      printf 'daemon  : running (pid %s) -- one held connection, no chime\n' "$(cat "$PIDFILE")"
    else
      printf 'daemon  : not running -- each change reconnects (device will chime)\n'
    fi
    live=0
    if [ -d "$SESSIONS" ]; then
      live=$(find "$SESSIONS" -type f -mmin -15 2>/dev/null | wc -l | tr -d ' ')
    fi
    if [ "$live" -gt 1 ]; then
      printf 'sessions: %s live -- panel shows the highest priority:\n' "$live"
      find "$SESSIONS" -type f -mmin -15 2>/dev/null | while read -r f; do
        printf '            %s = %s\n' "$(basename "$f" | cut -c1-8)" "$(cat "$f" 2>/dev/null)"
      done
    fi
    printf 'desired : %s\n' "$(read_state_file "$DESIRED")"
    printf 'applied : %s\n' "$(read_state_file "$APPLIED")"
    if [ -d "$LOCK" ]; then
      printf 'worker  : running (lock held %ss)\n' "$(( $(date +%s) - $(file_mtime "$LOCK") ))"
    else
      printf 'worker  : idle\n'
    fi
    printf 'binary  : %s\n' "$(resolve_bin || printf 'NOT FOUND')"
    printf 'faces   : %s\n' "$FACES_DIR"
    printf -- '--- last 10 log lines ---\n'
    tail -n 10 "$LOG" 2>/dev/null || printf '(no log yet)\n'
    exit 0
    ;;
  alert)
    # Reads the whole hook payload once: the session id AND the message have to
    # come from the same stdin, which can only be consumed one time.
    payload="$(head -c 8192 2>/dev/null)"
    id="$(printf '%s' "$payload" \
      | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' \
      | head -1 | sed 's/.*"\([^"]*\)"$/\1/')"
    case "$id" in
      "" | *[!a-zA-Z0-9_-]* ) id=manual ;;
    esac
    message="$(printf '%s' "$payload" \
      | grep -o '"message"[[:space:]]*:[[:space:]]*"[^"]*"' \
      | head -1 | sed 's/.*"\([^"]*\)"$/\1/')"
    STATE="$(classify_alert "$message")"
    log "alert: $STATE (from: ${message:-no message})"
    mkdir -p "$SESSIONS" 2>/dev/null
    printf '%s\n' "$STATE" > "$SESSIONS/$id"
    printf '%s\n' "$STATE" > "$DESIRED"
    if ! daemon_running && mkdir "$LOCK" 2>/dev/null; then
      nohup "$SELF" --worker >/dev/null 2>&1 &
    fi
    exit 0
    ;;
  turn)
    # A human just started a turn. Two things follow from that, and both are
    # about the panel not lying once you are back at the keyboard:
    #
    #   - last turn's fan-out pips are not this turn's news, so clear them;
    #   - the daemon holds a verdict indefinitely while nobody has come back to
    #     it, so a build that failed overnight is still red in the morning.
    #     This is the "came back" signal that releases the hold.
    rm -f "$RUNDIR/fanout" "$RUNDIR/fanout.start" "$RUNDIR/fanout.done" 2>/dev/null
    : > "$RUNDIR/last-prompt" 2>/dev/null
    exit 0
    ;;
  fanout)
    # Track a fan-out of parallel agents, drawn as pips along the top row.
    #
    # Counted by APPENDING a line per event and counting lines, not by
    # incrementing a number in a file. Subagents start and finish concurrently,
    # so read-modify-write would drop events under exactly the conditions this
    # is meant to measure -- a wide fan-out. A single short append is atomic;
    # two hooks racing both get counted.
    case "${2:-}" in
      start|done)
        printf 'x\n' >> "$RUNDIR/fanout.${2}" 2>/dev/null
        started="$(count_lines "$RUNDIR/fanout.start")"
        finished="$(count_lines "$RUNDIR/fanout.done")"
        if [ "$started" -gt 0 ]; then
          printf '%s/%s\n' "$finished" "$started" > "$RUNDIR/fanout"
        fi
        ;;
      clear)
        # At the start of a turn: last turn's pips are not this turn's news.
        rm -f "$RUNDIR/fanout" "$RUNDIR/fanout.start" "$RUNDIR/fanout.done" 2>/dev/null
        ;;
      *)
        printf 'usage: %s fanout start|done|clear\n' "$(basename "$SELF")" >&2
        exit 2 ;;
    esac
    exit 0
    ;;
  number)
    # Show a number on the panel: test failures, agents running, anything
    # countable. Held until the next state change, like draw.
    value="${2:-}"
    case "$value" in
      ''|*[!0-9]*) printf 'usage: %s number <0-99>\n' "$(basename "$SELF")" >&2; exit 2 ;;
    esac
    mkdir -p "$RUNDIR" 2>/dev/null
    printf '%s\n' "$value" > "$RUNDIR/number"
    STATE="number"
    ;;
  thinking | working | alerting | alert-question | alert-permission | alert-plan \
    | meeting | busy | number | success | error | compacting | chilling | custom | off)
    STATE="$1"
    ;;
  *)
    printf 'usage: %s thinking|working|alerting|success|error|compacting|chilling|busy|meeting|off\n       %s alert  (reads a Notification payload on stdin)\n       %s number <0-99> | fanout start|done|clear | turn\n       %s draw <image> | end | start | stop | status\n' "$(basename "$SELF")" "$(basename "$SELF")" "$(basename "$SELF")" >&2
    exit 2
    ;;
esac

mkdir -p "$SESSIONS" 2>/dev/null
printf '%s\n' "$STATE" >"$SESSIONS/$(session_id)" 2>/dev/null
printf '%s\n' "$STATE" >"$DESIRED" 2>/dev/null

# If the daemon is running it is watching $DESIRED, which we just wrote, so
# there is nothing else to do. This is the whole point of the daemon: no
# connect, no disconnect, and none of the chime the device plays for them.
if daemon_running; then
  exit 0
fi

# Fast path: nothing to do. This is the common case (PreToolUse firing
# repeatedly while already "working"), so it must not fork anything.
if [ "$(read_state_file "$APPLIED")" = "$STATE" ]; then
  exit 0
fi

# Take the lock, or leave it to the worker that already holds it -- it will
# pick up the state we just wrote.
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -d "$LOCK" ]; then
    lock_age=$(( $(date +%s) - $(file_mtime "$LOCK") ))
    if [ "$lock_age" -gt "$STALE_LOCK_SECONDS" ]; then
      log "breaking stale lock (${lock_age}s old)"
      rmdir "$LOCK" 2>/dev/null
    fi
  fi
  exit 0
fi

# Hand off to a detached worker so the hook returns immediately. The worker
# inherits the lock we just took and releases it when done.
nohup "$SELF" --worker >/dev/null 2>&1 &

exit 0
