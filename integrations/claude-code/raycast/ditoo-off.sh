#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title Blank the panel
# @raycast.mode silent
# @raycast.packageName Ditoo
# @raycast.icon ⚫
exec "$(dirname "$0")/../ditoo-state.sh" off
