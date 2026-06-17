# SYA VisionAI

Softwarestack voor een Raspberry Pi 4 kiosk die een smartphone automatisch scant, fotografeert en gradeert met behulp van:

- een Arduino Leonardo voor gate, lade, wrist-servo's en vacuum
- een Arduino Mega met GRBL voor X/Y/Z-beweging van de robotarm
- een USB-camera voor IMEI-detectie
- een Pi CSI-camera voor extra foto's
- een Vue frontend in kiosk mode
- een FastAPI backend die de volledige flow en hardware aanstuurt

Deze README is bedoeld als:

- opstarthandleiding voor de Raspberry Pi
- overzicht van alle belangrijke commando's
- uitleg van de code-architectuur
- referentie voor debuggen en kalibreren

## 1. Doel Van Het Project

De gebruiker legt een smartphone op een lade. Daarna:

1. leest de kiosk het IMEI-nummer
2. bepaalt de Pi het toesteltype en een richtwaarde
3. opent de gate/lade zodat het toestel in de box kan
4. positioneert de robotarm zich naar het toestel
5. pakt de arm het toestel op met vacuum
6. draait de arm/wrist het toestel voor de camera
7. maakt het systeem foto's van de voor- en achterkant
8. stuurt de backend foto's en IMEI naar een damage/pricing service
9. toont de kiosk het resultaat en een prijsvoorstel

De uiteindelijke flow in code is gemodelleerd in [`backend/services/scan_orchestrator.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/scan_orchestrator.py).

## 2. Hardware Overzicht

### Raspberry Pi 4

- draait frontend + backend
- praat via USB met Leonardo en Mega
- leest de USB-camera uit voor IMEI
- kan optioneel de Pi CSI-camera gebruiken voor extra foto's

### Arduino Leonardo

Wordt aangesproken via `pyserial` en stuurt:

- gate open/dicht
- lade in/uit
- 2 wrist-servo's
- vacuum aan/uit

Ondersteunde commando's in de Python-code:

- `GATE_OPEN`
- `GATE_CLOSE`
- `TRAY_OUT`
- `TRAY_IN`
- `GATE_POS`
- `STATUS`
- `VACUUM_ON`
- `VACUUM_OFF`

Stopper-switches op de Leonardo:

- bovenste gate-stopper: `A4`
- onderste gate-stopper: `A5`
- lade-uit-stopper: `D4`
- lade-in-stopper: `D5`
- alle stopper-switches zijn normally closed en gebruiken `INPUT_PULLUP`
- sluit elke switch naar `GND`: niet geraakt = `LOW`, stopper geraakt/contact open = `HIGH`

Belangrijke responses:

- `ACK:GATE_OPEN`
- `ACK:GATE_CLOSE`
- `ACK:TRAY_OUT`
- `ACK:TRAY_IN`
- `ACK:STATUS,gateState=...,gatePos=...,trayState=...,trayPos=...`
- `GATE_POS=UP`
- `GATE_POS=DOWN`
- `ERR:...`

De backend bepaalt of een gatebeweging klaar is via `STATUS`: `gateState=0` en
`gatePos=UP` of `gatePos=DOWN`.

De Leonardo-logica zit vooral in:

- [`backend/services/machine_service.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/machine_service.py)
- [`backend/controller/arduino.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/controller/arduino.py)

### Arduino Mega + GRBL

Stuurt:

- CoreXY X/Y-beweging
- Z-as

De Mega/GRBL-logica zit in:

- [`backend/services/grbl_service.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/grbl_service.py)
- [`backend/controller/arduino.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/controller/arduino.py)

## 3. Repo Structuur

### Backend

- [`backend/websrv.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/websrv.py)
  FastAPI app, router-registratie, websocket endpoint, frontend serving, boot initialization.

- [`backend/controller/scan.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/controller/scan.py)
  HTTP API voor scan start, confirm, status en abort.

- [`backend/services/scan_orchestrator.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/scan_orchestrator.py)
  De belangrijkste machineflow. Hier staan de stappen 19-60 van jouw flowchart.

- [`backend/controller/camera.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/controller/camera.py)
  USB-camera stream, IMEI detectie, scanfoto's en Pi CSI captures.

- [`backend/services/machine_service.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/machine_service.py)
  Alle Leonardo-gerelateerde hardwareacties.

- [`backend/services/grbl_service.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/grbl_service.py)
  Alle GRBL/NEMA-bewegingen.

- [`backend/services/ai_damage_service.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/ai_damage_service.py)
  Mock of echte API-call voor damage/pricing-resultaat.

