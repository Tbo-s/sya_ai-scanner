#!/usr/bin/env bash
set -eu

URL="${1:-http://127.0.0.1:3000}"

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/pi/.Xauthority}"

exec chromium-browser \
  --kiosk \
  --incognito \
  --noerrdialogs \
  --disable-infobars \
  --check-for-update-interval=31536000 \
  "$URL"
