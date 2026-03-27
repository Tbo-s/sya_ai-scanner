#include <Servo.h>

// =========================
// Servo objects
// =========================
Servo servoGate;        // 360 continuous
Servo servoPhoneLoader; // 360 continuous
Servo servoWrist1;      // 180 degree
Servo servoWrist2;      // 180 degree

// =========================
// Servo pins
// =========================
const int gateServoPin        = 9;
const int phoneLoaderServoPin = 10;
const int wrist1ServoPin      = 11;
const int wrist2ServoPin      = 12;

// =========================
// Switches (NC -> INPUT_PULLUP)
// C -> GND, NC -> pin
// geraakt = HIGH
// =========================
const int gateOpenSwitch  = 2;
const int gateCloseSwitch = 3;
const int trayOutSwitch   = 4;
const int trayInSwitch    = 5;

// =========================
// MOSFET output pins
// =========================
const int vacuumMotor1Pin = 6;
const int vacuumMotor2Pin = A1;
const int valve1Pin       = 8;
const int valve2Pin       = A0;

// =========================
// Continuous servo values
// =========================
const int SERVO_STOP = 90;

// Kalibreer indien nodig
const int GATE_OPEN_SPEED   = 180;
const int GATE_CLOSE_SPEED  = 0;

const int TRAY_OUT_SPEED    = 180;
const int TRAY_IN_SPEED     = 0;

// =========================
// Wrist calibration
// =========================
// Jij gaf aan:
// logisch 180 -> fysiek 175
// logisch 90  -> fysiek 85
// logisch 0   -> fysiek -5 (dus softwarematig clamp naar 0)
//
// Dus offset = -5
const int WRIST1_OFFSET = -5;
const int WRIST2_OFFSET = -5;

// Logische vaste posities
const int WRIST_LEFT_ANGLE   = 0;
const int WRIST_CENTER_ANGLE = 90;
const int WRIST_RIGHT_ANGLE  = 180;

// =========================
// Wrist defaults (logische hoeken)
// =========================
int wrist1Angle = WRIST_CENTER_ANGLE;
int wrist2Angle = WRIST_CENTER_ANGLE;

// =========================
// States
// =========================
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

enum TrayPosition {
  TRAY_UNKNOWN_POS,
  TRAY_OUT_POS,
  TRAY_IN_POS
};

GateState gateState = GATE_IDLE;
TrayState trayState = TRAY_IDLE;
GatePosition gatePosition = GATE_UNKNOWN_POS;
TrayPosition trayPosition = TRAY_UNKNOWN_POS;

// =========================
// Forward declarations
// =========================
void stopGate();
void stopTray();
void updateGatePositionFromSwitches();
void updateTrayPositionFromSwitches();
void printGatePosition();
void printTrayPosition();
void printStatus();

void setWrist1Angle(int logicalAngle);
void setWrist2Angle(int logicalAngle);

// =========================
// Setup
// =========================
void setup() {
  Serial.begin(115200);

  // Attach servos
  servoGate.attach(gateServoPin);
  servoPhoneLoader.attach(phoneLoaderServoPin);
  servoWrist1.attach(wrist1ServoPin);
  servoWrist2.attach(wrist2ServoPin);

  // Switches
  pinMode(gateOpenSwitch, INPUT_PULLUP);
  pinMode(gateCloseSwitch, INPUT_PULLUP);
  pinMode(trayOutSwitch, INPUT_PULLUP);
  pinMode(trayInSwitch, INPUT_PULLUP);

  // MOSFET outputs
  pinMode(vacuumMotor1Pin, OUTPUT);
  pinMode(vacuumMotor2Pin, OUTPUT);
  pinMode(valve1Pin, OUTPUT);
  pinMode(valve2Pin, OUTPUT);

  // Safe startup states
  stopGate();
  stopTray();

  setWrist1Angle(wrist1Angle);
  setWrist2Angle(wrist2Angle);

  digitalWrite(vacuumMotor1Pin, LOW);
  digitalWrite(vacuumMotor2Pin, LOW);
  digitalWrite(valve1Pin, LOW);
  digitalWrite(valve2Pin, LOW);

  updateGatePositionFromSwitches();
  updateTrayPositionFromSwitches();

  Serial.println("Leonardo ready");
  printStatus();
}

