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

GateState gateState = GATE_IDLE;
TrayState trayState = TRAY_IDLE;

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

  Serial.println("Leonardo ready");
}

void loop() {
  handleSerial();
  updateGate();
  updateTray();
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
    Serial.println("All stopped");
  }
  else if (cmd == "STATUS") {
    printStatus();
  }
}

void updateGate() {
  switch (gateState) {
    case GATE_OPENING:
      if (digitalRead(gateOpenSwitch) == HIGH) {   // switch geraakt
        stopGate();
        gateState = GATE_IDLE;
        Serial.println("GATE_OPEN_DONE");
      }
      break;

    case GATE_CLOSING:
      if (digitalRead(gateCloseSwitch) == HIGH) {
        stopGate();
        gateState = GATE_IDLE;
        Serial.println("GATE_CLOSE_DONE");
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

void printStatus() {
  Serial.print("gateState=");
  Serial.print(gateState);
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