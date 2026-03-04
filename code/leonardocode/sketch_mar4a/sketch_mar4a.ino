   #include <Servo.h>

   Servo motor;
   const int MOTOR_PIN = 9;

   // Tune these for your specific servo
   const int STOP_US   = 1500;
   const int RUN_US    = 1700;  // increase for more speed, decrease if too fast

   void setup() {
     Serial.begin(9600);
     motor.attach(MOTOR_PIN);
     motor.writeMicroseconds(STOP_US);  // start stopped
   }

   void loop() {
     if (Serial.available()) {
       char c = Serial.read();
       if (c == '1') {
         motor.writeMicroseconds(RUN_US);   // run while camera is on
       } else if (c == '0') {
         motor.writeMicroseconds(STOP_US);  // stop when camera is off
       }
     }
   }
