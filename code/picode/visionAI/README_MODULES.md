# Module Map (What Does What)

This file explains the current code structure in `visionAI` and what each main module is responsible for.

## System Overview

- **Backend (FastAPI)**: hardware control, camera/IMEI detection, device lookup, inspection flow orchestration.
- **Frontend (Vue + Vuetify)**: kiosk UI flow (start, IMEI scan/manual input, hardware test, machine-flow screens).
- **Arduino Leonardo**: MG996R-based gate/tray/wrist actions via serial commands.
- **Arduino Mega + GRBL**: NEMA motion (prepared via GRBL endpoints/services).

## Backend Entry Points

- `backend/websrv.py`
  - Creates the FastAPI app.
  - Registers API routers from `controller/*`.
  - Exposes `/api` alive endpoint and `/docs`.
- `backend/init.py`
  - Initializes config + database (notes) on startup.
  - Fails gracefully if DB/config is missing (non-DB features still run).

## Backend Controllers (`backend/controller`)

- `arduino.py`
  - API endpoints for Arduino/serial actions:
    - Leonardo: gate/tray/open-close/positions/home/emergency-stop.
    - Wrist sequence trigger endpoint.
    - GRBL command/unlock/home/stop/post-flow.
    - Serial port listing and board-role suggestions.
- `camera.py`
  - Camera MJPEG stream endpoint.
  - IMEI detection endpoint (`/imei/detect`) using barcode decode.
- `device_lookup.py`
  - IMEI -> device model + max value lookup endpoint using local JSON test data.
- `inspection_flow.py`
  - Inspection planning/execution endpoints.
  - State-machine definition/run endpoints.
- `notes.py`
  - Legacy notes demo API (from the original template).

## Backend Services (`backend/services`)

- `machine_service.py`
  - Low-level Leonardo serial helpers.
  - Gate/tray command functions and position parsing.
  - Generic command send helpers used by other services.
- `wrist_sequence_service.py`
  - Reusable logical-angle mapping (`-90/0/+90` -> physical angles).
  - Per-servo config (`min/center/max/inverted`).
  - Explicit named wrist motion sequence with delay + simulate mode.
- `grbl_service.py`
  - GRBL command validation and serial send.
  - Configurable post-flow sequence for end-of-flow automation.
- `inspection_service.py`
  - Phase/step inspection plan builder.
  - Dry-run/live execution for currently supported Leonardo steps.
- `inspection_state_machine_service.py`
  - Full process state machine:
    - states like `BOOT`, `WELCOME`, `IMEI_SCAN`, ..., `DONE`, `ERROR`, `EMERGENCY_STOP`
  - Contains explicit transitions, full flow step list, and executable actions.
- `notes_services.py`
  - Legacy notes logic.

## Backend Config/Data

- `backend/config/config.env`
  - Documents runtime env vars:
    - Leonardo serial port/baud
    - wrist servo mapping/calibration + command templates
    - GRBL port + post-flow settings
- `backend/data/device_lookup_test.json`
  - Local test mapping for IMEI lookup.

## Frontend Structure (`frontend/src`)

- `main.js`
  - App bootstrap + plugin registration.
- `router/index.js`
  - Auto-generated page routing (`src/pages/*`).
- `pages/index.vue`
  - Main kiosk flow UI:
    - start/prep steps
    - IMEI scan + manual keypad fallback
    - lookup/model/value display
    - gate/tray/wrist test actions
    - machineflow and state-machine test actions
- `plugins/*`
  - Vuetify/router setup.
- `components/*`
  - Reusable UI components (plus legacy notes components).

## Key API Groups

- `/api/imei/*` -> camera + IMEI extraction
- `/api/device/*` -> IMEI lookup
- `/api/arduino/leonardo/*` -> gate/tray/wrist actions
- `/api/arduino/grbl/*` -> GRBL/NEMA control hooks
- `/api/inspection/*` -> plan/run + full state-machine APIs

## Where To Edit For Common Changes

- Change kiosk step UI text/order: `frontend/src/pages/index.vue`
- Change Leonardo command behavior/parsing: `backend/services/machine_service.py`
- Change wrist servo sequence/mapping: `backend/services/wrist_sequence_service.py`
- Change state machine transitions/steps: `backend/services/inspection_state_machine_service.py`
- Add new inspection endpoints: `backend/controller/inspection_flow.py`
- Add/adjust API routers: `backend/websrv.py`
