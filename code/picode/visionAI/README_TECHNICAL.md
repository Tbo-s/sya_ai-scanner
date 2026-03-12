# SYA VisionAI Technical README

This document explains the current codebase module-by-module, with focus on:

- Raspberry Pi orchestration
- Arduino Leonardo + Mega communication
- IMEI scanning and lookup
- Frontend kiosk flow

## 1. Runtime Architecture

System at runtime:

1. User interacts with the kiosk UI (`frontend`, Vue/Vuetify).
2. UI calls FastAPI endpoints (`backend/controller/*`).
3. Backend communicates with:
   - Arduino Leonardo (MG996R gate/tray) via `pyserial`
   - Arduino Mega (GRBL / NEMA) via `pyserial`
   - USB camera for IMEI stream/scan via OpenCV + pyzbar
   - Raspberry Pi CSI camera for still-photo capture via `picamera2`
4. Backend can call device-lookup logic using local JSON (mock mode).

Main process boundaries:

- `backend/websrv.py` starts FastAPI and mounts all routers.
- `frontend/src/pages/index.vue` contains the main kiosk flow screens.

## 2. Backend Overview

### 2.1 Entry Files

- `backend/websrv.py`
  - Creates `FastAPI()` app
  - Registers routers:
    - `controller/notes.py`
    - `controller/camera.py`
    - `controller/arduino.py`
    - `controller/device_lookup.py`
  - Exposes:
    - `GET /api` alive check
    - `GET /docs` Swagger
    - `GET /redoc` ReDoc

- `backend/init.py`
  - Initializes config and DB-backed notes service.
  - Handles failures gracefully so hardware endpoints can still run without DB.

### 2.2 Controllers (`backend/controller`)

- `arduino.py`
  - Main hardware API facade.
  - Leonardo endpoints:
    - `POST /api/arduino/leonardo/gate`
    - `GET /api/arduino/leonardo/gate-position`
    - `POST /api/arduino/leonardo/tray`
    - `GET /api/arduino/leonardo/tray-position`
    - `POST /api/arduino/leonardo/home`
    - `POST /api/arduino/leonardo/emergency-stop`
  - GRBL/Mega endpoints:
    - `POST /api/arduino/grbl/command`
    - `POST /api/arduino/grbl/unlock`
    - `POST /api/arduino/grbl/home`
    - `POST /api/arduino/grbl/stop`
    - `POST /api/arduino/grbl/post-flow` (configurable sequence)
  - Utility endpoints:
    - `GET /api/arduino/ports` (serial enumeration and board role suggestions)
    - Legacy servo endpoints kept for compatibility:
      - `POST /api/arduino/servo`
      - `POST /api/arduino/leonardo/servo`

- `camera.py`
  - USB camera stream and IMEI detection:
    - `GET /api/camera/stream` (MJPEG stream)
    - `GET /api/imei/detect` (barcode decode + IMEI extraction)
  - Raspberry Pi CSI still capture:
    - `POST /api/camera/pi/capture`
    - Saves photos locally on Pi (`APP_PI_CAPTURE_DIR`)

- `device_lookup.py`
  - IMEI -> device model/value resolver.
  - Endpoint:
    - `POST /api/device/lookup`
  - Uses `backend/data/device_lookup_test.json` by default.
  - Supports exact match + TAC prefix match + fallback.

- `notes.py`
  - Legacy notes template API.

### 2.3 Services (`backend/services`)

- `machine_service.py`
  - Leonardo serial primitives and domain actions.
  - Responsibilities:
    - Send commands to Leonardo
    - Read responses
    - Parse gate/tray status lines
    - Expose actions:
      - `open_gate()`, `close_gate()`
      - `tray_out()`, `tray_in()`
      - `get_gate_position()`, `get_tray_position()`
      - `home_machine()`, `emergency_stop()`

- `grbl_service.py`
  - GRBL-safe command sending and response handling.
  - Responsibilities:
    - Validate command safety
    - Send GRBL command to Mega
    - Parse `ok`/`error` responses
    - Run configurable post-flow command sequence

- `notes_services.py`
  - Legacy notes business logic.

### 2.4 Utils (`backend/utils`)

- `database_utils.py`
  - ArangoDB CRUD helpers (notes domain).
- `socket_utils.py`
  - WebSocket connection manager.

### 2.5 Config and Data

- `backend/config/config.env`
  - Documents environment variables.
  - Relevant hardware keys:
    - `APP_LEONARDO_PORT`, `APP_LEONARDO_BAUD`, `APP_LEONARDO_READ_TIMEOUT_S`
    - `APP_GRBL_PORT`, `APP_GRBL_BAUD`, `APP_GRBL_READ_TIMEOUT_S`
    - `APP_GRBL_POSTFLOW_ENABLED`, `APP_GRBL_POSTFLOW_SEQUENCE`
    - `APP_PI_CAPTURE_DIR`

