#!/usr/bin/env bash
set -eu

URL="${1:-http://127.0.0.1:3000}"

export HOME="${HOME:-/home/sya}"
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

CHROMIUM_BIN="${CHROMIUM_BIN:-}"
if [ -z "$CHROMIUM_BIN" ]; then
  CHROMIUM_BIN="$(command -v chromium-browser || command -v chromium || true)"
fi
if [ -z "$CHROMIUM_BIN" ]; then
  echo "chromium-browser/chromium not found"
  exit 1
fi

exec "$CHROMIUM_BIN" \
  --kiosk \
  --incognito \
  --noerrdialogs \
  --disable-infobars \
  --check-for-update-interval=31536000 \
  "$URL"
