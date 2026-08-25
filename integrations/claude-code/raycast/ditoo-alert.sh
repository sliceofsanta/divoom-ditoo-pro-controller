#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title Raise an alert on the panel
# @raycast.mode silent
# @raycast.packageName Ditoo
# @raycast.icon 🔔
exec "$(dirname "$0")/../ditoo-state.sh" alerting
