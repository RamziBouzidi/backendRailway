#include <Arduino.h>
#include <Wire.h>
#include "HX711.h"
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <Update.h>

// WiFi and WebSocket config
const char* ssid = "Iphone";
const char* password = "ramzi15011";
const char* ws_host = "backendrailway-production-35ad.up.railway.app";
const uint16_t ws_port = 8000;
const char* ws_path = "/ws/microcontroller";

// I2C config
#define FAN_I2C_ADDR 0x12  // Arduino Uno I2C address

// HX711 pins
const int LOADCELL_DOUT_PIN_1 = 16;
const int LOADCELL_SCK_PIN_1 = 4;
const int LOADCELL_DOUT_PIN_2 = 5;
const int LOADCELL_SCK_PIN_2 = 17;
HX711 scale1, scale2;

WebSocketsClient webSocket;
bool device_on = false;
int wind_speed = 0;

void sendSettingsToFan() {
  Wire.beginTransmission(FAN_I2C_ADDR);
  Wire.write((uint8_t)device_on); // 1 byte: device_on (0 or 1)
  Wire.write((uint8_t)wind_speed); // 1 byte: wind_speed (0-255)
  Wire.endTransmission();
}

void sendForceDataWS(long drag, long down) {
  DynamicJsonDocument doc(256);
  doc["type"] = "force_data";
  doc["drag_force"] = drag;
  doc["down_force"] = down;
  String json;
  serializeJson(doc, json);
  webSocket.sendTXT(json);
  Serial.print("[WS] Sent drag_force: "); Serial.print(drag);
  Serial.print(", down_force: "); Serial.println(down);
}

void handleOtaUpdate(const String& otaUrl) {
  if (otaUrl.length() > 0) {
    HTTPClient http;
    http.begin(otaUrl);
    int httpCode = http.GET();
    if (httpCode == HTTP_CODE_OK) {
      int contentLength = http.getSize();
      WiFiClient * stream = http.getStreamPtr();
      if (!Update.begin(contentLength)) {
        Serial.println("Not enough space for OTA");
        http.end();
        webSocket.sendTXT("{\"type\":\"ota_ack\",\"status\":\"failed\"}");
        return;
      }
      size_t written = Update.writeStream(*stream);
      if (written == contentLength) {
        Serial.println("OTA written successfully");
      } else {
        Serial.println("OTA written only partial");
      }
      if (Update.end()) {
        if (Update.isFinished()) {
          Serial.println("OTA update finished. Rebooting...");
          webSocket.sendTXT("{\"type\":\"ota_ack\",\"status\":\"success\"}");
          delay(1000);
          ESP.restart();
        } else {
          Serial.println("OTA update not finished");
          webSocket.sendTXT("{\"type\":\"ota_ack\",\"status\":\"failed\"}");
        }
      } else {
        Serial.print("OTA update error: ");
        Serial.println(Update.getError());
        webSocket.sendTXT("{\"type\":\"ota_ack\",\"status\":\"failed\"}");
      }
    } else {
      Serial.print("HTTP GET failed, code: "); Serial.println(httpCode);
      webSocket.sendTXT("{\"type\":\"ota_ack\",\"status\":\"failed\"}");
    }
    http.end();
  }
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  if (type == WStype_TEXT) {
    DynamicJsonDocument doc(256);
    DeserializationError err = deserializeJson(doc, payload, length);
    if (err) return;
    if (!doc.containsKey("type")) return;
    String msgType = doc["type"].as<String>();
    if (msgType == "settings_update") {
      if (doc.containsKey("device_on")) device_on = doc["device_on"];
      if (doc.containsKey("wind_speed")) wind_speed = doc["wind_speed"];
      sendSettingsToFan();
    } else if (msgType == "updateMicro") {
      if (doc.containsKey("ota_url")) {
        String otaUrl = doc["ota_url"].as<String>();
        Serial.print("OTA update requested! URL: "); Serial.println(otaUrl);
        handleOtaUpdate(otaUrl);
      }
    }
  }
}

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  scale1.begin(LOADCELL_DOUT_PIN_1, LOADCELL_SCK_PIN_1);
  scale2.begin(LOADCELL_DOUT_PIN_2, LOADCELL_SCK_PIN_2);
  Wire.begin(); // I2C master
  webSocket.begin(ws_host, ws_port, ws_path);
  webSocket.onEvent(webSocketEvent);
}

unsigned long lastSend = 0;
const unsigned long sendInterval = 500; // ms

void loop() {
  webSocket.loop();
  unsigned long now = millis();
  if (now - lastSend > sendInterval) {
    long drag = scale1.is_ready() ? scale1.read() : 0;
    long down = scale2.is_ready() ? scale2.read() : 0;
    sendForceDataWS(drag, down);
    lastSend = now;
  }
}
