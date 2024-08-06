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

// WiFi Credentials
const char* ssid = "MathtechStudio";
const char* password = "Bellaciao13";

// Create instances for sensors
Adafruit_MPU6050 mpu;
MAX30105 particleSensor;
OneWire oneWire(18); // DS18B20 data pin
DallasTemperature sensors(&oneWire);
LiquidCrystal_I2C lcd(0x27, 20, 4); // I2C address 0x27 for 20x4 LCD

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
int user_id = -1;

// I2C Multiplexer Function
void tcaSelect(uint8_t i) {
  if (i > 7) return;
  Wire.beginTransmission(0x70);
  Wire.write(1 << i);
  Wire.endTransmission();
}

// WiFi and Server setup
AsyncWebServer server(80);

void setup() {
  Serial.begin(115200);

  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Menghubungkan ke WiFi...");
  }
  Serial.println("Terhubung ke WiFi");

  // Initialize I2C
  Wire.begin();
  
  // Initialize LCD on channel 0
  tcaSelect(0);
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print(" PT. Prima Feedmill");

  // Initialize MPU6050 on channel 1
  tcaSelect(1);
  if (!mpu.begin(0x68)) {
    Serial.println("Tidak dapat menemukan sensor MPU6050!");
    while (1);
  }
  Serial.println("MPU6050 berhasil diinisialisasi!");

  // Initialize MAX30105 on channel 4
  tcaSelect(4);
  if (!particleSensor.begin()) {
    Serial.println("Tidak dapat menemukan sensor MAX30105!");
    while (1);
  }
  particleSensor.setup();
  particleSensor.setPulseAmplitudeRed(0x0A); // Turn on RED LED
  particleSensor.setPulseAmplitudeGreen(0);  // Turn off GREEN LED
  Serial.println("MAX30105 berhasil diinisialisasi!");

  // Initialize DS18B20
  sensors.begin();
  Serial.println("DS18B20 berhasil diinisialisasi!");

  // Initialize AD8232
  pinMode(AD8232_OUTPUT, INPUT);
  pinMode(LO_MINUS, INPUT);
  pinMode(LO_PLUS, INPUT);

  // HTTP server routes
  server.on("/set_user_id", HTTP_POST, [](AsyncWebServerRequest *request) {}, NULL, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
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

  server.begin();
}

void loop() {
  // Check if WiFi is connected and user ID is set
  if (WiFi.status() == WL_CONNECTED && user_id != -1) {
    HTTPClient http;
    http.begin("http://192.168.20.136:5000/sensor_data");
    http.addHeader("Content-Type", "application/json");

    // Select channel for MPU6050 and read data
    tcaSelect(1);
    sensors_event_t accel, gyro;
    mpu.getAccelerometerSensor()->getEvent(&accel);
    mpu.getGyroSensor()->getEvent(&gyro);
    activity_level = sqrt(sq(accel.acceleration.x) + sq(accel.acceleration.y) + sq(accel.acceleration.z));

    // Select channel for MAX30105 and read data
    tcaSelect(4);
    uint32_t irBuffer[100]; // infrared LED sensor data
    uint32_t redBuffer[100]; // red LED sensor data
    int bufferLength = 100; // data length
    for (int i = 0; i < bufferLength; i++) {
      while (particleSensor.available() == false)
        particleSensor.check();
      redBuffer[i] = particleSensor.getRed();
      irBuffer[i] = particleSensor.getIR();
      particleSensor.nextSample();
    }

    // Calculate heart rate and SpO2
    int8_t validSPO2;
    int8_t validHeartRate;
    maxim_heart_rate_and_oxygen_saturation(irBuffer, bufferLength, redBuffer, (int32_t*)&spo2, &validSPO2, (int32_t*)&heartRate, &validHeartRate);

    // Read ECG value from AD8232
    ecg_value = analogRead(AD8232_OUTPUT);

    // Read temperature from DS18B20
    sensors.requestTemperatures();
    temperature = sensors.getTempCByIndex(0);

    // Ensure valid sensor data
    if (!validHeartRate || !validSPO2 || temperature == -127.00) {
      Serial.println("Data sensor tidak valid, mencoba lagi...");
      delay(10000);
      return;
    }

    // Print sensor data for debugging
    Serial.println("Data Sensor:");
    Serial.print("Temperature: ");
    Serial.print(temperature);
    Serial.println(" C");
    Serial.print("Heart Rate: ");
    Serial.print(heartRate);
    Serial.println(" bpm");
    Serial.print("Oxygen Level: ");
    Serial.print(spo2);
    Serial.println(" %");
    Serial.print("Activity Level: ");
    Serial.println(activity_level);
    Serial.print("ECG Value: ");
    Serial.println(ecg_value);

    // Prepare JSON payload
    String httpRequestData = "{\"user_id\":" + String(user_id) + ",\"temperature\":" + String(temperature)
                            + ",\"heart_rate\":" + String(heartRate)
                            + ",\"oxygen_level\":" + String(spo2)
                            + ",\"activity_level\":" + String(activity_level)
                            + ",\"ecg_value\":" + String(ecg_value) + "}";

    // Send POST request
    int httpResponseCode = http.POST(httpRequestData);

    // Print response
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println(httpResponseCode);
      Serial.println(response);
    } else {
      Serial.print("Error pada pengiriman HTTP POST: ");
      Serial.println(httpResponseCode);
      Serial.println(http.errorToString(httpResponseCode).c_str());
    }
    http.end();
  } else {
    Serial.println("Tidak terhubung ke WiFi atau user_id belum diset");
  }

  // Update LCD
  tcaSelect(0);
  lcd.setCursor(0, 0);
  lcd.print(" PT. Prima Feedmill");
  lcd.setCursor(0, 1);
  lcd.print("Temp: ");
  lcd.print(temperature);
  lcd.print("C");
  lcd.setCursor(0, 2);
  lcd.print("<3 BPM: ");
  lcd.print(heartRate);
  lcd.setCursor(10, 2);
  lcd.print("O2 SpO2: ");
  lcd.print(spo2);
  lcd.print("%");
  lcd.setCursor(0, 3);
  lcd.print("ECG: ");
  lcd.print(ecg_value);

  delay(10000); // Delay for 10 seconds

  // Prevent watchdog from triggering
  yield();
}