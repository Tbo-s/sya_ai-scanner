#include <Servo.h>

// ── Continuous 360° servos ──────────────────────────────────────────────────
Servo motorGate;
Servo motorTray;

// ── 180° positional wrist servos ────────────────────────────────────────────
Servo wrist1;
Servo wrist2;

// ── Servo pins ───────────────────────────────────────────────────────────────
const int gateServoPin  = 9;
const int trayServoPin  = 10;
const int wrist1Pin     = 11;
const int wrist2Pin     = 12;

// ── NC end-stop switches ─────────────────────────────────────────────────────
const int gateOpenSwitch  = 2;   // C->GND, NC->pin  (HIGH = switch triggered)
const int gateCloseSwitch = 3;
const int trayOutSwitch   = 4;
const int trayInSwitch    = 5;

// ── Vacuum relay ─────────────────────────────────────────────────────────────
const int vacuumPin = 6;         // HIGH = vacuum ON

// ── HC-SR04 distance sensor ───────────────────────────────────────────────────
const int distTrigPin = A0;
const int distEchoPin = A1;

// ── Continuous servo stop value ───────────────────────────────────────────────
const int SERVO_STOP = 90;

// Kalibreer deze waarden indien nodig
const int GATE_OPEN_SPEED  = 180;
const int GATE_CLOSE_SPEED = 0;
const int TRAY_OUT_SPEED   = 180;
const int TRAY_IN_SPEED    = 0;

// ── State machines ────────────────────────────────────────────────────────────
enum GateState  { GATE_IDLE, GATE_OPENING, GATE_CLOSING };
enum TrayState  { TRAY_IDLE, TRAY_OPENING, TRAY_CLOSING };
enum GatePosition { GATE_UNKNOWN_POS, GATE_UP, GATE_DOWN };

GateState    gateState    = GATE_IDLE;
TrayState    trayState    = TRAY_IDLE;
GatePosition gatePosition = GATE_UNKNOWN_POS;

bool   vacuumOn   = false;
int    wrist1Pos  = 90;
int    wrist2Pos  = 90;

// ─────────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  motorGate.attach(gateServoPin);
  motorTray.attach(trayServoPin);
  wrist1.attach(wrist1Pin);
  wrist2.attach(wrist2Pin);

  pinMode(gateOpenSwitch,  INPUT_PULLUP);
  pinMode(gateCloseSwitch, INPUT_PULLUP);
  pinMode(trayOutSwitch,   INPUT_PULLUP);
  pinMode(trayInSwitch,    INPUT_PULLUP);

  pinMode(vacuumPin, OUTPUT);
  digitalWrite(vacuumPin, LOW);

  pinMode(distTrigPin, OUTPUT);
  pinMode(distEchoPin, INPUT);

  stopGate();
  stopTray();
  wrist1.write(wrist1Pos);
  wrist2.write(wrist2Pos);

  updateGatePositionFromSwitches();

  Serial.println("Leonardo ready");
  printGatePosition();
}

