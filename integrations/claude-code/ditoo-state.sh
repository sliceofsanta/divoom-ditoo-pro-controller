#!/usr/bin/env bash
#
# Show a Claude Code status face on a Divoom Ditoo Pro.
#
#   ditoo-state.sh working|alerting|chilling|off
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

  local face="$FACES_DIR/$state.png"
  if [ ! -f "$face" ]; then
    log "ERROR no face image for state '$state' at $face"
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
  status)
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
  working | alerting | chilling | off)
    STATE="$1"
    ;;
  *)
    printf 'usage: %s working|alerting|chilling|off|status\n' "$(basename "$SELF")" >&2
    exit 2
    ;;
esac

printf '%s\n' "$STATE" >"$DESIRED" 2>/dev/null

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
