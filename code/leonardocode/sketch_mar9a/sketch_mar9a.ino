#include <Wire.h>
#include <SparkFun_VL53L1X.h>
#include <Servo.h>
#include <string.h>
#include <stdlib.h>

// =========================
// Serial parser
// =========================
const byte CMD_BUFFER_SIZE = 64;
char usbCmdBuffer[CMD_BUFFER_SIZE];
byte usbCmdIndex = 0;
char runtimeCmdBuffer[CMD_BUFFER_SIZE];
byte runtimeCmdIndex = 0;

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

// Wrist 1 uses calibrated reference points on the 270-degree servo:
// - back:   logical 32  -> physical 77
// - rest:   logical 93  -> physical 138
// - front:  logical 152 -> physical 197
const int WRIST1_LOGICAL_MIN_ANGLE = 32;
const int WRIST1_LOGICAL_CENTER_ANGLE = 93;
const int WRIST1_LOGICAL_MAX_ANGLE = 152;
const int WRIST1_LEFT_PHYSICAL_ANGLE = 77;
const int WRIST1_CENTER_PHYSICAL_ANGLE = 138;
const int WRIST1_RIGHT_PHYSICAL_ANGLE = 197;

// Wrist extended range
const int WRIST2_LOGICAL_MIN_ANGLE = -90;
const int WRIST2_LOGICAL_MAX_ANGLE = 90;
const int WRIST2_LEFT_PHYSICAL_ANGLE = -14;
const int WRIST2_CENTER_PHYSICAL_ANGLE = 83;
const int WRIST2_RIGHT_PHYSICAL_ANGLE = 190;

const int WRIST1_LEFT_US = 500;
const int WRIST1_CENTER_US = 1500;
const int WRIST1_RIGHT_US = 2500;
const int WRIST2_LEFT_US = 380;
const int WRIST2_CENTER_US = 1490;
const int WRIST2_RIGHT_US = 2800;
const int WRIST2_DIRECT_MIN_US = 300;
const int WRIST2_DIRECT_MAX_US = 2900;

int wrist1Angle = WRIST1_LOGICAL_CENTER_ANGLE;
int wrist1PhysicalAngle = WRIST1_CENTER_PHYSICAL_ANGLE;
int wrist1CurrentUs = WRIST1_CENTER_US;
int wrist2Angle = 0;
int wrist2PhysicalAngle = WRIST2_CENTER_PHYSICAL_ANGLE;
int wrist2CurrentUs = WRIST2_CENTER_US;

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
void readSerialNonBlocking(Stream &input, Print &output, char *cmdBuffer, byte &cmdIndex);
void processCommand(Print &output, const char *cmd);

void stopGate();
void stopTray();

void setWrist1Angle(int logicalAngle);
void setWrist2Angle(int logicalAngle);
void setWrist2Microseconds(int pulseUs);
int angleToMicroseconds(int angle, int minAngle, int maxAngle, int minUs, int maxUs);
int wrist1LogicalToPhysicalAngle(int logicalAngle);
int wrist1LogicalToMicroseconds(int logicalAngle);
int wrist2LogicalToPhysicalAngle(int logicalAngle);
int wrist2LogicalToMicroseconds(int logicalAngle);
int wrist2MicrosecondsToPhysicalAngle(int pulseUs);
int wrist2MicrosecondsToLogicalAngle(int pulseUs);

void updateGate();
void updateTray();

void updateGatePositionFromSwitches();
void updateTrayPositionFromSwitches();

void initDistanceSensor();
void updateDistanceMeasurement();
void updateDisplayDistance(uint16_t distance, uint8_t rangeStatus);
bool hasValidDistanceMeasurement();
bool hasDisplayDistanceMeasurement();

void printStatus(Print &output);
void printGatePositionValue(Print &output);
void printGatePositionValueInline(Print &output);
void printTrayPositionValue(Print &output);
void printTrayPositionValueInline(Print &output);

// =========================
// Setup
// =========================
void setup() {
  Serial.begin(115200);
  Serial1.begin(115200);
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
  Serial1.println("READY:LEONARDO");
}

// =========================
// Loop
// =========================
void loop() {
  readSerialNonBlocking(Serial1, Serial1, runtimeCmdBuffer, runtimeCmdIndex);
  readSerialNonBlocking(Serial, Serial, usbCmdBuffer, usbCmdIndex);

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
void readSerialNonBlocking(Stream &input, Print &output, char *cmdBuffer, byte &cmdIndex) {
  while (input.available() > 0) {
    char c = input.read();

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      cmdBuffer[cmdIndex] = '\0';

      if (cmdIndex > 0) {
        processCommand(output, cmdBuffer);
      }

      cmdIndex = 0;
      return;
    }

    if (cmdIndex < CMD_BUFFER_SIZE - 1) {
      cmdBuffer[cmdIndex++] = c;
    } else {
      cmdIndex = 0;
      output.println("ERR:BUFFER_OVERFLOW");
      return;
    }
  }
}

