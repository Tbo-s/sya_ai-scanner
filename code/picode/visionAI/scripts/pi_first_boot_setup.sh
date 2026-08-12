#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

sudo apt update
sudo apt install -y git curl python3 python3-venv python3-pip libzbar0

if ! sudo apt install -y chromium-browser; then
  sudo apt install -y chromium
fi

sudo apt install -y python3-picamera2 || true

make install
./scripts/pi_build_frontend.sh
mkdir -p captures

sudo cp deploy/systemd/sya-backend.service /etc/systemd/system/
sudo cp deploy/systemd/sya-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sya-backend.service
sudo systemctl enable sya-kiosk.service

echo "Pi setup complete."
echo "Review backend/config/config.env before starting services."
echo "Boot homing is intentionally disabled until all limit switches are verified."
