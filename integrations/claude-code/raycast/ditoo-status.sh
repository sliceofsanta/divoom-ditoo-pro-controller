#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title Ditoo status
# @raycast.mode fullOutput
# @raycast.packageName Ditoo
# @raycast.icon 📟
exec "$(dirname "$0")/../ditoo-state.sh" status