// =========================
// Main loop
// =========================
void loop() {
  handleSerial();
  updateGate();
  updateTray();

  if (gateState == GATE_IDLE) {
    updateGatePositionFromSwitches();
  }

  if (trayState == TRAY_IDLE) {
    updateTrayPositionFromSwitches();
  }
}

// =========================
// Serial command handling
// =========================
void handleSerial() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

  // -------------------------
  // Gate commands
  // -------------------------
  if (cmd == "GATE_OPEN") {
    gateState = GATE_OPENING;
    servoGate.write(GATE_OPEN_SPEED);
    Serial.println("GATE_OPENING");
  }
  else if (cmd == "GATE_CLOSE") {
    gateState = GATE_CLOSING;
    servoGate.write(GATE_CLOSE_SPEED);
    Serial.println("GATE_CLOSING");
  }
  else if (cmd == "GATE_STOP") {
    stopGate();
    gateState = GATE_IDLE;
    updateGatePositionFromSwitches();
    Serial.println("GATE_STOPPED");
  }
  else if (cmd == "GATE_POS") {
    printGatePosition();
  }

  // -------------------------
  // Tray / phone loader commands
  // -------------------------
  else if (cmd == "TRAY_OUT") {
    trayState = TRAY_OPENING;
    servoPhoneLoader.write(TRAY_OUT_SPEED);
    Serial.println("TRAY_MOVING_OUT");
  }
  else if (cmd == "TRAY_IN") {
    trayState = TRAY_CLOSING;
    servoPhoneLoader.write(TRAY_IN_SPEED);
    Serial.println("TRAY_MOVING_IN");
  }
  else if (cmd == "TRAY_STOP") {
    stopTray();
    trayState = TRAY_IDLE;
    updateTrayPositionFromSwitches();
    Serial.println("TRAY_STOPPED");
  }

  // -------------------------
  // Wrist commands
  // -------------------------
  else if (cmd.startsWith("WRIST1_ANGLE:")) {
    int angle = cmd.substring(String("WRIST1_ANGLE:").length()).toInt();
    setWrist1Angle(angle);
    Serial.print("WRIST1_DONE:");
    Serial.println(wrist1Angle);
  }
  else if (cmd.startsWith("WRIST2_ANGLE:")) {
    int angle = cmd.substring(String("WRIST2_ANGLE:").length()).toInt();
    setWrist2Angle(angle);
    Serial.print("WRIST2_DONE:");
    Serial.println(wrist2Angle);
  }
  else if (cmd == "WRIST_HOME") {
    setWrist1Angle(WRIST_CENTER_ANGLE);
    setWrist2Angle(WRIST_CENTER_ANGLE);
    Serial.println("WRIST_HOME_DONE");
  }

  // Handige vaste posities
  else if (cmd == "WRIST1_LEFT") {
    setWrist1Angle(WRIST_LEFT_ANGLE);
    Serial.println("WRIST1_LEFT_DONE");
  }
  else if (cmd == "WRIST1_CENTER") {
    setWrist1Angle(WRIST_CENTER_ANGLE);
    Serial.println("WRIST1_CENTER_DONE");
  }
  else if (cmd == "WRIST1_RIGHT") {
    setWrist1Angle(WRIST_RIGHT_ANGLE);
    Serial.println("WRIST1_RIGHT_DONE");
  }
  else if (cmd == "WRIST2_LEFT") {
    setWrist2Angle(WRIST_LEFT_ANGLE);
    Serial.println("WRIST2_LEFT_DONE");
  }
  else if (cmd == "WRIST2_CENTER") {
    setWrist2Angle(WRIST_CENTER_ANGLE);
    Serial.println("WRIST2_CENTER_DONE");
  }
  else if (cmd == "WRIST2_RIGHT") {
    setWrist2Angle(WRIST_RIGHT_ANGLE);
    Serial.println("WRIST2_RIGHT_DONE");
  }

  // -------------------------
  // Vacuum motor commands
  // -------------------------
  else if (cmd == "VAC1_ON") {
    digitalWrite(vacuumMotor1Pin, HIGH);
    Serial.println("VAC1_ON_DONE");
  }
  else if (cmd == "VAC1_OFF") {
    digitalWrite(vacuumMotor1Pin, LOW);
    Serial.println("VAC1_OFF_DONE");
  }
  else if (cmd == "VAC2_ON") {
    digitalWrite(vacuumMotor2Pin, HIGH);
    Serial.println("VAC2_ON_DONE");
  }
  else if (cmd == "VAC2_OFF") {
    digitalWrite(vacuumMotor2Pin, LOW);
    Serial.println("VAC2_OFF_DONE");
  }
  else if (cmd == "VAC_ALL_ON") {
    digitalWrite(vacuumMotor1Pin, HIGH);
    digitalWrite(vacuumMotor2Pin, HIGH);
    Serial.println("VAC_ALL_ON_DONE");
  }
  else if (cmd == "VAC_ALL_OFF") {
    digitalWrite(vacuumMotor1Pin, LOW);
    digitalWrite(vacuumMotor2Pin, LOW);
    Serial.println("VAC_ALL_OFF_DONE");
  }

  // -------------------------
  // Valve commands
  // -------------------------
  else if (cmd == "VALVE1_ON") {
    digitalWrite(valve1Pin, HIGH);
    Serial.println("VALVE1_ON_DONE");
  }
  else if (cmd == "VALVE1_OFF") {
    digitalWrite(valve1Pin, LOW);
    Serial.println("VALVE1_OFF_DONE");
  }
  else if (cmd == "VALVE2_ON") {
    digitalWrite(valve2Pin, HIGH);
    Serial.println("VALVE2_ON_DONE");
  }
  else if (cmd == "VALVE2_OFF") {
    digitalWrite(valve2Pin, LOW);
    Serial.println("VALVE2_OFF_DONE");
  }
  else if (cmd == "VALVE_ALL_ON") {
    digitalWrite(valve1Pin, HIGH);
    digitalWrite(valve2Pin, HIGH);
    Serial.println("VALVE_ALL_ON_DONE");
  }
  else if (cmd == "VALVE_ALL_OFF") {
    digitalWrite(valve1Pin, LOW);
    digitalWrite(valve2Pin, LOW);
    Serial.println("VALVE_ALL_OFF_DONE");
  }

  // -------------------------
  // Global
  // -------------------------
  else if (cmd == "STOP_ALL") {
    stopGate();
    stopTray();

    gateState = GATE_IDLE;
    trayState = TRAY_IDLE;

    digitalWrite(vacuumMotor1Pin, LOW);
    digitalWrite(vacuumMotor2Pin, LOW);
    digitalWrite(valve1Pin, LOW);
    digitalWrite(valve2Pin, LOW);

    updateGatePositionFromSwitches();
    updateTrayPositionFromSwitches();

    Serial.println("ALL_STOPPED");
  }
  else if (cmd == "STATUS") {
    printStatus();
  }
  else {
    Serial.print("ERROR:UNKNOWN_COMMAND:");
    Serial.println(cmd);
  }
}

