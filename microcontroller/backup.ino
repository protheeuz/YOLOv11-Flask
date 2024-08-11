#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <MAX30105.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <LiquidCrystal_I2C.h>
#include "spo2_algorithm.h"
#include "esp_task_wdt.h"
#include <Ticker.h>

// WiFi Credentials
const char *ssid = "MathtechStudio";
const char *password = "Bellaciao13";

// Create instances for sensors
Adafruit_MPU6050 mpu;
MAX30105 particleSensor;
OneWire oneWire(18);  // DS18B20 data pin
DallasTemperature sensors(&oneWire);
LiquidCrystal_I2C lcd(0x27, 20, 4);  // I2C address 0x27 for 20x4 LCD

// Define pins
const int AD8232_OUTPUT = 32;
const int LO_MINUS = 34;
const int LO_PLUS = 35;

// Variables to hold sensor readings
float temperature;
uint32_t heartRate;
uint32_t spo2;
float activity_level;
int ecg_value;
int user_id = -1;  // Default invalid user_id

// Custom characters for LCD
byte heart[8] = {
  0b00000,
  0b01010,
  0b11111,
  0b11111,
  0b11111,
  0b01110,
  0b00100,
  0b00000
};

byte oxygen[8] = {
  0b00000,
  0b00100,
  0b01110,
  0b10101,
  0b10101,
  0b01110,
  0b00100,
  0b00000
};

byte temp[8] = {
  0b00100,
  0b01010,
  0b01010,
  0b01010,
  0b01010,
  0b11111,
  0b11111,
  0b01110
};

byte activity[8] = {
  0b00000,
  0b00100,
  0b01110,
  0b11111,
  0b01110,
  0b00100,
  0b00000,
  0b00000
};

byte ecg[8] = {
  0b00000,
  0b01010,
  0b11111,
  0b01110,
  0b01110,
  0b11111,
  0b01010,
  0b00000
};

// I2C Multiplexer Function
void tcaSelect(uint8_t i) {
  if (i > 7) return;
  Wire.beginTransmission(0x70);
  Wire.write(1 << i);
  Wire.endTransmission();
}

// WiFi and Server setup
AsyncWebServer server(80);
Ticker ecgTicker;
bool ecgCollecting = false;
unsigned long startMillis;
unsigned long endMillis;
const int sampleInterval = 100;    // 100ms
const int sampleDuration = 15000;  // 15 seconds
std::vector<int> ecgData;