- `backend/data/device_lookup_test.json`
  - Mock IMEI lookup dataset.

### 2.6 Tests (`backend/tests`)

- `test_arduino.py`
  - Controller helpers: command validation, board-role inference, port suggestion.
- `test_machine_service.py`
  - Parsing logic for gate/tray status.
- `test_grbl_service.py`
  - GRBL command safety and sequence parsing.
- `test_device_lookup.py`
  - IMEI normalization and lookup resolution.
- `test_notes.py`, `test_utils.py`
  - Legacy notes/template tests.

## 3. Frontend Overview (`frontend/src`)

### 3.1 App Shell

- `App.vue`
  - Global `v-app`, app bar title (`SYA`), and `<router-view />`.

- `main.js`
  - Creates Vue app.
  - Registers plugins (Vuetify, Pinia, router).
  - Injects websocket service.

### 3.2 Router

- `router/index.js`
  - Auto route generation from `pages/*.vue`.

### 3.3 Kiosk Flow Screen

- `pages/index.vue`
  - Primary kiosk flow and stateful UI.
  - Includes:
    - startup/preparation steps
    - IMEI scan with USB camera
    - manual IMEI keypad fallback
    - device lookup display (model + max value)
    - Leonardo gate test controls
    - Pi camera photo capture button (CSI camera)
    - transition to final confirmation steps
    - optional GRBL post-flow trigger at end

### 3.4 Plugins/Store/Services

- `plugins/index.js` and `plugins/vuetify.js`
  - Registers Vuetify + router + Pinia.
- `store/*`
  - Generic app/messages stores (template leftovers, still usable).
- `services/websocket.js`
  - Browser websocket client for `/ws`.

### 3.5 Other UI Modules

- `components/*`
  - Mostly legacy notes UI components from template.
- `pages/notes/*`
  - Legacy notes pages.

## 4. Hardware Command Contracts

Leonardo command set currently used by backend:

- `GATE_OPEN`
- `GATE_CLOSE`
- `TRAY_OUT`
- `TRAY_IN`
- `GATE_POS`
- `STATUS`
- `STOP_ALL` (emergency stop)

Expected Leonardo response patterns parsed by backend:

- `GATE_POS=UP|DOWN|UNKNOWN`
- `gateState=..., trayOutSw=..., trayInSw=...` (for tray position derivation)

GRBL command flow:

- Validates command charset before send
- Waits for `ok` or `error...` unless `wait_for_ok=False`

## 5. API Map (Quick)

Core UI/API paths:

- IMEI scan:
  - `GET /api/camera/stream`
  - `GET /api/imei/detect`
- IMEI lookup:
  - `POST /api/device/lookup`
- Pi CSI photo capture:
  - `POST /api/camera/pi/capture`
- Leonardo actions:
  - `POST /api/arduino/leonardo/gate`
  - `POST /api/arduino/leonardo/tray`
  - `GET /api/arduino/leonardo/gate-position`
  - `GET /api/arduino/leonardo/tray-position`
  - `POST /api/arduino/leonardo/home`
  - `POST /api/arduino/leonardo/emergency-stop`
- GRBL actions:
  - `POST /api/arduino/grbl/command`
  - `POST /api/arduino/grbl/post-flow`

## 6. Raspberry Pi Deployment Notes

### 6.1 Backend dependencies

Already listed in `backend/requirements.txt`:

- `fastapi`, `uvicorn`
- `opencv-python-headless`
- `pyserial`
- `requests`

For IMEI barcode decode, install:

- Python: `pyzbar`
- System: `libzbar0`

For CSI camera capture endpoint, install:

- `python3-picamera2` (APT package on Raspberry Pi OS)

### 6.2 Camera split

- USB camera (`OpenCV`) is used for IMEI stream/scan.
- CSI camera (`Picamera2`) is used for photo capture and file saving on Pi.

## 7. Where To Change What

- Change kiosk flow text/buttons:
  - `frontend/src/pages/index.vue`

- Change Leonardo command parsing/behavior:
  - `backend/services/machine_service.py`
  - `backend/controller/arduino.py`

- Change GRBL safety/sequence behavior:
  - `backend/services/grbl_service.py`

- Change IMEI lookup rules or mock data:
  - `backend/controller/device_lookup.py`
  - `backend/data/device_lookup_test.json`

- Change camera behavior:
  - `backend/controller/camera.py`

## 8. Known Gaps / Planned Integrations

The current codebase is already usable for:

- kiosk UI flow
- IMEI scan + manual fallback
- Leonardo gate/tray control
- basic GRBL command path
- local Pi image capture and save

Still to integrate fully for complete autonomous grading:

- full NEMA motion choreography (X/Y/Z)
- vacuum motor switching in live run path
- distance/tactile sensor stop logic in backend action orchestration
- full multi-angle capture automation and upload pipeline
- external pricing API integration with accept/reject finalization
