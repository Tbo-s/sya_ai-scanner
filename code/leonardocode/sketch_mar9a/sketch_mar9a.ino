#include <Wire.h>
#include <SparkFun_VL53L1X.h>
#include <Servo.h>
#include <string.h>
#include <stdlib.h>

// =========================
// Serial parser
// =========================
const byte CMD_BUFFER_SIZE = 64;
char cmdBuffer[CMD_BUFFER_SIZE];
byte cmdIndex = 0;

// =========================
// Distance sensor
// =========================
SFEVL53L1X distanceSensor;
bool distanceSensorOk = false;
uint16_t lastDistanceMm = 0;
uint16_t lastRawDistanceMm = 0;
uint16_t lastDisplayDistanceMm = 0;
uint8_t lastDistanceRangeStatus = 255;
unsigned long lastDistanceUpdateMs = 0;

// =========================
// Servo objects
// =========================
Servo servoGate;
Servo servoPhoneLoader;
Servo servoWrist1;
Servo servoWrist2;

// =========================
// Pins
// =========================
const int gateServoPin        = 9;
const int phoneLoaderServoPin = 10;
const int wrist1ServoPin      = 11;
const int wrist2ServoPin      = 12;

const int gateOpenSwitch  = A2;
const int gateCloseSwitch = A3;
const int trayOutSwitch   = 4;
const int trayInSwitch    = 5;

const int vacuumMotor1Pin = 6;
const int vacuumMotor2Pin = A1;
const int valve1Pin       = 8;
const int valve2Pin       = A0;

// =========================
// Servo values
// =========================
const int SERVO_STOP = 90;

const int GATE_OPEN_SPEED  = 180;
const int GATE_CLOSE_SPEED = 0;

const int TRAY_OUT_SPEED = 180;
const int TRAY_IN_SPEED  = 0;

// Wrist extended range
const int WRIST_MIN_ANGLE = -5;
const int WRIST_MAX_ANGLE = 182;

const int WRIST_MIN_US = 500;
const int WRIST_MAX_US = 2500;

int wrist1Angle = 90;
int wrist2Angle = 90;

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
void readSerialNonBlocking();
void processCommand(const char *cmd);

void stopGate();
void stopTray();

void setWrist1Angle(int logicalAngle);
void setWrist2Angle(int logicalAngle);
int angleToMicroseconds(int angle);

void updateGate();
void updateTray();

void updateGatePositionFromSwitches();
void updateTrayPositionFromSwitches();

void initDistanceSensor();
void updateDistanceMeasurement();
void updateDisplayDistance(uint16_t distance, uint8_t rangeStatus);
bool hasValidDistanceMeasurement();
bool hasDisplayDistanceMeasurement();

void printStatus();
void printGatePositionValue();
void printGatePositionValueInline();
void printTrayPositionValue();
void printTrayPositionValueInline();

// =========================
// Setup
// =========================
void setup() {
  Serial.begin(115200);
  Wire.begin();

  servoGate.attach(gateServoPin);
  servoPhoneLoader.attach(phoneLoaderServoPin);
  servoWrist1.attach(wrist1ServoPin);
  servoWrist2.attach(wrist2ServoPin);

  pinMode(gateOpenSwitch, INPUT_PULLUP);
  pinMode(gateCloseSwitch, INPUT_PULLUP);
  pinMode(trayOutSwitch, INPUT_PULLUP);
  pinMode(trayInSwitch, INPUT_PULLUP);

  pinMode(vacuumMotor1Pin, OUTPUT);
  pinMode(vacuumMotor2Pin, OUTPUT);
  pinMode(valve1Pin, OUTPUT);
  pinMode(valve2Pin, OUTPUT);

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

  initDistanceSensor();

  Serial.println("READY:LEONARDO");
}

// =========================
// Loop
// =========================
void loop() {
  readSerialNonBlocking();

  updateGate();
  updateTray();
  updateDistanceMeasurement();

  if (gateState == GATE_IDLE) {
    updateGatePositionFromSwitches();
  }

  if (trayState == TRAY_IDLE) {
    updateTrayPositionFromSwitches();
  }
}