void setup() {
  Serial.begin(115200);

  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Menghubungkan ke WiFi...");
  }
  Serial.println("Terhubung ke WiFi");
  Serial.print("IP Address ESP32: ");
  Serial.println(WiFi.localIP());

  // Initialize I2C
  Wire.begin();

  // Initialize MPU6050
  tcaSelect(1);
  if (!mpu.begin(0x68)) {
    Serial.println("Tidak dapat menemukan sensor MPU6050 di channel 1!");
    while (1)
      ;
  }
  Serial.println("MPU6050 berhasil diinisialisasi di channel 1!");

  // Initialize MAX30105
  tcaSelect(4);
  if (!particleSensor.begin()) {
    Serial.println("Tidak dapat menemukan sensor MAX30105 di channel 4!");
    while (1)
      ;
  }
  particleSensor.setup();
  particleSensor.setPulseAmplitudeRed(0x0A);  // Turn on RED LED
  particleSensor.setPulseAmplitudeGreen(0);   // Turn off GREEN LED
  Serial.println("MAX30105 berhasil diinisialisasi di channel 4!");

  // Initialize DS18B20
  sensors.begin();
  Serial.println("DS18B20 berhasil diinisialisasi!");

  // Initialize AD8232
  pinMode(AD8232_OUTPUT, INPUT);
  pinMode(LO_MINUS, INPUT);
  pinMode(LO_PLUS, INPUT);

  // Initialize LCD
  tcaSelect(0);
  lcd.init();
  lcd.backlight();

  // Buat karakter khusus
  lcd.createChar(0, heart);
  lcd.createChar(1, oxygen);
  lcd.createChar(2, temp);
  lcd.createChar(3, activity);
  lcd.createChar(4, ecg);

  lcd.setCursor(0, 0);
  lcd.print(" PT. Prima Feedmill");

  // HTTP server routes
  server.on(
    "/set_user_id", HTTP_POST, [](AsyncWebServerRequest *request) {}, NULL, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
      Serial.print("Received data: ");
      Serial.write(data, len);
      Serial.println();

      DynamicJsonDocument doc(200);
      DeserializationError error = deserializeJson(doc, data);

      if (error) {
        Serial.print("deserializeJson() failed: ");
        Serial.println(error.c_str());
        request->send(400, "application/json", "{\"status\":\"gagal\", \"message\":\"Deserialization error\"}");
        return;
      }

      if (!doc.containsKey("user_id")) {
        Serial.println("No user_id key in JSON");
        request->send(400, "application/json", "{\"status\":\"gagal\", \"message\":\"No user_id key in JSON\"}");
        return;
      }

      user_id = doc["user_id"];
      Serial.print("User ID set to: ");
      Serial.println(user_id);
      request->send(200, "application/json", "{\"status\":\"sukses\"}");
    });

  server.on("/get_sensor_data/heart_rate", HTTP_GET, [](AsyncWebServerRequest *request) {
    tcaSelect(4);
    uint32_t irBuffer[100];
    uint32_t redBuffer[100];
    int bufferLength = 100;
    for (int i = 0; i < bufferLength; i++) {
      while (particleSensor.available() == false)
        particleSensor.check();
      redBuffer[i] = particleSensor.getRed();
      irBuffer[i] = particleSensor.getIR();
      particleSensor.nextSample();
      esp_task_wdt_reset();  // Reset watchdog timer
    }
    int8_t validSPO2;
    int8_t validHeartRate;
    maxim_heart_rate_and_oxygen_saturation(irBuffer, bufferLength, redBuffer, (int32_t *)&spo2, &validSPO2, (int32_t *)&heartRate, &validHeartRate);
    if (!validHeartRate) {
      request->send(500, "application/json", "{\"status\":\"gagal\", \"message\":\"Invalid heart rate data\"}");
      return;
    }
    String jsonResponse = "{\"status\":\"sukses\",\"value\":" + String(heartRate) + "}";
    request->send(200, "application/json", jsonResponse);
  });

  server.on("/get_sensor_data/oxygen_level", HTTP_GET, [](AsyncWebServerRequest *request) {
    tcaSelect(4);
    uint32_t irBuffer[100];
    uint32_t redBuffer[100];
    int bufferLength = 100;
    for (int i = 0; i < bufferLength; i++) {
      while (particleSensor.available() == false)
        particleSensor.check();
      redBuffer[i] = particleSensor.getRed();
      irBuffer[i] = particleSensor.getIR();
      particleSensor.nextSample();
      esp_task_wdt_reset();  // Reset watchdog timer
    }
    int8_t validSPO2;
    int8_t validHeartRate;
    maxim_heart_rate_and_oxygen_saturation(irBuffer, bufferLength, redBuffer, (int32_t *)&spo2, &validSPO2, (int32_t *)&heartRate, &validHeartRate);
    if (!validSPO2) {
      request->send(500, "application/json", "{\"status\":\"gagal\", \"message\":\"Invalid oxygen level data\"}");
      return;
    }
    String jsonResponse = "{\"status\":\"sukses\",\"value\":" + String(spo2) + "}";
    request->send(200, "application/json", jsonResponse);
  });

  server.on("/get_sensor_data/temperature", HTTP_GET, [](AsyncWebServerRequest *request) {
    sensors.requestTemperatures();
    temperature = sensors.getTempCByIndex(0);
    if (temperature == -127.00) {
      request->send(500, "application/json", "{\"status\":\"gagal\", \"message\":\"Invalid temperature data\"}");
      return;
    }
    String jsonResponse = "{\"status\":\"sukses\",\"value\":" + String(temperature) + "}";
    request->send(200, "application/json", jsonResponse);
  });

  server.on("/get_sensor_data/activity_level", HTTP_GET, [](AsyncWebServerRequest *request) {
    tcaSelect(1);
    sensors_event_t accel, gyro;
    mpu.getAccelerometerSensor()->getEvent(&accel);
    mpu.getGyroSensor()->getEvent(&gyro);
    activity_level = sqrt(sq(accel.acceleration.x) + sq(accel.acceleration.y) + sq(accel.acceleration.z));
    String jsonResponse = "{\"status\":\"sukses\",\"value\":" + String(activity_level) + "}";
    request->send(200, "application/json", jsonResponse);
  });

  server.on("/get_sensor_data/ecg", HTTP_GET, [](AsyncWebServerRequest *request) {
    if (!ecgCollecting) {
      ecgData.clear();
      ecgCollecting = true;
      startMillis = millis();
      endMillis = startMillis + sampleDuration;
      ecgTicker.attach_ms(sampleInterval, collectECG);
      request->send(200, "application/json", "{\"status\":\"sukses\", \"message\":\"ECG collection started\"}");
    } else if (millis() >= endMillis) {
      // Cek apakah data sudah terkumpul sepenuhnya
      if (ecgData.size() > 50) {  // Menambahkan syarat minimal data yang terkumpul
        DynamicJsonDocument doc(4096);
        doc["status"] = "sukses";
        doc["user_id"] = user_id;
        JsonArray data = doc.createNestedArray("value");

        for (int value : ecgData) {
          data.add(value);
        }

        String jsonResponse;
        serializeJson(doc, jsonResponse);
        request->send(200, "application/json", jsonResponse);
      } else {
        request->send(400, "application/json", "{\"status\":\"gagal\", \"message\":\"Data ECG tidak cukup terkumpul\"}");
      }
      ecgData.clear();
      ecgCollecting = false;
      ecgTicker.detach();
    } else {
      request->send(400, "application/json", "{\"status\":\"gagal\", \"message\":\"Pengumpulan data ECG masih berlangsung atau tidak ada data\"}");
    }
  });

  server.begin();
}

void loop() {
  // Reset watchdog timer
  esp_task_wdt_reset();

  // Update LCD
  tcaSelect(0);
  lcd.setCursor(0, 0);
  lcd.print(" PT. Prima Feedmill");

  lcd.setCursor(0, 1);
  lcd.write(byte(0));
  lcd.print(": ");
  lcd.print(heartRate);
  lcd.print(" bpm   ");
  lcd.write(byte(1));
  lcd.print(": ");
  lcd.print(spo2);
  lcd.print("%");

  lcd.setCursor(0, 2);
  lcd.write(byte(2));
  lcd.print(": ");
  lcd.print(temperature);
  lcd.print("C   ");
  lcd.write(byte(3));
  lcd.print(": ");
  lcd.print(activity_level);

  lcd.setCursor(0, 3);
  lcd.write(byte(4));
  lcd.print(": ");
  lcd.print(ecg_value);

  delay(10000);          // Delay for 10 seconds
  esp_task_wdt_reset();  // Reset watchdog timer again after delay
}

void collectECG() {
  ecg_value = analogRead(AD8232_OUTPUT);
  Serial.print("ECG Value: ");
  Serial.println(ecg_value);
  if (ecg_value < 4095) {  // Hanya simpan data yang valid
    ecgData.push_back(ecg_value);
  }
}