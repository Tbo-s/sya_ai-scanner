#include <Servo.h>

Servo motorGate;
Servo motorTray;

// Servo pins
const int gateServoPin = 9;
const int trayServoPin = 10;

// Switches
const int gateOpenSwitch   = 2;  // C->GND, NC->pin
const int gateCloseSwitch  = 3;
const int trayOutSwitch    = 4;
const int trayInSwitch     = 5;

// Continuous servo values
const int SERVO_STOP = 90;

// Kalibreer deze waarden indien nodig
const int GATE_OPEN_SPEED  = 180;
const int GATE_CLOSE_SPEED = 0;

const int TRAY_OUT_SPEED   = 180;
const int TRAY_IN_SPEED    = 0;

// State machine
enum GateState {
  GATE_IDLE,
  GATE_OPENING,
  GATE_CLOSING
};

enum TrayState {
  TRAY_IDLE,
  TRAY_OPENING,
  TRAY_CLOSING
};

enum GatePosition {
  GATE_UNKNOWN_POS,
  GATE_UP,
  GATE_DOWN
};

GateState gateState = GATE_IDLE;
TrayState trayState = TRAY_IDLE;
GatePosition gatePosition = GATE_UNKNOWN_POS;

void setup() {
  Serial.begin(115200);

  motorGate.attach(gateServoPin);
  motorTray.attach(trayServoPin);

  pinMode(gateOpenSwitch, INPUT_PULLUP);
  pinMode(gateCloseSwitch, INPUT_PULLUP);
  pinMode(trayOutSwitch, INPUT_PULLUP);
  pinMode(trayInSwitch, INPUT_PULLUP);

  stopGate();
  stopTray();

  // Bepaal gate-positie bij opstart
  updateGatePositionFromSwitches();

  Serial.println("Leonardo ready");
  printGatePosition();
}

void loop() {
  handleSerial();
  updateGate();
  updateTray();

  // Hou positie up-to-date als gate stilstaat
  if (gateState == GATE_IDLE) {
    updateGatePositionFromSwitches();
  }
}

void handleSerial() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

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
  else if (cmd == "STOP_ALL") {
    stopGate();
    stopTray();
    gateState = GATE_IDLE;
    trayState = TRAY_IDLE;
    updateGatePositionFromSwitches();
    Serial.println("All stopped");
  }
  else if (cmd == "STATUS") {
    printStatus();
  }
  else if (cmd == "GATE_POS") {
    printGatePosition();
  }
}

void updateGate() {
  switch (gateState) {
    case GATE_OPENING:
      if (digitalRead(gateOpenSwitch) == HIGH) {   // switch geraakt
        stopGate();
        gateState = GATE_IDLE;
        gatePosition = GATE_UP;
        Serial.println("GATE_OPEN_DONE");
        printGatePosition();
      }
      break;

    case GATE_CLOSING:
      if (digitalRead(gateCloseSwitch) == HIGH) {
        stopGate();
        gateState = GATE_IDLE;
        gatePosition = GATE_DOWN;
        Serial.println("GATE_CLOSE_DONE");
        printGatePosition();
      }
      break;

    case GATE_IDLE:
      break;
  }
}

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

void stopGate() {
  motorGate.write(SERVO_STOP);
}

void stopTray() {
  motorTray.write(SERVO_STOP);
}

void updateGatePositionFromSwitches() {
  bool openPressed  = (digitalRead(gateOpenSwitch) == HIGH);
  bool closePressed = (digitalRead(gateCloseSwitch) == HIGH);

  if (openPressed && !closePressed) {
    gatePosition = GATE_UP;
  }
  else if (!openPressed && closePressed) {
    gatePosition = GATE_DOWN;
  }
  else if (!openPressed && !closePressed) {
    // geen switch geraakt -> tussenpositie of onbekend
    // laat laatste bekende positie staan
  }
  else {
    // beide switches tegelijk geraakt = fout / mechanisch probleem
    gatePosition = GATE_UNKNOWN_POS;
  }
}

void printGatePosition() {
  Serial.print("GATE_POS=");

  switch (gatePosition) {
    case GATE_UP:
      Serial.println("UP");
      break;
    case GATE_DOWN:
      Serial.println("DOWN");
      break;
    default:
      Serial.println("UNKNOWN");
      break;
  }
}

void printStatus() {
  Serial.print("gateState=");
  Serial.print(gateState);

  Serial.print(", gatePos=");
  switch (gatePosition) {
    case GATE_UP:
      Serial.print("UP");
      break;
    case GATE_DOWN:
      Serial.print("DOWN");
      break;
    default:
      Serial.print("UNKNOWN");
      break;
  }

  Serial.print(", trayState=");
  Serial.print(trayState);

  Serial.print(", gateOpenSw=");
  Serial.print(digitalRead(gateOpenSwitch));

  Serial.print(", gateCloseSw=");
  Serial.print(digitalRead(gateCloseSwitch));

  Serial.print(", trayOutSw=");
  Serial.print(digitalRead(trayOutSwitch));

  Serial.print(", trayInSw=");
  Serial.println(digitalRead(trayInSwitch));
}