// =========================
// Serial parser zonder String
// =========================
void readSerialNonBlocking() {
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      cmdBuffer[cmdIndex] = '\0';

      if (cmdIndex > 0) {
        processCommand(cmdBuffer);
      }

      cmdIndex = 0;
      return;
    }

    if (cmdIndex < CMD_BUFFER_SIZE - 1) {
      cmdBuffer[cmdIndex++] = c;
    } else {
      cmdIndex = 0;
      Serial.println("ERR:BUFFER_OVERFLOW");
      return;
    }
  }
}

// =========================
// Command processor
// Exact 1 antwoord per command
// =========================
void processCommand(const char *cmd) {
  if (strcmp(cmd, "GATE_OPEN") == 0) {
    gateState = GATE_OPENING;
    servoGate.write(GATE_OPEN_SPEED);
    Serial.println("ACK:GATE_OPEN");
  }

  else if (strcmp(cmd, "GATE_CLOSE") == 0) {
    gateState = GATE_CLOSING;
    servoGate.write(GATE_CLOSE_SPEED);
    Serial.println("ACK:GATE_CLOSE");
  }

  else if (strcmp(cmd, "GATE_STOP") == 0) {
    stopGate();
    gateState = GATE_IDLE;
    updateGatePositionFromSwitches();
    Serial.println("ACK:GATE_STOP");
  }

  else if (strcmp(cmd, "TRAY_OUT") == 0) {
    trayState = TRAY_OPENING;
    servoPhoneLoader.write(TRAY_OUT_SPEED);
    Serial.println("ACK:TRAY_OUT");
  }

  else if (strcmp(cmd, "TRAY_IN") == 0) {
    trayState = TRAY_CLOSING;
    servoPhoneLoader.write(TRAY_IN_SPEED);
    Serial.println("ACK:TRAY_IN");
  }

  else if (strcmp(cmd, "TRAY_STOP") == 0) {
    stopTray();
    trayState = TRAY_IDLE;
    updateTrayPositionFromSwitches();
    Serial.println("ACK:TRAY_STOP");
  }

  else if (strncmp(cmd, "WRIST1_ANGLE:", 13) == 0) {
    int angle = atoi(cmd + 13);
    setWrist1Angle(angle);
    Serial.print("ACK:WRIST1_ANGLE=");
    Serial.println(wrist1Angle);
  }

  else if (strncmp(cmd, "WRIST2_ANGLE:", 13) == 0) {
    int angle = atoi(cmd + 13);
    setWrist2Angle(angle);
    Serial.print("ACK:WRIST2_ANGLE=");
    Serial.println(wrist2Angle);
  }

  else if (strcmp(cmd, "WRIST_HOME") == 0) {
    setWrist1Angle(90);
    setWrist2Angle(90);
    Serial.println("ACK:WRIST_HOME");
  }

  else if (strcmp(cmd, "WRIST1_LEFT") == 0) {
    setWrist1Angle(-5);
    Serial.println("ACK:WRIST1_LEFT");
  }

  else if (strcmp(cmd, "WRIST1_CENTER") == 0) {
    setWrist1Angle(90);
    Serial.println("ACK:WRIST1_CENTER");
  }

  else if (strcmp(cmd, "WRIST1_RIGHT") == 0) {
    setWrist1Angle(182);
    Serial.println("ACK:WRIST1_RIGHT");
  }

  else if (strcmp(cmd, "WRIST2_LEFT") == 0) {
    setWrist2Angle(-5);
    Serial.println("ACK:WRIST2_LEFT");
  }

  else if (strcmp(cmd, "WRIST2_CENTER") == 0) {
    setWrist2Angle(90);
    Serial.println("ACK:WRIST2_CENTER");
  }

  else if (strcmp(cmd, "WRIST2_RIGHT") == 0) {
    setWrist2Angle(182);
    Serial.println("ACK:WRIST2_RIGHT");
  }

  else if (strcmp(cmd, "VAC1_ON") == 0) {
    digitalWrite(vacuumMotor1Pin, HIGH);
    Serial.println("ACK:VAC1_ON");
  }

  else if (strcmp(cmd, "VAC1_OFF") == 0) {
    digitalWrite(vacuumMotor1Pin, LOW);
    Serial.println("ACK:VAC1_OFF");
  }

  else if (strcmp(cmd, "VAC2_ON") == 0) {
    digitalWrite(vacuumMotor2Pin, HIGH);
    Serial.println("ACK:VAC2_ON");
  }

  else if (strcmp(cmd, "VAC2_OFF") == 0) {
    digitalWrite(vacuumMotor2Pin, LOW);
    Serial.println("ACK:VAC2_OFF");
  }

  else if (strcmp(cmd, "VAC_ALL_ON") == 0) {
    digitalWrite(vacuumMotor1Pin, HIGH);
    digitalWrite(vacuumMotor2Pin, HIGH);
    Serial.println("ACK:VAC_ALL_ON");
  }

  else if (strcmp(cmd, "VAC_ALL_OFF") == 0) {
    digitalWrite(vacuumMotor1Pin, LOW);
    digitalWrite(vacuumMotor2Pin, LOW);
    Serial.println("ACK:VAC_ALL_OFF");
  }

  else if (strcmp(cmd, "VALVE1_ON") == 0) {
    digitalWrite(valve1Pin, HIGH);
    Serial.println("ACK:VALVE1_ON");
  }

  else if (strcmp(cmd, "VALVE1_OFF") == 0) {
    digitalWrite(valve1Pin, LOW);
    Serial.println("ACK:VALVE1_OFF");
  }

  else if (strcmp(cmd, "VALVE2_ON") == 0) {
    digitalWrite(valve2Pin, HIGH);
    Serial.println("ACK:VALVE2_ON");
  }

  else if (strcmp(cmd, "VALVE2_OFF") == 0) {
    digitalWrite(valve2Pin, LOW);
    Serial.println("ACK:VALVE2_OFF");
  }

  else if (strcmp(cmd, "VALVE_ALL_ON") == 0) {
    digitalWrite(valve1Pin, HIGH);
    digitalWrite(valve2Pin, HIGH);
    Serial.println("ACK:VALVE_ALL_ON");
  }

  else if (strcmp(cmd, "VALVE_ALL_OFF") == 0) {
    digitalWrite(valve1Pin, LOW);
    digitalWrite(valve2Pin, LOW);
    Serial.println("ACK:VALVE_ALL_OFF");
  }

  else if (strcmp(cmd, "DISTANCE_MM") == 0) {
    updateDistanceMeasurement();

    Serial.print("ACK:DISTANCE_MM=");

    if (!distanceSensorOk) {
      Serial.println("ERROR");
    } else if (lastDistanceMm == 0) {
      Serial.println("NA");
    } else {
      Serial.println(lastDistanceMm);
    }
  }

  else if (strcmp(cmd, "DISTANCE_STATUS") == 0) {
    updateDistanceMeasurement();

    Serial.print("ACK:DISTANCE_STATUS=");

    if (!distanceSensorOk) {
      Serial.println("ERROR");
    } else {
      Serial.print("OK,VALID=");
      Serial.print(hasValidDistanceMeasurement() ? 1 : 0);
      Serial.print(",DISPLAY_MM=");
      if (hasDisplayDistanceMeasurement()) {
        Serial.print(lastDisplayDistanceMm);
      } else {
        Serial.print("NA");
      }
      Serial.print(",RANGE_STATUS=");
      Serial.print(lastDistanceRangeStatus);
      Serial.print(",RAW_MM=");
      Serial.print(lastRawDistanceMm);
      Serial.print(",LAST_MM=");
      Serial.print(lastDistanceMm);
      Serial.print(",AGE_MS=");

      if (lastDistanceUpdateMs > 0) {
        Serial.println(millis() - lastDistanceUpdateMs);
      } else {
        Serial.println("NA");
      }
    }
  }

  else if (strcmp(cmd, "GATE_POS") == 0) {
    Serial.print("ACK:GATE_POS=");
    printGatePositionValue();
  }

  else if (strcmp(cmd, "TRAY_POS") == 0) {
    Serial.print("ACK:TRAY_POS=");
    printTrayPositionValue();
  }

  else if (strcmp(cmd, "STOP_ALL") == 0) {
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

    Serial.println("ACK:STOP_ALL");
  }

  else if (strcmp(cmd, "STATUS") == 0) {
    printStatus();
  }

  else {
    Serial.print("ERR:UNKNOWN_COMMAND=");
    Serial.println(cmd);
  }
}