// ─────────────────────────────────────────────────────────────────────────────
void loop() {
  handleSerial();
  updateGate();
  updateTray();

  if (gateState == GATE_IDLE) {
    updateGatePositionFromSwitches();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
void handleSerial() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

  // ── Gate ──────────────────────────────────────────────────────────────────
  if (cmd == "GATE_OPEN") {
    gateState = GATE_OPENING;
    motorGate.write(GATE_OPEN_SPEED);
    Serial.println("Gate opening...");
  }
  else if (cmd == "GATE_CLOSE") {
    gateState = GATE_CLOSING;
    motorGate.write(GATE_CLOSE_SPEED);
    Serial.println("Gate closing...");
  }

  // ── Tray ──────────────────────────────────────────────────────────────────
  else if (cmd == "TRAY_OUT") {
    trayState = TRAY_OPENING;
    motorTray.write(TRAY_OUT_SPEED);
    Serial.println("Tray moving out...");
  }
  else if (cmd == "TRAY_IN") {
    trayState = TRAY_CLOSING;
    motorTray.write(TRAY_IN_SPEED);
    Serial.println("Tray moving in...");
  }

  // ── Stop all ──────────────────────────────────────────────────────────────
  else if (cmd == "STOP_ALL") {
    stopGate();
    stopTray();
    gateState = GATE_IDLE;
    trayState = TRAY_IDLE;
    updateGatePositionFromSwitches();
    Serial.println("All stopped");
  }

  // ── Vacuum ────────────────────────────────────────────────────────────────
  else if (cmd == "VACUUM_ON") {
    digitalWrite(vacuumPin, HIGH);
    vacuumOn = true;
    Serial.println("VACUUM_ON_DONE");
  }
  else if (cmd == "VACUUM_OFF") {
    digitalWrite(vacuumPin, LOW);
    vacuumOn = false;
    Serial.println("VACUUM_OFF_DONE");
  }

  // ── Wrist servo 1 (180° positional) ──────────────────────────────────────
  else if (cmd.startsWith("SERVO1_POS:")) {
    int angle = cmd.substring(11).toInt();
    angle = constrain(angle, 0, 180);
    wrist1.write(angle);
    wrist1Pos = angle;
    Serial.print("SERVO1_DONE:");
    Serial.println(angle);
  }

  // ── Wrist servo 2 (180° positional) ──────────────────────────────────────
  else if (cmd.startsWith("SERVO2_POS:")) {
    int angle = cmd.substring(11).toInt();
    angle = constrain(angle, 0, 180);
    wrist2.write(angle);
    wrist2Pos = angle;
    Serial.print("SERVO2_DONE:");
    Serial.println(angle);
  }

  // ── Distance sensor ───────────────────────────────────────────────────────
  else if (cmd == "DIST_READ") {
    long dist = readDistanceCm();
    Serial.print("DIST=");
    Serial.println(dist);
  }

  // ── Status / position queries ─────────────────────────────────────────────
  else if (cmd == "STATUS") {
    printStatus();
  }
  else if (cmd == "GATE_POS") {
    printGatePosition();
  }
  else {
    Serial.print("ERROR:unknown_command:");
    Serial.println(cmd);
  }
}

// ── HC-SR04 distance measurement ─────────────────────────────────────────────
long readDistanceCm() {
  digitalWrite(distTrigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(distTrigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(distTrigPin, LOW);
  long duration = pulseIn(distEchoPin, HIGH, 30000UL);  // 30 ms timeout
  if (duration == 0) return -1;                          // no echo → -1
  return duration * 17L / 1000L;                        // µs → cm  (≈ 0.034/2)
}

// ── Gate state machine ────────────────────────────────────────────────────────
void updateGate() {
  switch (gateState) {
    case GATE_OPENING:
      if (digitalRead(gateOpenSwitch) == HIGH) {
        stopGate();
        gateState    = GATE_IDLE;
        gatePosition = GATE_UP;
        Serial.println("GATE_OPEN_DONE");
        printGatePosition();
      }
      break;

    case GATE_CLOSING:
      if (digitalRead(gateCloseSwitch) == HIGH) {
        stopGate();
        gateState    = GATE_IDLE;
        gatePosition = GATE_DOWN;
        Serial.println("GATE_CLOSE_DONE");
        printGatePosition();
      }
      break;

    case GATE_IDLE:
      break;
  }
}

// ── Tray state machine ────────────────────────────────────────────────────────
void updateTray() {
  switch (trayState) {
    case TRAY_OPENING:
      if (digitalRead(trayOutSwitch) == HIGH) {
        stopTray();
        trayState = TRAY_IDLE;
        Serial.println("TRAY_OUT_DONE");
      }
      break;

    case TRAY_CLOSING:
      if (digitalRead(trayInSwitch) == HIGH) {
        stopTray();
        trayState = TRAY_IDLE;
        Serial.println("TRAY_IN_DONE");
      }
      break;

    case TRAY_IDLE:
      break;
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
void stopGate() { motorGate.write(SERVO_STOP); }
void stopTray()  { motorTray.write(SERVO_STOP); }

void updateGatePositionFromSwitches() {
  bool openPressed  = (digitalRead(gateOpenSwitch)  == HIGH);
  bool closePressed = (digitalRead(gateCloseSwitch) == HIGH);

  if (openPressed && !closePressed)       gatePosition = GATE_UP;
  else if (!openPressed && closePressed)  gatePosition = GATE_DOWN;
  else if (openPressed && closePressed)   gatePosition = GATE_UNKNOWN_POS;
  // neither → keep last known position
}

void printGatePosition() {
  Serial.print("GATE_POS=");
  switch (gatePosition) {
    case GATE_UP:      Serial.println("UP");      break;
    case GATE_DOWN:    Serial.println("DOWN");    break;
    default:           Serial.println("UNKNOWN"); break;
  }
}

void printStatus() {
  Serial.print("gateState=");  Serial.print(gateState);
  Serial.print(", gatePos=");
  switch (gatePosition) {
    case GATE_UP:   Serial.print("UP");      break;
    case GATE_DOWN: Serial.print("DOWN");    break;
    default:        Serial.print("UNKNOWN"); break;
  }
  Serial.print(", trayState=");    Serial.print(trayState);
  Serial.print(", gateOpenSw=");   Serial.print(digitalRead(gateOpenSwitch));
  Serial.print(", gateCloseSw=");  Serial.print(digitalRead(gateCloseSwitch));
  Serial.print(", trayOutSw=");    Serial.print(digitalRead(trayOutSwitch));
  Serial.print(", trayInSw=");     Serial.print(digitalRead(trayInSwitch));
  Serial.print(", vacuum=");       Serial.print(vacuumOn ? 1 : 0);
  Serial.print(", wrist1=");       Serial.print(wrist1Pos);
  Serial.print(", wrist2=");       Serial.println(wrist2Pos);
}