// =========================
// Command processor
// Exact 1 antwoord per command
// =========================
void processCommand(Print &output, const char *cmd) {
  if (strcmp(cmd, "GATE_OPEN") == 0) {
    gateState = GATE_OPENING;
    servoGate.write(GATE_OPEN_SPEED);
    output.println("ACK:GATE_OPEN");
  }

  else if (strcmp(cmd, "GATE_CLOSE") == 0) {
    gateState = GATE_CLOSING;
    servoGate.write(GATE_CLOSE_SPEED);
    output.println("ACK:GATE_CLOSE");
  }

  else if (strcmp(cmd, "GATE_STOP") == 0) {
    stopGate();
    gateState = GATE_IDLE;
    updateGatePositionFromSwitches();
    output.println("ACK:GATE_STOP");
  }

  else if (strcmp(cmd, "TRAY_OUT") == 0) {
    trayState = TRAY_OPENING;
    servoPhoneLoader.write(TRAY_OUT_SPEED);
    output.println("ACK:TRAY_OUT");
  }

  else if (strcmp(cmd, "TRAY_IN") == 0) {
    trayState = TRAY_CLOSING;
    servoPhoneLoader.write(TRAY_IN_SPEED);
    output.println("ACK:TRAY_IN");
  }

  else if (strcmp(cmd, "TRAY_STOP") == 0) {
    stopTray();
    trayState = TRAY_IDLE;
    updateTrayPositionFromSwitches();
    output.println("ACK:TRAY_STOP");
  }

  else if (strncmp(cmd, "WRIST1_ANGLE:", 13) == 0) {
    int angle = atoi(cmd + 13);
    setWrist1Angle(angle);
    output.print("ACK:WRIST1_ANGLE=");
    output.println(wrist1Angle);
  }

  else if (strncmp(cmd, "WRIST2_ANGLE:", 13) == 0) {
    int angle = atoi(cmd + 13);
    setWrist2Angle(angle);
    output.print("ACK:WRIST2_ANGLE=");
    output.println(wrist2Angle);
  }

  else if (strncmp(cmd, "WRIST2_US:", 10) == 0) {
    int pulseUs = atoi(cmd + 10);
    setWrist2Microseconds(pulseUs);
    output.print("ACK:WRIST2_US=");
    output.print(wrist2CurrentUs);
    output.print(",LOGICAL=");
    output.print(wrist2Angle);
    output.print(",PHYSICAL=");
    output.println(wrist2PhysicalAngle);
  }

  else if (strcmp(cmd, "WRIST_HOME") == 0) {
    setWrist1Angle(WRIST1_LOGICAL_CENTER_ANGLE);
    setWrist2Angle(0);
    output.println("ACK:WRIST_HOME");
  }

  else if (strcmp(cmd, "WRIST1_LEFT") == 0) {
    setWrist1Angle(WRIST1_LOGICAL_MIN_ANGLE);
    output.println("ACK:WRIST1_LEFT");
  }

  else if (strcmp(cmd, "WRIST1_CENTER") == 0) {
    setWrist1Angle(WRIST1_LOGICAL_CENTER_ANGLE);
    output.println("ACK:WRIST1_CENTER");
  }

  else if (strcmp(cmd, "WRIST1_RIGHT") == 0) {
    setWrist1Angle(WRIST1_LOGICAL_MAX_ANGLE);
    output.println("ACK:WRIST1_RIGHT");
  }

  else if (strcmp(cmd, "WRIST2_LEFT") == 0) {
    setWrist2Angle(-90);
    output.println("ACK:WRIST2_LEFT");
  }

  else if (strcmp(cmd, "WRIST2_CENTER") == 0) {
    setWrist2Angle(0);
    output.println("ACK:WRIST2_CENTER");
  }

  else if (strcmp(cmd, "WRIST2_RIGHT") == 0) {
    setWrist2Angle(90);
    output.println("ACK:WRIST2_RIGHT");
  }

  else if (strcmp(cmd, "VAC1_ON") == 0) {
    digitalWrite(vacuumMotor1Pin, HIGH);
    output.println("ACK:VAC1_ON");
  }

  else if (strcmp(cmd, "VAC1_OFF") == 0) {
    digitalWrite(vacuumMotor1Pin, LOW);
    output.println("ACK:VAC1_OFF");
  }

  else if (strcmp(cmd, "VAC2_ON") == 0) {
    digitalWrite(vacuumMotor2Pin, HIGH);
    output.println("ACK:VAC2_ON");
  }

  else if (strcmp(cmd, "VAC2_OFF") == 0) {
    digitalWrite(vacuumMotor2Pin, LOW);
    output.println("ACK:VAC2_OFF");
  }

  else if (strcmp(cmd, "VAC_ALL_ON") == 0) {
    digitalWrite(vacuumMotor1Pin, HIGH);
    digitalWrite(vacuumMotor2Pin, HIGH);
    output.println("ACK:VAC_ALL_ON");
  }

  else if (strcmp(cmd, "VAC_ALL_OFF") == 0) {
    digitalWrite(vacuumMotor1Pin, LOW);
    digitalWrite(vacuumMotor2Pin, LOW);
    output.println("ACK:VAC_ALL_OFF");
  }

  else if (strcmp(cmd, "VALVE1_ON") == 0) {
    digitalWrite(valve1Pin, HIGH);
    output.println("ACK:VALVE1_ON");
  }

  else if (strcmp(cmd, "VALVE1_OFF") == 0) {
    digitalWrite(valve1Pin, LOW);
    output.println("ACK:VALVE1_OFF");
  }

  else if (strcmp(cmd, "VALVE2_ON") == 0) {
    digitalWrite(valve2Pin, HIGH);
    output.println("ACK:VALVE2_ON");
  }

  else if (strcmp(cmd, "VALVE2_OFF") == 0) {
    digitalWrite(valve2Pin, LOW);
    output.println("ACK:VALVE2_OFF");
  }

  else if (strcmp(cmd, "VALVE_ALL_ON") == 0) {
    digitalWrite(valve1Pin, HIGH);
    digitalWrite(valve2Pin, HIGH);
    output.println("ACK:VALVE_ALL_ON");
  }

  else if (strcmp(cmd, "VALVE_ALL_OFF") == 0) {
    digitalWrite(valve1Pin, LOW);
    digitalWrite(valve2Pin, LOW);
    output.println("ACK:VALVE_ALL_OFF");
  }

  else if (strcmp(cmd, "DISTANCE_MM") == 0) {
    updateDistanceMeasurement();

    output.print("ACK:DISTANCE_MM=");

    if (!distanceSensorOk) {
      output.println("ERROR");
    } else if (lastDistanceMm == 0) {
      output.println("NA");
    } else {
      output.println(lastDistanceMm);
    }
  }

  else if (strcmp(cmd, "DISTANCE_STATUS") == 0) {
    updateDistanceMeasurement();

    output.print("ACK:DISTANCE_STATUS=");

    if (!distanceSensorOk) {
      output.println("ERROR");
    } else {
      output.print("OK,VALID=");
      output.print(hasValidDistanceMeasurement() ? 1 : 0);
      output.print(",DISPLAY_MM=");
      if (hasDisplayDistanceMeasurement()) {
        output.print(lastDisplayDistanceMm);
      } else {
        output.print("NA");
      }
      output.print(",RANGE_STATUS=");
      output.print(lastDistanceRangeStatus);
      output.print(",RAW_MM=");
      output.print(lastRawDistanceMm);
      output.print(",LAST_MM=");
      output.print(lastDistanceMm);
      output.print(",AGE_MS=");

      if (lastDistanceUpdateMs > 0) {
        output.println(millis() - lastDistanceUpdateMs);
      } else {
        output.println("NA");
      }
    }
  }

  else if (strcmp(cmd, "GATE_POS") == 0) {
    output.print("ACK:GATE_POS=");
    printGatePositionValue(output);
  }

  else if (strcmp(cmd, "TRAY_POS") == 0) {
    output.print("ACK:TRAY_POS=");
    printTrayPositionValue(output);
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

    output.println("ACK:STOP_ALL");
  }

  else if (strcmp(cmd, "STATUS") == 0) {
    printStatus(output);
  }

  else {
    output.print("ERR:UNKNOWN_COMMAND=");
    output.println(cmd);
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

int angleToMicroseconds(int angle, int minAngle, int maxAngle, int minUs, int maxUs) {
  angle = constrain(angle, minAngle, maxAngle);
  return map(angle, minAngle, maxAngle, minUs, maxUs);
}

int wrist1LogicalToPhysicalAngle(int logicalAngle) {
  int clampedLogical = constrain(logicalAngle, WRIST1_LOGICAL_MIN_ANGLE, WRIST1_LOGICAL_MAX_ANGLE);
  if (clampedLogical >= WRIST1_LOGICAL_CENTER_ANGLE) {
    return map(
      clampedLogical,
      WRIST1_LOGICAL_CENTER_ANGLE,
      WRIST1_LOGICAL_MAX_ANGLE,
      WRIST1_CENTER_PHYSICAL_ANGLE,
      WRIST1_RIGHT_PHYSICAL_ANGLE
    );
  }
  return map(
    clampedLogical,
    WRIST1_LOGICAL_MIN_ANGLE,
    WRIST1_LOGICAL_CENTER_ANGLE,
    WRIST1_LEFT_PHYSICAL_ANGLE,
    WRIST1_CENTER_PHYSICAL_ANGLE
  );
}

int wrist1LogicalToMicroseconds(int logicalAngle) {
  int clampedLogical = constrain(logicalAngle, WRIST1_LOGICAL_MIN_ANGLE, WRIST1_LOGICAL_MAX_ANGLE);
  if (clampedLogical >= WRIST1_LOGICAL_CENTER_ANGLE) {
    return map(
      clampedLogical,
      WRIST1_LOGICAL_CENTER_ANGLE,
      WRIST1_LOGICAL_MAX_ANGLE,
      WRIST1_CENTER_US,
      WRIST1_RIGHT_US
    );
  }
  return map(
    clampedLogical,
    WRIST1_LOGICAL_MIN_ANGLE,
    WRIST1_LOGICAL_CENTER_ANGLE,
    WRIST1_LEFT_US,
    WRIST1_CENTER_US
  );
}

int wrist2LogicalToPhysicalAngle(int logicalAngle) {
  int clampedLogical = constrain(logicalAngle, WRIST2_LOGICAL_MIN_ANGLE, WRIST2_LOGICAL_MAX_ANGLE);
  if (clampedLogical >= 0) {
    return map(clampedLogical, 0, WRIST2_LOGICAL_MAX_ANGLE, WRIST2_CENTER_PHYSICAL_ANGLE, WRIST2_RIGHT_PHYSICAL_ANGLE);
  }
  return map(clampedLogical, WRIST2_LOGICAL_MIN_ANGLE, 0, WRIST2_LEFT_PHYSICAL_ANGLE, WRIST2_CENTER_PHYSICAL_ANGLE);
}

int wrist2LogicalToMicroseconds(int logicalAngle) {
  int clampedLogical = constrain(logicalAngle, WRIST2_LOGICAL_MIN_ANGLE, WRIST2_LOGICAL_MAX_ANGLE);
  if (clampedLogical >= 0) {
    return map(clampedLogical, 0, WRIST2_LOGICAL_MAX_ANGLE, WRIST2_CENTER_US, WRIST2_RIGHT_US);
  }
  return map(clampedLogical, WRIST2_LOGICAL_MIN_ANGLE, 0, WRIST2_LEFT_US, WRIST2_CENTER_US);
}

int wrist2MicrosecondsToPhysicalAngle(int pulseUs) {
  int clampedUs = constrain(pulseUs, WRIST2_DIRECT_MIN_US, WRIST2_DIRECT_MAX_US);
  if (clampedUs >= WRIST2_CENTER_US) {
    return map(clampedUs, WRIST2_CENTER_US, WRIST2_RIGHT_US, WRIST2_CENTER_PHYSICAL_ANGLE, WRIST2_RIGHT_PHYSICAL_ANGLE);
  }
  return map(clampedUs, WRIST2_LEFT_US, WRIST2_CENTER_US, WRIST2_LEFT_PHYSICAL_ANGLE, WRIST2_CENTER_PHYSICAL_ANGLE);
}

int wrist2MicrosecondsToLogicalAngle(int pulseUs) {
  int clampedUs = constrain(pulseUs, WRIST2_DIRECT_MIN_US, WRIST2_DIRECT_MAX_US);
  if (clampedUs >= WRIST2_CENTER_US) {
    return map(clampedUs, WRIST2_CENTER_US, WRIST2_RIGHT_US, 0, WRIST2_LOGICAL_MAX_ANGLE);
  }
  return map(clampedUs, WRIST2_LEFT_US, WRIST2_CENTER_US, WRIST2_LOGICAL_MIN_ANGLE, 0);
}

void setWrist1Angle(int logicalAngle) {
  wrist1Angle = constrain(logicalAngle, WRIST1_LOGICAL_MIN_ANGLE, WRIST1_LOGICAL_MAX_ANGLE);
  wrist1PhysicalAngle = wrist1LogicalToPhysicalAngle(wrist1Angle);
  wrist1CurrentUs = wrist1LogicalToMicroseconds(wrist1Angle);
  servoWrist1.writeMicroseconds(wrist1CurrentUs);
}

void setWrist2Angle(int logicalAngle) {
  wrist2Angle = constrain(logicalAngle, WRIST2_LOGICAL_MIN_ANGLE, WRIST2_LOGICAL_MAX_ANGLE);
  wrist2PhysicalAngle = wrist2LogicalToPhysicalAngle(wrist2Angle);
  wrist2CurrentUs = wrist2LogicalToMicroseconds(wrist2Angle);
  servoWrist2.writeMicroseconds(wrist2CurrentUs);
}

void setWrist2Microseconds(int pulseUs) {
  wrist2CurrentUs = constrain(pulseUs, WRIST2_DIRECT_MIN_US, WRIST2_DIRECT_MAX_US);
  wrist2PhysicalAngle = wrist2MicrosecondsToPhysicalAngle(wrist2CurrentUs);
  wrist2Angle = wrist2MicrosecondsToLogicalAngle(wrist2CurrentUs);
  servoWrist2.writeMicroseconds(wrist2CurrentUs);
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
void printStatus(Print &output) {
  updateDistanceMeasurement();

  output.print("ACK:STATUS");

  output.print(",gateState=");
  output.print(gateState);

  output.print(",gatePos=");
  printGatePositionValueInline(output);

  output.print(",trayState=");
  output.print(trayState);

  output.print(",trayPos=");
  printTrayPositionValueInline(output);

  output.print(",wrist1=");
  output.print(wrist1Angle);

  output.print(",wrist1_physical=");
  output.print(wrist1PhysicalAngle);

  output.print(",wrist1_us=");
  output.print(wrist1CurrentUs);

  output.print(",wrist2=");
  output.print(wrist2Angle);

  output.print(",wrist2_physical=");
  output.print(wrist2PhysicalAngle);

  output.print(",wrist2_us=");
  output.print(wrist2CurrentUs);

  output.print(",vac1=");
  output.print(digitalRead(vacuumMotor1Pin));

  output.print(",vac2=");
  output.print(digitalRead(vacuumMotor2Pin));

  output.print(",valve1=");
  output.print(digitalRead(valve1Pin));

  output.print(",valve2=");
  output.print(digitalRead(valve2Pin));

  output.print(",distanceOk=");
  output.print(distanceSensorOk ? 1 : 0);

  output.print(",distanceValid=");
  output.print(hasValidDistanceMeasurement() ? 1 : 0);

  output.print(",distanceMm=");
  if (hasDisplayDistanceMeasurement()) {
    output.print(lastDisplayDistanceMm);
  } else if (distanceSensorOk) {
    output.print("NA");
  } else {
    output.print("ERROR");
  }

  output.print(",validDistanceMm=");
  if (hasValidDistanceMeasurement()) {
    output.print(lastDistanceMm);
  } else if (distanceSensorOk) {
    output.print("NA");
  } else {
    output.print("ERROR");
  }

  output.print(",rawDistanceMm=");
  output.print(lastRawDistanceMm);

  output.print(",rangeStatus=");
  output.print(lastDistanceRangeStatus);

  output.print(",distanceAgeMs=");
  if (lastDistanceUpdateMs > 0) {
    output.print(millis() - lastDistanceUpdateMs);
  } else {
    output.print("NA");
  }

  output.print(",gateOpenSw=");
  output.print(digitalRead(gateOpenSwitch));

  output.print(",gateCloseSw=");
  output.print(digitalRead(gateCloseSwitch));

  output.print(",trayOutSw=");
  output.print(digitalRead(trayOutSwitch));

  output.print(",trayInSw=");
  output.println(digitalRead(trayInSwitch));
}

// =========================
// Position output helpers
// =========================
void printGatePositionValue(Print &output) {
  printGatePositionValueInline(output);
  output.println();
}

void printGatePositionValueInline(Print &output) {
  switch (gatePosition) {
    case GATE_UP:
      output.print("UP");
      break;
    case GATE_DOWN:
      output.print("DOWN");
      break;
    default:
      output.print("UNKNOWN");
      break;
  }
}

void printTrayPositionValue(Print &output) {
  printTrayPositionValueInline(output);
  output.println();
}

void printTrayPositionValueInline(Print &output) {
  switch (trayPosition) {
    case TRAY_OUT_POS:
      output.print("OUT");
      break;
    case TRAY_IN_POS:
      output.print("IN");
      break;
    default:
      output.print("UNKNOWN");
      break;
  }
}
