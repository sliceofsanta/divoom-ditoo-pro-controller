#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title Draw an image on the Ditoo
# @raycast.mode silent
# @raycast.packageName Ditoo
# @raycast.icon 🖼️
# @raycast.argument1 { "type": "text", "placeholder": "path to image" }
exec "$(dirname "$0")/../ditoo-state.sh" draw "$1"