// =========================
// Distance sensor
// =========================
void initDistanceSensor() {
  int initStatus = distanceSensor.init();
  distanceSensorOk = (initStatus == 0);

  if (!distanceSensorOk) {
    lastDistanceRangeStatus = 255;
    return;
  }

  distanceSensor.setDistanceModeLong();
  distanceSensor.setTimingBudgetInMs(100);
  distanceSensor.setIntermeasurementPeriod(200);
  distanceSensor.startRanging();

  unsigned long started = millis();

  while (millis() - started < 500) {
    if (distanceSensor.checkForDataReady()) {
      uint8_t rangeStatus = distanceSensor.getRangeStatus();
      uint16_t distance = distanceSensor.getDistance();
      distanceSensor.clearInterrupt();

      lastRawDistanceMm = distance;
      lastDistanceRangeStatus = rangeStatus;
      updateDisplayDistance(distance, rangeStatus);

      if (rangeStatus == 0 && distance > 0) {
        lastDistanceMm = distance;
        lastDistanceUpdateMs = millis();
      }

      break;
    }

    delay(5);
  }
}

void updateDistanceMeasurement() {
  if (!distanceSensorOk) return;
  if (!distanceSensor.checkForDataReady()) return;

  uint8_t rangeStatus = distanceSensor.getRangeStatus();
  uint16_t distance = distanceSensor.getDistance();
  distanceSensor.clearInterrupt();

  lastRawDistanceMm = distance;
  lastDistanceRangeStatus = rangeStatus;
  updateDisplayDistance(distance, rangeStatus);

  if (rangeStatus == 0 && distance > 0) {
    lastDistanceMm = distance;
    lastDistanceUpdateMs = millis();
  }
}

