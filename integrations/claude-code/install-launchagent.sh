#!/usr/bin/env bash
#
# Install (or remove) the LaunchAgent that keeps the Ditoo daemon running from
# login, independent of whether any Claude Code session is open.
#
#   ./install-launchagent.sh          # install and start
#   ./install-launchagent.sh remove   # stop and uninstall
#
# Why this COPIES everything into ~/Library/Application Support/ditoo:
# macOS refuses to let a LaunchAgent execute anything inside ~/Documents,
# ~/Desktop or ~/Downloads -- the agent does not inherit the file-access grants
# the app that built it has, and the attempt fails with "Operation not
# permitted" (exit 126). Copying out of the protected folder is the supported
# way round it, and is what an installed background service should look like
# anyway. Re-run this after changing the faces or rebuilding the binary.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
LABEL="com.sliceofsanta.ditoo"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"
PREFIX="$HOME/Library/Application Support/ditoo"
RUNDIR="${DITOO_RUNDIR:-$HOME/.claude/ditoo}"

if [ "${1:-}" = "remove" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
  rm -f "$TARGET"
  "$HERE/ditoo-state.sh" stop >/dev/null 2>&1
  rm -rf "$PREFIX"
  printf 'removed %s and %s\n' "$LABEL" "$PREFIX"
  exit 0
fi

# Locate a binary to install. Prefer release; fall back to debug.
BIN=""
for candidate in "$REPO/target/release/divoom-ditoo-pro-controller" \
                 "$REPO/target/debug/divoom-ditoo-pro-controller"; do
  [ -x "$candidate" ] && BIN="$candidate" && break
done
if [ -z "$BIN" ]; then
  printf 'no binary found; run: cargo build --release --no-default-features --features all-image-formats\n' >&2
  exit 1
fi

mkdir -p "$PREFIX/faces" "$HOME/Library/LaunchAgents" "$RUNDIR"
cp "$BIN" "$PREFIX/divoom-ditoo-pro-controller"
cp "$HERE/ditoo-state.sh" "$HERE/ditoo-context.sh" "$PREFIX/"
cp "$HERE"/faces/*.gif "$HERE"/faces/*.png "$PREFIX/faces/" 2>/dev/null
chmod +x "$PREFIX/divoom-ditoo-pro-controller" "$PREFIX"/*.sh

sed -e "s|__SCRIPT__|$PREFIX/ditoo-state.sh|g" \
    -e "s|__RUNDIR__|$RUNDIR|g" \
    -e "s|__PREFIX__|$PREFIX|g" \
    "$HERE/$LABEL.plist" > "$TARGET"

# bootout is asynchronous: bootstrapping straight after it races the teardown
# and fails, even though the job loads correctly a moment later. Wait for the
# old job to actually go, then retry the load a few times before believing it.
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
for _ in 1 2 3 4 5 6 7 8 9 10; do
  launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || break
  sleep 1
done

loaded=""
for _ in 1 2 3 4 5; do
  launchctl bootstrap "gui/$(id -u)" "$TARGET" 2>/dev/null
  sleep 1
  if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    loaded=yes
    break
  fi
done
if [ -z "$loaded" ]; then
  printf 'failed to load the agent; check %s\n' "$TARGET" >&2
  exit 1
fi
launchctl kickstart "gui/$(id -u)/$LABEL" 2>/dev/null

printf 'installed to %s\n' "$PREFIX"
printf 'agent %s will start the daemon at login\n' "$LABEL"
printf 're-run this script after changing faces or rebuilding\n'
