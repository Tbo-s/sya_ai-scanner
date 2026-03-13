#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR/backend"

export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/pycache}"

if [ ! -x "$ROOT_DIR/backend/venv/bin/uvicorn" ]; then
  echo "backend/venv/bin/uvicorn not found. Run: make install"
  exit 1
fi

exec ../backend/venv/bin/uvicorn websrv:app --host 0.0.0.0 --port 3000