void updateDisplayDistance(uint16_t distance, uint8_t rangeStatus) {
  if (rangeStatus == 0 && distance > 0) {
    lastDisplayDistanceMm = distance;
    return;
  }

  if (distance > 0) {
    lastDisplayDistanceMm = distance;
  }
}

bool hasValidDistanceMeasurement() {
  return distanceSensorOk && lastDistanceMm > 0 && lastDistanceRangeStatus == 0;
}

bool hasDisplayDistanceMeasurement() {
  return distanceSensorOk && lastDisplayDistanceMm > 0;
}

// =========================
// Gate update logic
// Geen Serial prints hier
// =========================
void updateGate() {
  switch (gateState) {
    case GATE_OPENING:
      if (digitalRead(gateOpenSwitch) == HIGH) {
        stopGate();
        gateState = GATE_IDLE;
        gatePosition = GATE_UP;
      }
      break;

    case GATE_CLOSING:
      if (digitalRead(gateCloseSwitch) == HIGH) {
        stopGate();
        gateState = GATE_IDLE;
        gatePosition = GATE_DOWN;
      }
      break;

    case GATE_IDLE:
      break;
  }
}

// =========================
// Tray update logic
// Geen Serial prints hier
// =========================
void updateTray() {
  switch (trayState) {
    case TRAY_OPENING:
      if (digitalRead(trayOutSwitch) == HIGH) {
        stopTray();
        trayState = TRAY_IDLE;
        trayPosition = TRAY_OUT_POS;
      }
      break;

    case TRAY_CLOSING:
      if (digitalRead(trayInSwitch) == HIGH) {
        stopTray();
        trayState = TRAY_IDLE;
        trayPosition = TRAY_IN_POS;
      }
      break;

    case TRAY_IDLE:
      break;
  }
}

// =========================
// Servo helpers
// =========================
void stopGate() {
  servoGate.write(SERVO_STOP);
}

void stopTray() {
  servoPhoneLoader.write(SERVO_STOP);
}

int angleToMicroseconds(int angle) {
  angle = constrain(angle, WRIST_MIN_ANGLE, WRIST_MAX_ANGLE);
  return map(angle, WRIST_MIN_ANGLE, WRIST_MAX_ANGLE, WRIST_MIN_US, WRIST_MAX_US);
}

void setWrist1Angle(int logicalAngle) {
  wrist1Angle = constrain(logicalAngle, WRIST_MIN_ANGLE, WRIST_MAX_ANGLE);
  servoWrist1.writeMicroseconds(angleToMicroseconds(wrist1Angle));
}

