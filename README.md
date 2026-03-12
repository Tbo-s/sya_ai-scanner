# SYA AI-Scanner

Een geautomatiseerde smartphone-gradeerder. De gebruiker legt zijn toestel op een lade, het systeem fotografeert alle kanten met een robotarm, en een AI-analyse bepaalt de staat en geeft een bod.

---

## Inhoudsopgave

1. [Architectuur overzicht](#1-architectuur-overzicht)
2. [Hardware](#2-hardware)
3. [Arduino Leonardo – servo & vacuum control](#3-arduino-leonardo--servo--vacuum-control)
4. [Arduino Mega – GRBL CNC](#4-arduino-mega--grbl-cnc)
5. [Raspberry Pi 4 – backend (FastAPI)](#5-raspberry-pi-4--backend-fastapi)
6. [Raspberry Pi 4 – frontend (Vue 3)](#6-raspberry-pi-4--frontend-vue-3)
7. [De volledige 65-stappen flow](#7-de-volledige-65-stappen-flow)
8. [Scan Orchestrator – hoe werkt de scansequentie](#8-scan-orchestrator--hoe-werkt-de-scansequentie)
9. [WebSocket communicatie](#9-websocket-communicatie)
10. [AI schade-analyse service](#10-ai-schade-analyse-service)
11. [IMEI lookup](#11-imei-lookup)
12. [Configuratie (config.env)](#12-configuratie-configenv)
13. [Installatie op de Raspberry Pi](#13-installatie-op-de-raspberry-pi)
14. [Development starten (laptop)](#14-development-starten-laptop)
15. [Kalibratie van de arm](#15-kalibratie-van-de-arm)
16. [Troubleshooting](#16-troubleshooting)
17. [Projectstructuur](#17-projectstructuur)

---

## 1. Architectuur overzicht

```
┌─────────────────────────────────────────────────────────┐
│                    Raspberry Pi 4                        │
│                                                          │
│  ┌──────────────┐        ┌──────────────────────────┐   │
│  │  Vue 3 (SPA) │◄──WS──►│   FastAPI backend         │   │
│  │  Vuetify     │        │   (uvicorn, port 3000)    │   │
│  │  Pinia store │        │                          │   │
│  └──────────────┘        │  ┌────────────────────┐  │   │
│                          │  │ ScanOrchestrator   │  │   │
│                          │  │ (asyncio Task)     │  │   │
│                          │  └────────┬───────────┘  │   │
│                          └───────────┼───────────────┘   │
│                                      │                    │
│              USB                     │ USB                │
│         ┌────┴────┐           ┌──────┴──────┐            │
│         │ Arduino │           │   Arduino   │            │
│         │ Leonardo│           │    Mega     │            │
│         │(servos) │           │   (GRBL)    │            │
│         └────┬────┘           └──────┬──────┘            │
└─────────────┼────────────────────────┼───────────────────┘
              │                        │
    ┌─────────┴──────────┐    ┌────────┴────────┐
    │ • Gate servo (360°)│    │ • NEMA17 X-as   │
    │ • Tray servo (360°)│    │ • NEMA17 Y-as   │
    │ • Wrist 1 (180°)   │    │ • NEMA17 Z-as   │
    │ • Wrist 2 (180°)   │    └─────────────────┘
    │ • Vacuum relay     │
    │ • HC-SR04 sensor   │
    │ • 4× NC switches   │
    └────────────────────┘
```

**Data flow samengevat:**

1. Gebruiker bedient de touchscreen kiosk (Vue frontend)
2. Frontend praat via HTTP met de FastAPI backend
3. Backend stuurt commando's via pySerial naar de Arduino's
4. De ScanOrchestrator coördineert de volledige scansequentie en stuurt real-time updates via WebSocket terug naar de frontend

---

## 2. Hardware

### Componenten

| Component | Aantal | Functie |
|---|---|---|
| Raspberry Pi 4 | 1 | Centrale computer – draait backend + frontend |
| Arduino Leonardo | 1 | Servo + vacuum control |
| Arduino Mega (GRBL) | 1 | NEMA17 stappenmotoren (XYZ) |
| NEMA17 stappenmotor | 3 | X-as, Y-as (CoreXY), Z-as (arm op/neer) |
| MG996R 360° servo | 2 | Gate (open/dicht), Tray (uitschuiven/inrijden) |
| MG996R 180° servo | 2 | Wrist van de arm (toestel draaien) |
| Vacuum motor + relay | 1 | Vastzuigen van het toestel |
| HC-SR04 afstandssensor | 1 | Detecteert wanneer arm het toestel raakt |
| NC micro-switch | 4 | Eindposities gate en tray |
| USB camera | 1 | IMEI-scan + foto's van het toestel |
| Display (touchscreen) | 1 | Kiosk UI |

### Bedradingsprincipes

**NC switches (Normally Closed):**
De eindstops zijn NC aangesloten op de Arduino Leonardo. Ze zijn verbonden tussen de pin en GND. `INPUT_PULLUP` is actief op elke pin.

- **Ruststand** (NC = gesloten): schakelaar geleidt → pin verbonden met GND → pin leest **LOW**
- **Geactiveerd** (NC opent = circuit verbroken): interne pullup trekt pin naar 5V → pin leest **HIGH**

De firmware stopt de servo zodra de pin HIGH wordt.

```
5V (intern pullup)
    │
Arduino pin ──[NC switch]── GND

Ruststand:  schakelaar dicht → pin = LOW
Geactiveerd: schakelaar open → pin = HIGH (pullup)
```

**Vacuum relay:**
Een digitale uitgang (pin 6) stuurt een relay aan. `HIGH` = vacuum aan, `LOW` = vacuum uit.

**HC-SR04:**
- Trigger → pin A0 (output)
- Echo → pin A1 (input)
- Meting: puls sturen → echo meten → afstand berekenen in cm

---

## 3. Arduino Leonardo – servo & vacuum control

**Bestand:** `code/leonardocode/sketch_mar9a/sketch_mar9a.ino`

### Pinout

| Pin | Verbonden met |
|---|---|
| 9 | Gate servo (360° continu) |
| 10 | Tray servo (360° continu) |
| 11 | Wrist servo 1 (180° positioneel) |
| 12 | Wrist servo 2 (180° positioneel) |
| 6 | Vacuum relay (HIGH = aan) |
| 2 | NC switch – gate open eindpositie |
| 3 | NC switch – gate gesloten eindpositie |
| 4 | NC switch – tray buiten eindpositie |
| 5 | NC switch – tray binnen eindpositie |
| A0 | HC-SR04 trigger |
| A1 | HC-SR04 echo |

### Seriële commando's (Pi → Leonardo, 115200 baud)

| Commando | Actie | Respons |
|---|---|---|
| `GATE_OPEN` | Start gate servo richting open | `Gate opening...` → `GATE_OPEN_DONE` + `GATE_POS=UP` |
| `GATE_CLOSE` | Start gate servo richting dicht | `Gate closing...` → `GATE_CLOSE_DONE` + `GATE_POS=DOWN` |
| `TRAY_OUT` | Start tray servo richting buiten | `Tray moving out...` → `TRAY_OUT_DONE` |
| `TRAY_IN` | Start tray servo richting binnen | `Tray moving in...` → `TRAY_IN_DONE` |
| `STOP_ALL` | Alle servo's stoppen | `All stopped` |
| `VACUUM_ON` | Vacuum relay aanzetten | `VACUUM_ON_DONE` |
| `VACUUM_OFF` | Vacuum relay uitzetten | `VACUUM_OFF_DONE` |
| `SERVO1_POS:<hoek>` | Wrist 1 naar absolute hoek (0-180°) | `SERVO1_DONE:<hoek>` |
| `SERVO2_POS:<hoek>` | Wrist 2 naar absolute hoek (0-180°) | `SERVO2_DONE:<hoek>` |
| `DIST_READ` | Afstand meten met HC-SR04 | `DIST=<cm>` (of `-1` als geen echo) |
| `GATE_POS` | Huidige gate positie opvragen | `GATE_POS=UP\|DOWN\|UNKNOWN` |
| `STATUS` | Volledige status opvragen | `gateState=..., gatePos=..., ..., vacuum=0/1, wrist1=90, wrist2=90` |

### State machine logica

De 360° servo's werken met een **non-blocking state machine**:

```
GATE_OPEN commando ontvangen
    → gateState = GATE_OPENING
    → motorGate.write(180)  ← draait continu

In loop():
    if gateState == GATE_OPENING AND gateOpenSwitch == HIGH:
        motorGate.write(90)  ← stop
        gateState = GATE_IDLE
        print("GATE_OPEN_DONE")
```

Zo blokkeert de Arduino nooit — hij blijft tegelijk luisteren naar nieuwe commando's.

### Hoek-mapping wrist servos

De flowchart gebruikt relatieve hoeken (-90°, 0°, +90°). De `write()` functie van de Servo-bibliotheek werkt met absolute waarden 0-180:

| Conceptuele hoek | `write()` waarde |
|---|---|
| -90° | 0 |
| 0° (neutraal/thuis) | 90 |
| +90° | 180 |

---

## 4. Arduino Mega – GRBL CNC

**Bestand:** `code/megacode/grblUpload_copy_20260304140826/grblUpload_copy_20260304140826.ino`

De Mega draait standaard **GRBL** (open-source CNC firmware). GRBL ontvangt G-code commando's via serieel en stuurt de 3 NEMA17 stappenmotoren aan.

### GRBL instellen

1. Open de GRBL sketch in Arduino IDE
2. Zet de GRBL map in je Arduino libraries folder (zie https://github.com/gnea/grbl-Mega)
3. Upload naar Mega
4. Stuur `$` in Serial Monitor (115200 baud) om versie te controleren

### Gehanteerde G-code commando's

| Commando | Betekenis |
|---|---|
| `G90` | Absolute positionering |
| `G1 X50 Y100 F3000` | Beweeg naar X=50, Y=100 aan 3000 mm/min |
| `G1 Z30 F3000` | Z-as omhoog (pickup hoogte) |
| `G1 Z5 F3000` | Z-as omlaag (rij-hoogte) |
| `$H` | Homing sequence |
| `$X` | Alarm unlock |
| `!` | Feed hold (onmiddellijk stoppen) |

### CoreXY uitleg

De X en Y motoren zijn in **CoreXY** configuratie. Beide motoren werken samen voor elke beweging:

- **Alleen X bewegen:** motor A vooruit, motor B achteruit (tegengesteld)
- **Alleen Y bewegen:** motor A en B samen in dezelfde richting
- **Diagonaal (45°):** één motor draait, andere staat stil

GRBL berekent de motorstappen automatisch vanuit de G-code coördinaten.

---

## 5. Raspberry Pi 4 – backend (FastAPI)

**Map:** `code/picode/visionAI/backend/`

### Technologie

- **FastAPI** – REST API + WebSocket server
- **Uvicorn** – ASGI webserver, poort 3000
- **pySerial** – seriële communicatie met beide Arduino's
- **OpenCV** – camera frame capture
- **pyzbar** – barcode/QR decodering voor IMEI-scan

### Opstarten

```bash
cd code/picode/visionAI
make run_backend
# of direct:
backend/venv/bin/uvicorn websrv:app --host 0.0.0.0 --port 3000
```

### API endpoints overzicht

#### Arduino – Leonardo
| Methode | Pad | Omschrijving |
|---|---|---|
| POST | `/api/arduino/leonardo/gate` | Stuur `GATE_OPEN` of `GATE_CLOSE` |
| GET | `/api/arduino/leonardo/gate-position` | Lees gate positie |
| POST | `/api/arduino/leonardo/tray` | Stuur `TRAY_OUT` of `TRAY_IN` |
| GET | `/api/arduino/leonardo/tray-position` | Lees tray positie via STATUS |
| POST | `/api/arduino/leonardo/home` | Tray in + gate dicht |
| POST | `/api/arduino/leonardo/emergency-stop` | `STOP_ALL` sturen |
| GET | `/api/arduino/ports` | Lijst USB poorten + board detectie |

#### Arduino – GRBL (Mega)
| Methode | Pad | Omschrijving |
|---|---|---|
| POST | `/api/arduino/grbl/command` | Willekeurig GRBL commando |
| POST | `/api/arduino/grbl/unlock` | `$X` |
| POST | `/api/arduino/grbl/home` | `$H` |
| POST | `/api/arduino/grbl/stop` | `!` (feed hold) |
| POST | `/api/arduino/grbl/post-flow` | Geconfigureerde post-flow sequence |

#### Camera
| Methode | Pad | Omschrijving |
|---|---|---|
| GET | `/api/camera/stream` | MJPEG live stream |
| GET | `/api/imei/detect` | IMEI barcode detectie op huidig frame |
| POST | `/api/camera/capture` | Sla huidig frame op als JPG |

#### Scan
| Methode | Pad | Omschrijving |
|---|---|---|
| POST | `/api/scan/start` | Start de volledige scansequentie |
| POST | `/api/scan/confirm` | Gebruiker drukt OK (bijv. "toestel geplaatst") |
| GET | `/api/scan/status` | Huidig sessiestatus + stap |
| POST | `/api/scan/abort` | Noodstop + sequentie afbreken |

#### AI & Device
| Methode | Pad | Omschrijving |
|---|---|---|
| POST | `/api/device/lookup` | IMEI → toestelmodel + max waarde |
| POST | `/api/ai/analyze` | Foto's analyseren → schadegraad + bod |

### Services architectuur

```
controller/          ← HTTP route handlers (FastAPI routers)
    arduino.py       ← Seriële commando's doorsturen
    camera.py        ← Camera stream + IMEI + foto capture
    device_lookup.py ← IMEI → toestel lookup
    scan.py          ← Scan sessie starten/stoppen/bevestigen
    ai_damage.py     ← AI analyse endpoint
    notes.py         ← Notities (intern gebruik)

services/            ← Business logica (hardware-niveau)
    machine_service.py    ← Leonardo: gate, tray, vacuum, wrist, afstand
    grbl_service.py       ← Mega: G-code bewegingen, distance-stop
    scan_orchestrator.py  ← De volledige 65-stappen sequentie
    ai_damage_service.py  ← Mock/real AI schadings-analyse

utils/
    socket_utils.py  ← WebSocket connection pool + broadcast
    database_utils.py ← ArangoDB verbinding (voor notities)
```

---

## 6. Raspberry Pi 4 – frontend (Vue 3)

**Map:** `code/picode/visionAI/frontend/`

### Technologie

- **Vue 3** – reactief framework
- **Vuetify 3** – Material Design UI componenten
- **Pinia** – state management
- **Vite** – build tool

### Kiosk mode

In productie wordt de frontend gebuild (`npm run build`) en de `dist/` folder gekopieerd naar de backend. FastAPI serveert hem als een SPA. Bij opstarten van de Pi opent Chromium automatisch in kiosk mode op `http://localhost:3000`.

### Componenten structuur

```
pages/
    index.vue              ← Hoofdcoördinator (kiest welk component te tonen)

components/scan/
    StepWelcome.vue        ← Welkomstscherm + "start" knop
    StepPrepare.vue        ← Hoesje verwijderen + toestel reinigen
    StepImei.vue           ← Camera scan of manuele invoer IMEI
    StepDeviceInfo.vue     ← Toestelmodel + max waarde tonen
    StepPowerOff.vue       ← Instructie: toestel uitschakelen
    StepMachineRunning.vue ← Machine bezig – live voortgang via WebSocket
    StepPhoneReady.vue     ← Schade grade + bod – accepteren/weigeren
    StepThankYou.vue       ← Bedankt + 30s afteller → herstart

store/
    scan.js                ← Pinia store: alle scanstaat (IMEI, model, AI resultaat, UI stap...)
```

### Stap-navigatie

`index.vue` gebruikt één getal (`uiStep`) om te bepalen welk component zichtbaar is:

```
uiStep 0-3   → StepWelcome
uiStep 4-8   → StepPrepare
uiStep 9-13  → StepImei
uiStep 14-16 → StepDeviceInfo
uiStep 17-18 → StepPowerOff
uiStep 19-59 → StepMachineRunning   ← machine draait
uiStep 60-62 → StepPhoneReady
uiStep 63+   → StepThankYou
```

### Pinia scan store

`store/scan.js` bevat alle scandata:

| Veld | Type | Inhoud |
|---|---|---|
| `uiStep` | number | Huidige UI stap (0-65) |
| `imei` | string | Gescand IMEI-nummer |
| `deviceModel` | string | Model naam van het toestel |
| `maxValueEur` | number | Maximale waarde voor dit model |
| `scanStatus` | string | `idle` / `running` / `awaiting_user` / `complete` / `failed` |
| `currentHwStep` | number | Hardware stap die momenteel uitgevoerd wordt |
| `aiResult` | object | Volledig AI analyse resultaat |
| `customerAccepted` | boolean | Of de klant het bod heeft geaccepteerd |
| `errorMessage` | string | Foutbericht bij storing |

---

## 7. De volledige 65-stappen flow

### UI-stappen (door gebruiker bediend, geen hardware)

| Stap | Actie | Hardware |
|---|---|---|
| 1 | Voeding aan / opstarten | – |
| 2 | Welkomstscherm | – |
| 3 | "Wil je een prijsberekening?" | – |
| 4 | Knop: Start | – |
| 5-6 | Screenprotector + hoesje verwijderen | – |
| 7-8 | Toestel proper maken | – |
| 9-10 | Instructie: `*#06#` intoetsen | – |
| 11-13 | Camera opent, IMEI barcode scannen | Camera stream |
| 14 | IMEI → API → model + waarde | HTTP POST /api/device/lookup |
| 15-16 | Max prijs tonen + bevestigen | – |
| 17-18 | Toestel uitschakelen | – |

### Hardware-stappen (automatisch, door ScanOrchestrator)

| Stap | Actie | Arduino |
|---|---|---|
| 19 | Gate omhoog | Leonardo: `GATE_OPEN` |
| 20 | Lade uitschuiven | Leonardo: `TRAY_OUT` |
| 21-22 | **Wacht op gebruiker:** "Toestel geplaatst?" | – |
| 23 | Lade terugschuiven | Leonardo: `TRAY_IN` |
| 24 | Gate omlaag | Leonardo: `GATE_CLOSE` |
| 25 | Arm beweegt langzaam naar voorkant, stopt bij contact | Mega: G1 slow + HC-SR04 |
| 26 | *(stap niet gebruikt in flowchart)* | – |
| 27 | Vacuum aan | Leonardo: `VACUUM_ON` |
| 28 | Arm omhoog (toestel opgepakt) | Mega: `G1 Z30` |
| 29 | Lade naar camera positie | Leonardo: `TRAY_OUT` |
| 30-36 | Wrist rotaties + 3 foto's voorkant | Leonardo: `SERVO1_POS`, `SERVO2_POS` + Camera |
| 37 | Lade terug naar midden | Leonardo: `TRAY_IN` |
| 38 | Wrist naar neutrale positie | Leonardo: `SERVO1_POS:90`, `SERVO2_POS:90` |
| 39 | Arm omlaag (toestel neergelegd) | Mega: `G1 Z5` |
| 40 | Vacuum uit | Leonardo: `VACUUM_OFF` |
| 41 | Arm beweegt naar achterkant (snel) | Mega: `G1 X50 Y20` |
| 42 | Arm nadert langzaam, stopt bij contact | Mega: G1 slow + HC-SR04 |
| 43 | Vacuum aan | Leonardo: `VACUUM_ON` |
| 44 | Arm omhoog | Mega: `G1 Z30` |
| 45-52 | Wrist rotaties + 3 foto's achterkant | Leonardo + Camera |
| 53 | Foto's naar AI → schade score + bod | HTTP POST /api/ai/analyze |
| 54 | Lade terug | Leonardo: `TRAY_IN` |
| 55 | Wrist neutraal | Leonardo: `SERVO1_POS:90`, `SERVO2_POS:90` |
| 56 | Arm omlaag | Mega: `G1 Z5` |
| 57 | Vacuum uit | Leonardo: `VACUUM_OFF` |
| 58 | Gate omhoog | Leonardo: `GATE_OPEN` |
| 59 | Lade uitschuiven | Leonardo: `TRAY_OUT` |

### Afrondingsstappen (UI)

| Stap | Actie |
|---|---|
| 60 | "Toestel kan worden opgehaald" |
| 61 | Schadegraad + bod op scherm |
| 62 | Klant accepteert of weigert |
| 63 | "Bedankt" |
| 64 | 30 seconden wachten of "Start opnieuw" |
| 65 | Terug naar stap 1 |

---

## 8. Scan Orchestrator – hoe werkt de scansequentie

**Bestand:** `backend/services/scan_orchestrator.py`

De ScanOrchestrator is het hart van het systeem. Hij voert alle hardware-stappen sequentieel uit en zorgt voor foutafhandeling en real-time communicatie met de frontend.

### Asyncio architectuur

```python
# Starten van een scan (vanuit controller/scan.py):
session = await orchestrator.start_scan(imei, device_model, max_value_eur)
# → start asyncio.create_task(_run_sequence(session))
```

De sequentie draait als een **achtergrondtaak** in de FastAPI event loop. Dit betekent:

1. De HTTP request die `/api/scan/start` aanroept, keert **onmiddellijk terug** (non-blocking)
2. De sequentie loopt op de achtergrond
3. De frontend krijgt updates via WebSocket

### Blocking calls in async context

De Arduino en GRBL communicatie zijn **blocking** (pySerial). Om de FastAPI event loop niet te blokkeren, worden ze uitgevoerd via `asyncio.to_thread()`:

```python
# Zo doe je het NIET (blokkeert de event loop):
result = machine_service.vacuum_on()

# Zo doe je het WEL (voert uit in threadpool):
result = await asyncio.to_thread(machine_service.vacuum_on)
```

### Gebruikersbevestiging (step 21)

Wanneer de arm klaarstaat en de lade open is, moet de gebruiker het toestel plaatsen en op OK drukken:

```python
# In de sequentie:
await self._await_user(session, 21, "phone_added_check", "Toestel toegevoegd?")
```

Dit:
1. Stuurt een `awaiting_user` WebSocket event → frontend toont de OK knop
2. Wacht op `asyncio.Event.wait()` (timeout: 5 minuten)
3. Wanneer de gebruiker op OK drukt → frontend POST `/api/scan/confirm` → `orchestrator.confirm_user_action()` → `event.set()`
4. Sequentie loopt verder

### Foutafhandeling

Elke stap zit gewikkeld in een `try/except`. Bij een fout:

```python
except Exception as exc:
    session.status = "failed"
    session.error = str(exc)
    await self._broadcast("scan_failed", ...)
    await asyncio.to_thread(self._hw_emergency_stop)
```

De noodstop stuurt:
1. `VACUUM_OFF` naar Leonardo
2. `STOP_ALL` naar Leonardo
3. `!` (feed hold) naar GRBL

### ScanSession dataclass

```python
@dataclass
class ScanSession:
    session_id: str          # UUID4
    imei: str
    device_model: str
    max_value_eur: float
    photo_paths: list[str]   # pad naar elke gemaakte foto
    ai_result: dict          # AI analyse resultaat
    status: str              # running | awaiting_user | complete | failed
    current_step: int        # huidige stap (19-60)
    error: str               # foutbericht bij fout
```

---

## 9. WebSocket communicatie

**Backend:** `backend/utils/socket_utils.py` + `backend/websrv.py`
**Frontend:** `frontend/src/services/websocket.js`

### Hoe broadcasting werkt

De `ConnectionManager.broadcast()` in `socket_utils.py` accepteert een `dict` of een `str`. Een dict wordt automatisch naar JSON geserialiseerd. Berichten worden via `send_text()` als JSON-tekst verstuurd. De frontend parst ze met `JSON.parse()`.

### Event formaat (backend → frontend)

```json
{
    "scan_event": {
        "type": "step_complete",
        "step": 27,
        "step_name": "vacuum_on",
        "data": { "command": "VACUUM_ON", "ack": true }
    }
}
```

De frontend WebSocket service leest de sleutel van het JSON-object (`"scan_event"`) en roept de bijbehorende callback aan.

### Event types

| Type | Wanneer |
|---|---|
| `step_complete` | Een hardware-stap is succesvol afgerond |
| `awaiting_user` | Machine wacht op gebruikersbevestiging (stap 21) |
| `scan_complete` | Volledige sequentie afgerond (stap 60) — `data.ai_result` bevat het analyse-resultaat |
| `scan_failed` | Er is een fout opgetreden — `data.error` bevat de foutmelding |

### Frontend luisteren

```javascript
// In StepMachineRunning.vue (mounted):
webSocketService.onMessage("scan_event", (event) => {
    this.scanStore.handleScanEvent(event);
});

// In beforeUnmount:
webSocketService.offMessage("scan_event");
```

`onMessage()` vervangt een bestaande registratie voor dezelfde sleutel, zodat herbergen van het component nooit dubbele callbacks veroorzaakt.

De Pinia store verwerkt het event en past `scanStatus`, `currentHwStep` en `aiResult` aan. Wanneer `type === "scan_complete"` zet de store `uiStep` automatisch op 60. Vue re-rendert op basis van deze state.

### Gebruiker bevestigen

De OK-knop in `StepMachineRunning.vue` stuurt een HTTP POST:
```javascript
await axios.post("/api/scan/confirm");
```

Alternatief kan ook via WebSocket (beide werken):
```javascript
webSocketService.socket.send(JSON.stringify({ action: "confirm" }));
```

De backend vangt beide op:
```python
# HTTP endpoint /api/scan/confirm:
await orchestrator.confirm_user_action()

# WebSocket handler in websrv.py:
if msg.get("action") == "confirm":
    await orchestrator.confirm_user_action()
```

---

## 10. AI schade-analyse service

**Bestand:** `backend/services/ai_damage_service.py`

### Mock modus (standaard)

Zolang `APP_AI_DAMAGE_API_MOCK=1` (standaard), wordt **geen externe API** aangeroepen. De service genereert een gesimuleerd resultaat:

```python
score = random.uniform(0.0, 0.4)   # meeste toestellen zijn in goede staat
grade = "A" als score < 0.10
grade = "B" als 0.10 ≤ score < 0.25
grade = "C" als 0.25 ≤ score < 0.50
...
final_offer = max_value_eur × (1 - score)
```

### Real modus

Zet `APP_AI_DAMAGE_API_MOCK=0` en configureer `APP_AI_DAMAGE_API_URL`.

De service:
1. Leest alle foto-bestanden
2. Encodeert ze als base64
3. POST naar de externe API:
```json
{
    "imei": "352134981213276",
    "session_id": "uuid4",
    "photos": [
        { "label": "front_side_1", "data": "<base64>" },
        ...
    ]
}
```
4. Verwacht terug: `damage_score`, `grade`, `damage_details`, `final_offer_eur`

### AIDamageResult model

```python
class AIDamageResult(BaseModel):
    imei: str
    session_id: str
    damage_score: float       # 0.0 = perfect, 1.0 = kapot
    grade: str                # "A" t/m "F"
    damage_details: list[str] # bv. ["minor_scratches", "screen_crack"]
    final_offer_eur: float    # bod in euro
    photos_analyzed: int      # aantal foto's geanalyseerd
    mock: bool                # was dit een mock resultaat?
```

---

## 11. IMEI lookup

**Bestand:** `backend/controller/device_lookup.py`
**Data:** `backend/data/device_lookup_test.json`

### Lookup strategie (3 niveaus)

1. **Exact match** – volledige 15-cijferige IMEI
2. **TAC match** – eerste 8 cijfers (Type Allocation Code = fabrikant + model)
3. **Fallback** – "Unknown device", €0

```json
{
    "exact": {
        "490154203237518": { "model": "Apple iPhone 13 128GB", "max_value_eur": 360 }
    },
    "tac": {
        "35391805": { "model": "Samsung Galaxy S21 128GB", "max_value_eur": 300 }
    },
    "fallback": { "model": "Unknown device", "max_value_eur": 0 }
}
```

### Eigen toestellen toevoegen

Voeg toe aan `device_lookup_test.json`:

```json
"exact": {
    "JOUW_15_CIJFER_IMEI": { "model": "Mijn Toestel", "max_value_eur": 150 }
}
```

Of via TAC (first 8 digits van IMEI):
```json
"tac": {
    "35265108": { "model": "iPhone 14 Pro", "max_value_eur": 600 }
}
```

---

## 12. Configuratie (config.env)

**Bestand:** `backend/config/config.env`

### Seriële poorten

```env
APP_LEONARDO_PORT=/dev/ttyACM0   # USB poort Leonardo
APP_LEONARDO_BAUD=115200
APP_GRBL_PORT=/dev/ttyACM1       # USB poort Mega
APP_GRBL_BAUD=115200
```

Gebruik `scripts/detect_ports.sh` om de juiste poorten te vinden.

### Camera

```env
APP_CAMERA_INDEX=0               # 0 = eerste USB camera
APP_PHOTO_STORAGE_DIR=/var/sya_photos
```

### Arm posities (kalibreren!)

```env
APP_GRBL_FEED_RATE=3000          # mm/min snelheid
APP_GRBL_FRONT_X=50.0            # X positie voorkant toestel
APP_GRBL_FRONT_Y=100.0           # Y positie voorkant toestel
APP_GRBL_BACK_X=50.0             # X positie achterkant toestel
APP_GRBL_BACK_Y=20.0             # Y positie achterkant toestel
APP_GRBL_Z_PICKUP=30.0           # Z hoogte om toestel op te pakken
APP_GRBL_Z_TRAVEL=5.0            # Z hoogte voor rijden (laag)
APP_ARM_DISTANCE_THRESHOLD_CM=3  # afstand in cm waarbij arm stopt
```

### Wrist servo's

```env
APP_WRIST_DWELL_MS=600           # wachttijd na servocommando (ms)
```

Verhoog dit als de servo niet op tijd zijn positie bereikt.

### AI analyse

```env
APP_AI_DAMAGE_API_MOCK=1         # 1 = mock (voor testing), 0 = echte API
APP_AI_DAMAGE_API_URL=http://localhost:4000/api/v1/analyze
```

### Timeouts

```env
APP_GATE_MOVE_TIMEOUT_S=10       # max wachttijd gate open/dicht (s)
APP_TRAY_MOVE_TIMEOUT_S=10       # max wachttijd tray in/uit (s)
APP_VACUUM_DWELL_S=1.0           # wachttijd na vacuum aan (s)
APP_LEONARDO_READ_TIMEOUT_S=1.5  # seriële lees timeout Leonardo
APP_GRBL_READ_TIMEOUT_S=1.5      # seriële lees timeout GRBL
```

---

## 13. Installatie op de Raspberry Pi

### Éénmalige setup

```bash
cd ~/sya_ai-scanner/code/picode/visionAI
bash scripts/setup_pi.sh
```

> Het script gaat er van uit dat de repository staat op `~/sya_ai-scanner`. Staat hij ergens anders, pas dan het pad bovenaan het script aan.

Dit script doet:
1. `apt-get install` van alle systeem-afhankelijkheden (libzbar0, nodejs, chromium, ...)
2. Voegt de gebruiker toe aan de `dialout` groep (seriële poort toegang)
3. Maakt `/var/sya_photos` aan
4. Installeert Python virtual environment + packages
5. Bouwt de Vue frontend (`npm run build`)
6. Installeert en activeer een systemd service
7. Configureert Chromium kiosk autostart

**Herstart na de setup** zodat de `dialout` groepswijziging actief wordt.

### Service beheren

```bash
# Starten
sudo systemctl start sya-scanner

# Stoppen
sudo systemctl stop sya-scanner

# Status bekijken
sudo systemctl status sya-scanner

# Live logs volgen
sudo journalctl -u sya-scanner -f

# Automatisch opstarten aan/uitzetten
sudo systemctl enable sya-scanner
sudo systemctl disable sya-scanner
```

### Poorten detecteren

```bash
bash scripts/detect_ports.sh
```

Kopieer de gevonden poorten naar `config.env`:
```env
APP_LEONARDO_PORT=/dev/ttyACM0
APP_GRBL_PORT=/dev/ttyACM1
```

### Frontend herbouwen na wijzigingen

```bash
cd code/picode/visionAI/frontend
npm run build
cp -r dist ../backend/dist
sudo systemctl restart sya-scanner
```

---

## 14. Development starten (laptop)

```bash
cd code/picode/visionAI

# Alles installeren
make install

# Backend + frontend tegelijk starten
make run

# Of apart:
make run_backend    # http://localhost:3000/api
make run_frontend   # http://localhost:5173 (Vite dev server)

# Tests uitvoeren
make install_test
make test

# Code formatteren
make format

# Code controleren
make check
```

De Swagger UI is beschikbaar op `http://localhost:3000/docs` — handig om endpoints manueel te testen zonder hardware.

---

## 15. Kalibratie van de arm

Voordat de machine voor het eerst gebruikt wordt, moeten de GRBL-posities gekalibreerd worden. Dit doe je door de arm manueel te joggern en de coördinaten te noteren.

### Stap 1: GRBL verbinden

```bash
# Installeer een terminal tool als je dat nog niet hebt:
sudo apt install screen    # of: sudo apt install minicom

# Verbind met de Mega (pas poort aan indien nodig):
screen /dev/ttyACM1 115200
# of
minicom -b 115200 -D /dev/ttyACM1
```

### Stap 2: Alarmen resetten

```
$X
```

### Stap 3: Arm manueel joggeren

```
# Stuur kleine stappen:
$J=G91X10F500     # 10mm naar rechts
$J=G91X-10F500    # 10mm naar links
$J=G91Y10F500     # 10mm vooruit
$J=G91Z5F200      # 5mm omhoog
```

### Stap 4: Coördinaten noteren

Joger naar de exacte positie boven de voorkant van het toestel (in lade):
```
?           # huidige positie opvragen → noteert X, Y waarden
```

Joger naar de hoogte waarbij de zuignap het toestel raakt:
```
?           # noteert Z waarde → APP_GRBL_Z_PICKUP
```

Vul alles in in `config.env`.

### Afstandssensor kalibreren

Er is geen aparte HTTP endpoint voor de afstandssensor. Test hem direct via de seriële monitor van de Leonardo:

```bash
# Installeer screen als het nog niet aanwezig is:
sudo apt install screen

# Verbind met de Leonardo (pas poort aan indien nodig):
screen /dev/ttyACM0 115200
```

Typ dan in de terminal:
```
DIST_READ
```

De Leonardo antwoordt met `DIST=<cm>`. Houd je hand of het toestel op de gewenste stopafstand voor de sensor en lees de waarde af. Stel `APP_ARM_DISTANCE_THRESHOLD_CM` in op die waarde (bv. `3`).

---

## 16. Troubleshooting

### "Failed to talk to serial device on /dev/ttyACM0"

1. Check of de Arduino verbonden is: `ls /dev/ttyACM*`
2. Check groep: `groups $USER` → `dialout` moet erin staan. Zo niet: `sudo usermod -aG dialout $USER` + herstart
3. Gebruik `scripts/detect_ports.sh` om de juiste poort te vinden
4. Controleer of de poorten niet verwisseld zijn in `config.env`

### Gate/tray beweegt niet

1. Test via Swagger UI: `POST /api/arduino/leonardo/gate` met `{"command": "GATE_OPEN"}`
2. Check of de NC switches goed aangesloten zijn (pull-up actief, switch verbindt met GND)
3. Controleer servo speed waarden in de Arduino sketch (`GATE_OPEN_SPEED = 180`)

### IMEI barcode wordt niet gelezen

1. Zorg dat het toestel `*#06#` toont
2. Houd het scherm stil voor de camera
3. Probeer de manuele IMEI invoer als fallback
4. Controleer belichting (geen reflecties)

### Arm stopt niet bij het toestel

1. Controleer de HC-SR04 bedrading (trig=A0, echo=A1)
2. Test: `DIST_READ` sturen via serial monitor → moet een realistisch getal teruggeven
3. Verlaag `APP_ARM_DISTANCE_THRESHOLD_CM` indien de sensor te laat reageert
4. Controleer of er niets de sensor blokkeert

### Scan start maar er komen geen WebSocket events

1. Check of de frontend verbonden is: open browser DevTools → Network → WS
2. Controleer `GET /api/scan/status` → toont de huidige sessiestatus
3. Check logs: `sudo journalctl -u sya-scanner -f`

### Foto's worden niet gemaakt

1. Check of `/var/sya_photos` bestaat en schrijfrechten heeft: `ls -la /var/sya_photos`
2. Check `APP_CAMERA_INDEX` – probeer index 1 of 2 als er meerdere camera's zijn
3. Controleer via `GET /api/camera/stream` of de camera werkt

### Scan blijft hangen op "Toestel toegevoegd?"

De orchestrator wacht maximaal 5 minuten (`APP_USER_CONFIRM_TIMEOUT_S=300`) op een gebruikersbevestiging. Als de knop niet reageert:
1. Controleer via `GET /api/scan/status` of `scanStatus === "awaiting_user"`
2. Stuur handmatig `POST /api/scan/confirm` via de Swagger UI
3. Of druk op de Noodstop knop in de UI → `POST /api/scan/abort`

### Scan toont een fout na het starten

1. Controleer of beide Arduino's verbonden zijn vóór het starten van de backend
2. Controleer `config.env` — poorten verwisseld of verkeerde baud rate?
3. Check of een vorige scan de poort nog blokkeerde: `sudo systemctl restart sya-scanner`

---

## 17. Projectstructuur

```
sya_ai-scanner/
├── README.md                          ← Dit bestand
│
├── 3D_files/                          ← STL bestanden voor 3D printen
│   ├── ARM/                           ← Robotarm onderdelen
│   ├── gate/                          ← Gate mechanisme
│   ├── phone-loader/                  ← Lade mechanisme
│   ├── structure/                     ← Hoofdframe
│   └── xy-parts/                      ← CoreXY bewegingssysteem
│
└── code/
    ├── leonardocode/
    │   └── sketch_mar9a/
    │       └── sketch_mar9a.ino       ← Arduino Leonardo firmware
    │
    ├── megacode/
    │   └── grblUpload_.../
    │       └── grblUpload_.ino        ← GRBL upload voor Arduino Mega
    │
    └── picode/
        └── visionAI/
            │
            ├── backend/
            │   ├── websrv.py                    ← FastAPI app + startup
            │   ├── init.py                      ← App initialisatie
            │   ├── requirements.txt
            │   │
            │   ├── config/
            │   │   ├── config.env               ← Alle configuratie variabelen
            │   │   └── init_config.py
            │   │
            │   ├── controller/                  ← HTTP route handlers
            │   │   ├── arduino.py
            │   │   ├── camera.py
            │   │   ├── device_lookup.py
            │   │   ├── scan.py                  ← NIEUW: scan sessie endpoints
            │   │   ├── ai_damage.py             ← NIEUW: AI analyse endpoint
            │   │   └── notes.py
            │   │
            │   ├── services/                    ← Business logica
            │   │   ├── machine_service.py       ← Leonardo: gate/tray/vacuum/wrist
            │   │   ├── grbl_service.py          ← Mega: G-code bewegingen
            │   │   ├── scan_orchestrator.py     ← NIEUW: volledige scansequentie
            │   │   ├── ai_damage_service.py     ← NIEUW: schade-analyse (mock/real)
            │   │   └── notes_services.py
            │   │
            │   ├── utils/
            │   │   ├── socket_utils.py          ← WebSocket connection pool
            │   │   └── database_utils.py        ← ArangoDB (voor notities)
            │   │
            │   ├── data/
            │   │   └── device_lookup_test.json  ← IMEI → toestelmodel database
            │   │
            │   └── tests/                       ← Unit tests
            │
            ├── frontend/
            │   └── src/
            │       ├── pages/
            │       │   └── index.vue            ← Hoofdcoördinator (herschreven)
            │       │
            │       ├── components/
            │       │   └── scan/                ← NIEUW: 8 stap-componenten
            │       │       ├── StepWelcome.vue
            │       │       ├── StepPrepare.vue
            │       │       ├── StepImei.vue
            │       │       ├── StepDeviceInfo.vue
            │       │       ├── StepPowerOff.vue
            │       │       ├── StepMachineRunning.vue
            │       │       ├── StepPhoneReady.vue
            │       │       └── StepThankYou.vue
            │       │
            │       ├── store/
            │       │   ├── scan.js              ← NIEUW: Pinia scan store
            │       │   ├── app.js
            │       │   └── messages.js
            │       │
            │       └── services/
            │           └── websocket.js         ← WebSocket client
            │
            └── scripts/
                ├── setup_pi.sh                  ← NIEUW: éénmalige Pi setup
                └── detect_ports.sh              ← NIEUW: Arduino poorten detecteren
```

---

## GRBL flash instructies (eenmalig)

1. Download GRBL Mega van https://github.com/gnea/grbl-Mega (edge branch, als ZIP)
2. Pak uit → kopieer de `grbl` map naar `~/Documents/Arduino/libraries/`
3. Open `code/megacode/grblUpload_.../grblUpload_.ino` in Arduino IDE
4. Selecteer board: **Arduino Mega 2560**
5. Upload
6. Open Serial Monitor (115200 baud) → typ `$` → moet GRBL versie tonen
