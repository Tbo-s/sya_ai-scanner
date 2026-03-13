# SYA VisionAI

Kioskgestuurde smartphone-scanner voor Raspberry Pi 4. De applicatie combineert:

- Vue frontend in kiosk mode
- FastAPI backend op de Pi
- Arduino Leonardo via `pyserial` voor gate, lade, wrist-servo's en vacuum
- Arduino Mega met GRBL voor X/Y/Z-beweging
- USB-camera voor IMEI-detectie via OpenCV + `pyzbar`
- Pi CSI-camera voor detailfoto's
- mockbare device/pricing/damage API-integratie

## Hoofdflow

1. gebruiker start scan
2. IMEI wordt gescand of manueel ingevoerd
3. toesteltype en richtprijs worden opgehaald of gemockt
4. gebruiker schakelt toestel uit
5. backend `ScanOrchestrator` stuurt gate, lade, arm, wrist en vacuum aan
6. foto's van voor- en achterkant worden genomen
7. foto's gaan naar damage/pricing service
8. kiosk toont eindresultaat en prijs

## Belangrijke backend modules

- `backend/websrv.py`: FastAPI app, websocket endpoint, boot initialisatie
- `backend/controller/scan.py`: scan API
- `backend/services/scan_orchestrator.py`: volledige machineflow
- `backend/controller/camera.py`: USB stream, IMEI detectie, Pi captures
- `backend/services/machine_service.py`: Leonardo commando's
- `backend/services/grbl_service.py`: Mega/GRBL commando's
- `backend/services/system_service.py`: safe-idle en boot/home helpers

## Raspberry Pi setup

### 1. Repository plaatsen

```bash
cd /home/pi
git clone <jouw-repo-url> sya
cd sya
```

### 2. Dependencies installeren

```bash
make install
```

Extra Pi packages die typisch nodig zijn:

```bash
sudo apt update
sudo apt install -y libzbar0 chromium-browser
```

Voor Pi CSI camera:

```bash
sudo apt install -y python3-picamera2
```

### 3. Configuratie invullen

Gebruik [`backend/config/config.env`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/backend/config/config.env) als basis en zet de echte poorten, posities en timeouts.

Belangrijkste variabelen:

- `APP_LEONARDO_PORT`
- `APP_GRBL_PORT`
- `APP_CAMERA_INDEX`
- `APP_GRBL_FRONT_X`, `APP_GRBL_FRONT_Y`
- `APP_GRBL_BACK_X`, `APP_GRBL_BACK_Y`
- `APP_GRBL_Z_PICKUP`, `APP_GRBL_Z_TRAVEL`
- `APP_MACHINE_SAFE_IDLE_ON_BOOT`
- `APP_AI_DAMAGE_API_MOCK`

### 4. Frontend builden

```bash
./scripts/pi_build_frontend.sh
```

De backend serveert standaard `frontend/dist`, of wat in `APP_FRONTEND_DIST` staat.

### 5. Backend lokaal starten

```bash
./scripts/pi_run_backend.sh
```

Frontend is daarna beschikbaar via:

```text
http://<raspberry-pi-ip>:3000
```

## Systemd services

Service templates staan in [`deploy/systemd`](/Users/tbo/Desktop/github/sya_ai-scanner/code/picode/visionAI/deploy/systemd).

Installatievoorbeeld:

```bash
sudo cp deploy/systemd/sya-backend.service /etc/systemd/system/
sudo cp deploy/systemd/sya-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sya-backend.service
sudo systemctl enable sya-kiosk.service
sudo systemctl start sya-backend.service
sudo systemctl start sya-kiosk.service
```

## Debug endpoints

- `GET /api/arduino/ports`
- `GET /api/arduino/leonardo/gate-position`
- `GET /api/arduino/leonardo/tray-position`
- `POST /api/system/safe-idle`
- `POST /api/system/home`
- `GET /api/system/settings`
- `GET /api/scan/status`

## Opmerking

De softwareflow staat nu klaar voor echte hardware-integratie, maar de mechanische kalibratie blijft cruciaal:

- servo-hoeken moeten op de echte arm afgestemd worden
- GRBL-posities moeten fysiek ingemeten worden
- afstandssensor-threshold moet getest worden op echte toestellen
- safe-idle/home gedrag moet op de echte machine bevestigd worden