void setWrist2Angle(int logicalAngle) {
  wrist2Angle = constrain(logicalAngle, WRIST_MIN_ANGLE, WRIST_MAX_ANGLE);
  servoWrist2.writeMicroseconds(angleToMicroseconds(wrist2Angle));
}

// =========================
// Position tracking
// =========================
void updateGatePositionFromSwitches() {
  bool openPressed  = digitalRead(gateOpenSwitch) == HIGH;
  bool closePressed = digitalRead(gateCloseSwitch) == HIGH;

  if (openPressed && !closePressed) {
    gatePosition = GATE_UP;
  } else if (!openPressed && closePressed) {
    gatePosition = GATE_DOWN;
  } else if (openPressed && closePressed) {
    gatePosition = GATE_UNKNOWN_POS;
  }
}

void updateTrayPositionFromSwitches() {
  bool outPressed = digitalRead(trayOutSwitch) == HIGH;
  bool inPressed  = digitalRead(trayInSwitch) == HIGH;

  if (outPressed && !inPressed) {
    trayPosition = TRAY_OUT_POS;
  } else if (!outPressed && inPressed) {
    trayPosition = TRAY_IN_POS;
  } else if (outPressed && inPressed) {
    trayPosition = TRAY_UNKNOWN_POS;
  }
}

// =========================
// Status output
// =========================
void printStatus() {
  updateDistanceMeasurement();

  Serial.print("ACK:STATUS");

  Serial.print(",gateState=");
  Serial.print(gateState);

  Serial.print(",gatePos=");
  printGatePositionValueInline();

  Serial.print(",trayState=");
  Serial.print(trayState);

  Serial.print(",trayPos=");
  printTrayPositionValueInline();

  Serial.print(",wrist1=");
  Serial.print(wrist1Angle);

  Serial.print(",wrist2=");
  Serial.print(wrist2Angle);

  Serial.print(",vac1=");
  Serial.print(digitalRead(vacuumMotor1Pin));

  Serial.print(",vac2=");
  Serial.print(digitalRead(vacuumMotor2Pin));

  Serial.print(",valve1=");
  Serial.print(digitalRead(valve1Pin));

  Serial.print(",valve2=");
  Serial.print(digitalRead(valve2Pin));

  Serial.print(",distanceOk=");
  Serial.print(distanceSensorOk ? 1 : 0);

  Serial.print(",distanceValid=");
  Serial.print(hasValidDistanceMeasurement() ? 1 : 0);

  Serial.print(",distanceMm=");
  if (hasDisplayDistanceMeasurement()) {
    Serial.print(lastDisplayDistanceMm);
  } else if (distanceSensorOk) {
    Serial.print("NA");
  } else {
    Serial.print("ERROR");
  }

  Serial.print(",validDistanceMm=");
  if (hasValidDistanceMeasurement()) {
    Serial.print(lastDistanceMm);
  } else if (distanceSensorOk) {
    Serial.print("NA");
  } else {
    Serial.print("ERROR");
  }

  Serial.print(",rawDistanceMm=");
  Serial.print(lastRawDistanceMm);

  Serial.print(",rangeStatus=");
  Serial.print(lastDistanceRangeStatus);

  Serial.print(",distanceAgeMs=");
  if (lastDistanceUpdateMs > 0) {
    Serial.print(millis() - lastDistanceUpdateMs);
  } else {
    Serial.print("NA");
  }

  Serial.print(",gateOpenSw=");
  Serial.print(digitalRead(gateOpenSwitch));

  Serial.print(",gateCloseSw=");
  Serial.print(digitalRead(gateCloseSwitch));

  Serial.print(",trayOutSw=");
  Serial.print(digitalRead(trayOutSwitch));

  Serial.print(",trayInSw=");
  Serial.println(digitalRead(trayInSwitch));
}

// =========================
// Position output helpers
// =========================
void printGatePositionValue() {
  printGatePositionValueInline();
  Serial.println();
}

void printGatePositionValueInline() {
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
}

void printTrayPositionValue() {
  printTrayPositionValueInline();
  Serial.println();
}

void printTrayPositionValueInline() {
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
}