- [`backend/services/system_service.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/system_service.py)
  Boot-safe-idle, home en runtime settings.

- [`backend/controller/system.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/controller/system.py)
  Debug/system endpoints om de machine in veilige toestand te zetten.

- [`backend/controller/device_lookup.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/controller/device_lookup.py)
  Mock lookup van IMEI naar toesteltype en maximale waarde.

### Frontend

- [`frontend/src/pages/index.vue`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/frontend/src/pages/index.vue)
  De kioskflow voor de gebruiker: starten, IMEI scannen, toestel bevestigen, scanstatus volgen, resultaat tonen.

- [`frontend/src/services/websocket.js`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/frontend/src/services/websocket.js)
  Websocket client voor real-time `scan_event` updates.

### Deploy / Scripts

- [`scripts/pi_run_backend.sh`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/scripts/pi_run_backend.sh)
  Start de backend op de Pi.

- [`scripts/pi_build_frontend.sh`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/scripts/pi_build_frontend.sh)
  Bouwt de frontend productieversie.

- [`scripts/pi_start_kiosk.sh`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/scripts/pi_start_kiosk.sh)
  Start Chromium in kiosk mode.

- [`deploy/systemd/sya-backend.service`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/deploy/systemd/sya-backend.service)
  Systemd unit voor backend.

- [`deploy/systemd/sya-kiosk.service`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/deploy/systemd/sya-kiosk.service)
  Systemd unit voor kiosk/browser.

## 4. Raspberry Pi Setup

### 4.1 Repo clonen

```bash
cd /home/pi
git clone <jouw-repo-url> sya
cd sya
```

### 4.2 Systeempackages installeren

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip libzbar0 chromium-browser
```

Voor Pi CSI camera:

```bash
sudo apt install -y python3-picamera2
```

### 4.3 Project dependencies installeren

```bash
make install
```

Wat dit doet:

- maakt `backend/venv`
- installeert Python dependencies uit `backend/requirements.txt`
- installeert frontend dependencies uit `frontend/package.json`

### 4.4 Config invullen

Open:

```bash
nano backend/config/config.env
```

Belangrijkste variabelen:

- `APP_LEONARDO_PORT`
- `APP_GRBL_PORT`
- `APP_LEONARDO_BAUD`
- `APP_GRBL_BAUD`
- `APP_CAMERA_INDEX`
- `APP_PHOTO_STORAGE_DIR`
- `APP_PI_CAPTURE_DIR`
- `APP_FRONTEND_DIST`
- `APP_GRBL_FRONT_X`
- `APP_GRBL_FRONT_Y`
- `APP_GRBL_BACK_X`
- `APP_GRBL_BACK_Y`
- `APP_GRBL_Z_PICKUP`
- `APP_GRBL_Z_TRAVEL`
- `APP_GRBL_HOME_Z_CLEARANCE`
- `APP_GRBL_HOME_Z_STEP`
- `APP_GRBL_HOME_Z_SEARCH_DISTANCE`
- `APP_GRBL_HOME_Z_FEED_RATE`
- `APP_GRBL_Z_LIMIT_TOWARD_ZERO_SIGN`
- `APP_ARM_DISTANCE_THRESHOLD_CM`
- `APP_GATE_MOVE_TIMEOUT_S`
- `APP_TRAY_MOVE_TIMEOUT_S`
- `APP_USER_CONFIRM_TIMEOUT_S`
- `APP_MACHINE_SAFE_IDLE_ON_BOOT`
- `APP_DEVICE_LOOKUP_API_ENABLED`
- `APP_DEVICE_LOOKUP_API_URL`
- `APP_DEVICE_LOOKUP_API_TIMEOUT_S`
- `APP_AI_DAMAGE_API_MOCK`
- `APP_AI_DAMAGE_API_URL`

De documentatie van die env vars staat in:

- [`backend/config/config.env`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/config/config.env)
- [`backend/config/README.md`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/config/README.md)

## 5. Frontend / Backend Opstarten

### 5.1 Development mode

Backend:

```bash
make run_backend
```

Frontend:

```bash
make run_frontend
```

Samen:

```bash
make run
```

In development:

- frontend draait normaal op `http://localhost:8080`
- backend draait op `http://localhost:3000`

### 5.2 Productie / Pi mode

Frontend builden:

```bash
./scripts/pi_build_frontend.sh
```

Backend starten:

```bash
./scripts/pi_run_backend.sh
```

Dan serveert de backend de gebouwde frontend op:

```text
http://<raspberry-pi-ip>:3000
```

### 5.3 Chromium kiosk starten

Op de Pi met een actieve desktop-sessie:

```bash
./scripts/pi_start_kiosk.sh http://127.0.0.1:3000
```

## 6. Systemd Boot Op De Pi

De bedoeling is dat backend en kiosk automatisch starten bij opstarten van de Pi.

Installeer de services:

```bash
sudo cp deploy/systemd/sya-backend.service /etc/systemd/system/
sudo cp deploy/systemd/sya-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sya-backend.service
sudo systemctl enable sya-kiosk.service
sudo systemctl start sya-backend.service
sudo systemctl start sya-kiosk.service
```

Status controleren:

```bash
sudo systemctl status sya-backend.service
sudo systemctl status sya-kiosk.service
```

Logs bekijken:

```bash
journalctl -u sya-backend.service -f
journalctl -u sya-kiosk.service -f
```

## 7. Runtime Flow In De Code

### 7.1 Gebruikersflow

De frontend in [`frontend/src/pages/index.vue`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/frontend/src/pages/index.vue) doet:

1. startscherm tonen
2. case/screenprotector schoonmaakflow
3. IMEI scannen met USB-camera
4. manuele IMEI fallback aanbieden
5. toesteldata ophalen
6. gebruiker toestel laten uitschakelen
7. backend scan starten via `/api/scan/start`
8. live machine-updates ontvangen via websocket
9. eindprijs/resultaat tonen

### 7.2 Scan flow

De backend scanflow zit in [`backend/services/scan_orchestrator.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/scan_orchestrator.py).

Belangrijk:

- `start_scan()`
  Start een nieuwe scan en maakt een `ScanSession`.

- `_await_user()`
  Pauzeert de flow wanneer de gebruiker het toestel nog moet plaatsen.

- `_step()`
  Draait een hardwarefunctie in een thread en broadcast de status.

- `_execute_sequence()`
  Bevat de volledige fysieke machineflow.

### 7.3 Leonardo logica

[`backend/services/machine_service.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/machine_service.py) is de laag die letterlijk met de Leonardo praat.

Belangrijke functies:

- `open_gate()`
- `close_gate()`
- `tray_out()`
- `tray_in()`
- `wait_for_gate_done()`
- `wait_for_tray_done()`
- `set_wrist1()`
- `set_wrist2()`
- `wrist_home()`
- `vacuum_on()`
- `vacuum_off()`
- `read_distance()`

### 7.4 GRBL logica

[`backend/services/grbl_service.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/grbl_service.py) praat met de Mega via GRBL.

Belangrijke functies:

- `send_grbl()`
- `move_to_front_of_phone()`
- `move_to_back_of_phone()`
- `move_to_front_slow_with_distance_stop()`
- `move_to_back_slow_with_distance_stop()`
- `z_up()`
- `z_down()`
- `run_sequence()`
- `run_postflow_sequence()`

### 7.5 Camera logica

[`backend/controller/camera.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/controller/camera.py) beheert:

- live USB-camera stream via `/api/camera/stream`
- IMEI detectie via `/api/imei/detect`
- scanfoto's via `take_photo()`
- Pi CSI captures via `/api/camera/pi/capture`

### 7.6 Device lookup / pricing mock

[`backend/controller/device_lookup.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/controller/device_lookup.py) gebruikt standaard een lokale JSON lookup om een toesteltype, grootte en maximumwaarde te geven.
Zet `APP_DEVICE_LOOKUP_API_ENABLED=1` en `APP_DEVICE_LOOKUP_API_URL=...` om later een echte IMEI/product-API aan te sluiten.

[`backend/services/ai_damage_service.py`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/services/ai_damage_service.py) geeft:

- mock-resultaten als `APP_AI_DAMAGE_API_MOCK=1`
- echte API-calls met IMEI, sessie, maximumwaarde en alle foto's als `APP_AI_DAMAGE_API_MOCK=0`

## 8. API Endpoints

### Scan

- `POST /api/scan/start`
- `POST /api/scan/confirm`
- `POST /api/scan/abort`
- `GET /api/scan/status`

De automatische UI-flow gebruikt een expliciete state machine in plaats van losse
stapnummers: `BOOT`, `WELCOME`, `IMEI_SCAN`, `DEVICE_LOOKUP`, `WAIT_POWER_OFF`,
`LOAD_DEVICE`, `CLOSE_BOX`, `CAPTURE_FRONT`, `CAPTURE_BACK`, `UPLOAD_RESULTS`,
`RETURN_DEVICE`, `SHOW_PRICE`, `DONE`, `ERROR` en `EMERGENCY_STOP`. Hardware-substeps
worden alleen nog als detailinformatie meegestuurd via websocket-events.

### Camera

- `GET /api/camera/stream`
- `GET /api/imei/detect`
- `POST /api/camera/capture`
- `POST /api/camera/pi/capture`

### Device lookup

- `POST /api/device/lookup`

### Arduino / hardware debug

- `POST /api/arduino/servo`
- `POST /api/arduino/leonardo/servo`
- `POST /api/arduino/leonardo/gate`
- `GET /api/arduino/leonardo/gate-position`
- `POST /api/arduino/leonardo/tray`
- `GET /api/arduino/leonardo/tray-position`
- `POST /api/arduino/leonardo/home`
- `POST /api/arduino/leonardo/emergency-stop`
- `POST /api/arduino/grbl/command`
- `POST /api/arduino/grbl/unlock`
- `POST /api/arduino/grbl/home`
- `POST /api/arduino/grbl/home-xy`
- `POST /api/arduino/grbl/stop`
- `POST /api/arduino/grbl/post-flow`
- `GET /api/arduino/ports`

### System

- `GET /api/system/settings`
- `POST /api/system/safe-idle`
- `POST /api/system/home`
- `GET /api/system/boot-report`

## 9. Websocket Events

Frontend en backend communiceren live via `/ws`.

Belangrijkste event:

- `scan_event`

Types:

- `awaiting_user`
- `step_complete`
- `scan_complete`
- `scan_failed`

Frontend-afhandeling zit in [`frontend/src/services/websocket.js`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/frontend/src/services/websocket.js) en [`frontend/src/pages/index.vue`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/frontend/src/pages/index.vue).

## 10. Test- En Debugcommando's

Seriële poorten opvragen:

```bash
curl http://127.0.0.1:3000/api/arduino/ports
```

Gate positie lezen:

```bash
curl http://127.0.0.1:3000/api/arduino/leonardo/gate-position
```

Tray positie lezen:

```bash
curl http://127.0.0.1:3000/api/arduino/leonardo/tray-position
```

Machine in veilige idle toestand zetten:

```bash
curl -X POST http://127.0.0.1:3000/api/system/safe-idle
```

Home flow uitvoeren:

```bash
curl -X POST http://127.0.0.1:3000/api/system/home
```

GRBL unlock/home:

```bash
curl -X POST http://127.0.0.1:3000/api/arduino/grbl/unlock
curl -X POST http://127.0.0.1:3000/api/arduino/grbl/home
```

`/api/arduino/grbl/home` voert de volledige arm-homeflow uit: Z eerst `+2 mm`,
daarna X/Y naar hun limits, daarna Z in stappen van `-1 mm` tot de Z-limit onderaan
geraakt wordt. De exacte waarden zijn configureerbaar met `APP_GRBL_HOME_Z_*`.

Frontend build:

```bash
./scripts/pi_build_frontend.sh
```

Backend starten:

```bash
./scripts/pi_run_backend.sh
```

## 11. Kalibratiepunten

Voor echte productie moet je minstens deze parameters op de hardware afstemmen:

- `APP_GRBL_FRONT_X`
- `APP_GRBL_FRONT_Y`
- `APP_GRBL_BACK_X`
- `APP_GRBL_BACK_Y`
- `APP_GRBL_Z_PICKUP`
- `APP_GRBL_Z_TRAVEL`
- `APP_ARM_DISTANCE_THRESHOLD_CM`
- `APP_WRIST_DWELL_MS`
- `APP_GATE_MOVE_TIMEOUT_S`
- `APP_TRAY_MOVE_TIMEOUT_S`
- `APP_VACUUM_DWELL_S`

Praktisch:

- test eerst zonder echte smartphone
- test daarna met dummy toestel
- pas daarna met echte smartphone
- zet `APP_AI_DAMAGE_API_MOCK=1` tijdens mechanische integratie
- zet `APP_DEVICE_LOOKUP_API_ENABLED=0` zolang de echte IMEI/product-API nog niet bestaat

## 12. Belangrijke Opmerkingen

- De code is klaar als softwarebasis voor de Pi, maar de echte betrouwbaarheid hangt af van mechanische kalibratie.
- De Leonardo firmware en GRBL settings moeten overeenkomen met de verwachte commando's en posities in deze repo.
- De notes/Arango stukken zijn nog aanwezig uit de oorspronkelijke template, maar zijn niet kritisch voor de scannerflow.
- Voor een echte live uitrol raad ik aan om eerst alle `/api/system/*` en `/api/arduino/*` debug endpoints stap voor stap op de Pi te testen.
