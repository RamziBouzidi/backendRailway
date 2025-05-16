#include <Wire.h>

const int fanPin = 9; // PWM-capable pin on Uno
volatile bool device_on = false;
volatile uint8_t wind_speed = 0;

void receiveEvent(int howMany) {
  if (howMany >= 2) {
    device_on = Wire.read();
    wind_speed = Wire.read();
    analogWrite(fanPin, device_on ? wind_speed : 0);
  }
}

void setup() {
  pinMode(fanPin, OUTPUT);
  analogWrite(fanPin, 0);
  Wire.begin(0x12); // I2C slave address
  Wire.onReceive(receiveEvent);
}

void loop() {
  // Nothing needed here, all handled in receiveEvent
}