// =========================
// Gate update logic
// =========================
void updateGate() {
  switch (gateState) {
    case GATE_OPENING:
      if (digitalRead(gateOpenSwitch) == HIGH) {
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

// =========================
// Tray update logic
// =========================
void updateTray() {
  switch (trayState) {
    case TRAY_OPENING:
      if (digitalRead(trayOutSwitch) == HIGH) {
        stopTray();
        trayState = TRAY_IDLE;
        trayPosition = TRAY_OUT_POS;
        Serial.println("TRAY_OUT_DONE");
        printTrayPosition();
      }
      break;

    case TRAY_CLOSING:
      if (digitalRead(trayInSwitch) == HIGH) {
        stopTray();
        trayState = TRAY_IDLE;
        trayPosition = TRAY_IN_POS;
        Serial.println("TRAY_IN_DONE");
        printTrayPosition();
      }
      break;

    case TRAY_IDLE:
      break;
  }
}

// =========================
// Servo helper functions
// =========================
void stopGate() {
  servoGate.write(SERVO_STOP);
}

void stopTray() {
  servoPhoneLoader.write(SERVO_STOP);
}

void setWrist1Angle(int logicalAngle) {
  wrist1Angle = constrain(logicalAngle, 0, 180);
  int physicalAngle = constrain(wrist1Angle + WRIST1_OFFSET, 0, 180);
  servoWrist1.write(physicalAngle);
}

void setWrist2Angle(int logicalAngle) {
  wrist2Angle = constrain(logicalAngle, 0, 180);
  int physicalAngle = constrain(wrist2Angle + WRIST2_OFFSET, 0, 180);
  servoWrist2.write(physicalAngle);
}

// =========================
// Position tracking
// =========================
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
    // tussenpositie of onbekend, laat laatste gekende waarde staan
  }
  else {
    gatePosition = GATE_UNKNOWN_POS;
  }
}

void updateTrayPositionFromSwitches() {
  bool outPressed = (digitalRead(trayOutSwitch) == HIGH);
  bool inPressed  = (digitalRead(trayInSwitch) == HIGH);

  if (outPressed && !inPressed) {
    trayPosition = TRAY_OUT_POS;
  }
  else if (!outPressed && inPressed) {
    trayPosition = TRAY_IN_POS;
  }
  else if (!outPressed && !inPressed) {
    // tussenpositie of onbekend, laat laatste gekende waarde staan
  }
  else {
    trayPosition = TRAY_UNKNOWN_POS;
  }
}

// =========================
// Serial status printers
// =========================
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

void printTrayPosition() {
  Serial.print("TRAY_POS=");
  switch (trayPosition) {
    case TRAY_OUT_POS:
      Serial.println("OUT");
      break;
    case TRAY_IN_POS:
      Serial.println("IN");
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

  Serial.print(", trayPos=");
  switch (trayPosition) {
    case TRAY_OUT_POS:
      Serial.print("OUT");
      break;
    case TRAY_IN_POS:
      Serial.print("IN");
      break;
    default:
      Serial.print("UNKNOWN");
      break;
  }

  Serial.print(", wrist1_logical=");
  Serial.print(wrist1Angle);
  Serial.print(", wrist1_physical=");
  Serial.print(constrain(wrist1Angle + WRIST1_OFFSET, 0, 180));

  Serial.print(", wrist2_logical=");
  Serial.print(wrist2Angle);
  Serial.print(", wrist2_physical=");
  Serial.print(constrain(wrist2Angle + WRIST2_OFFSET, 0, 180));

  Serial.print(", vac1=");
  Serial.print(digitalRead(vacuumMotor1Pin));

  Serial.print(", vac2=");
  Serial.print(digitalRead(vacuumMotor2Pin));

  Serial.print(", valve1=");
  Serial.print(digitalRead(valve1Pin));

  Serial.print(", valve2=");
  Serial.print(digitalRead(valve2Pin));

  Serial.print(", gateOpenSw=");
  Serial.print(digitalRead(gateOpenSwitch));

  Serial.print(", gateCloseSw=");
  Serial.print(digitalRead(gateCloseSwitch));

  Serial.print(", trayOutSw=");
  Serial.print(digitalRead(trayOutSwitch));

  Serial.print(", trayInSw=");
  Serial.println(digitalRead(trayInSwitch));
}