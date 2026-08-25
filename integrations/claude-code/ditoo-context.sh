#!/usr/bin/env bash
#
# Claude Code statusline hook: forward context usage to the Ditoo daemon, which
# paints it as a bar along the bottom row of whatever face is showing.
#
# Wire it up in ~/.claude/settings.json:
#
#   "statusLine": {
#     "type": "command",
#     "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-context.sh"
#   }
#
# Claude Code feeds this JSON on stdin and prints whatever we echo as the
# status line, so this stays silent and just records the number.

set -uo pipefail

RUNDIR="${DITOO_RUNDIR:-$HOME/.claude/ditoo}"
mkdir -p "$RUNDIR" 2>/dev/null

payload="$(head -c 8192 2>/dev/null)"

# Claude Code has moved this field around between versions, so accept any of
# the shapes rather than depending on one. Values may be a fraction or a
# percentage; both are normalised below.
value="$(printf '%s' "$payload" | grep -oE '"(context_used_percent|contextUsedPercent|percent_used|used_percent)"[[:space:]]*:[[:space:]]*[0-9.]+' | head -1 | grep -oE '[0-9.]+$')"

if [ -z "$value" ]; then
  # Fall back to computing it from token counts if they are present.
  used="$(printf '%s' "$payload" | grep -oE '"(total_tokens|used_tokens)"[[:space:]]*:[[:space:]]*[0-9]+' | head -1 | grep -oE '[0-9]+$')"
  max="$(printf '%s' "$payload" | grep -oE '"(context_window|max_tokens)"[[:space:]]*:[[:space:]]*[0-9]+' | head -1 | grep -oE '[0-9]+$')"
  if [ -n "$used" ] && [ -n "$max" ] && [ "$max" -gt 0 ]; then
    value=$(( used * 100 / max ))
  fi
fi

if [ -n "$value" ]; then
  # Normalise a 0-1 fraction to a percentage, then clamp.
  percent="$(awk -v v="$value" 'BEGIN {
    p = (v <= 1.0) ? v * 100 : v;
    if (p < 0) p = 0; if (p > 100) p = 100;
    printf "%d", p
  }')"
  printf '%s\n' "$percent" > "$RUNDIR/context" 2>/dev/null
fi

# Print nothing: the panel is the status line.
exit 0
