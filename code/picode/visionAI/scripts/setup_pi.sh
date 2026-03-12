#!/usr/bin/env bash
# setup_pi.sh – one-time setup for Raspberry Pi 4
# Run as: bash setup_pi.sh
set -e

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$REPO_DIR/visionAI/backend"
FRONTEND_DIR="$REPO_DIR/visionAI/frontend"

echo "=== SYA AI-Scanner – Raspberry Pi setup ==="
echo "Repo: $REPO_DIR"

# ── System packages ──────────────────────────────────────────────────────────
sudo apt-get update -y
sudo apt-get install -y \
  python3-venv python3-pip \
  libzbar0 libzbar-dev \
  libopencv-dev \
  nodejs npm \
  git \
  chromium-browser \
  xdotool

# ── Serial access ─────────────────────────────────────────────────────────────
echo "Adding user to dialout group (serial port access)…"
sudo usermod -aG dialout "$USER"

# ── Photo storage ─────────────────────────────────────────────────────────────
sudo mkdir -p /var/sya_photos
sudo chown "$USER":"$USER" /var/sya_photos
echo "Photo storage: /var/sya_photos"

# ── Python virtual environment ────────────────────────────────────────────────
cd "$BACKEND_DIR"
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# ── Build frontend ────────────────────────────────────────────────────────────
cd "$FRONTEND_DIR"
npm install
npm run build
# Copy dist into backend so FastAPI can serve it
cp -r dist "$BACKEND_DIR/dist"

# ── systemd service ───────────────────────────────────────────────────────────
SERVICE_FILE="/etc/systemd/system/sya-scanner.service"
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=SYA AI Scanner Backend
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=$BACKEND_DIR/config/config.env
ExecStart=$BACKEND_DIR/venv/bin/uvicorn websrv:app --host 0.0.0.0 --port 3000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable sya-scanner

# ── Kiosk autostart ───────────────────────────────────────────────────────────
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/sya-kiosk.desktop" << EOF
[Desktop Entry]
Type=Application
Name=SYA Kiosk
Exec=bash -c "sleep 8 && chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run http://localhost:3000"
X-GNOME-Autostart-enabled=true
EOF

echo ""
echo "=== Setup complete ==="
echo "1. Log out and back in (or reboot) to activate serial port group."
echo "2. Start the service: sudo systemctl start sya-scanner"
echo "3. Check logs: sudo journalctl -u sya-scanner -f"
echo ""
echo "Before first run, edit:"
echo "  $BACKEND_DIR/config/config.env"
echo "  – Set APP_LEONARDO_PORT and APP_GRBL_PORT (run detect_ports.sh to find them)"
echo "  – Calibrate GRBL positions: APP_GRBL_FRONT_X/Y, APP_GRBL_BACK_X/Y, APP_GRBL_Z_PICKUP/TRAVEL"
