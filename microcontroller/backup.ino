#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <MAX30100_PulseOximeter.h>
#include <LiquidCrystal_I2C.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <ESPAsyncWebServer.h>

const char* ssid = "MathtechStudio";
const char* password = "Bellaciao13";

Adafruit_MPU6050 mpu;
PulseOximeter pox;
LiquidCrystal_I2C lcd(0x27, 20, 4); // Alamat I2C LCD mungkin berbeda
const int AD8232_OUTPUT = 2;
const int ONE_WIRE_BUS = 4; // GPIO pin untuk DS18B20
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

AsyncWebServer server(80);

float temperature;
float heart_rate;
float oxygen_level;
float activity_level;
int ecg_value;
int user_id = -1;

void tcaSelect(uint8_t i) {
  if (i > 7) return;
  Wire.beginTransmission(0x70);
  Wire.write(1 << i);
  Wire.endTransmission();
}

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Menghubungkan ke WiFi...");
  }
  Serial.println("Terhubung ke WiFi");

  Wire.begin();

  // Inisialisasi MPU6050
  tcaSelect(0);
  if (!mpu.begin()) {
    Serial.println("Tidak dapat menemukan sensor MPU6050!");
  } else {
    Serial.println("MPU6050 berhasil diinisialisasi!");
  }

  // Inisialisasi MAX30100
  tcaSelect(1);
  if (!pox.begin()) {
    Serial.println("Tidak dapat menemukan sensor MAX30100!");
  } else {
    pox.setIRLedCurrent(MAX30100_LED_CURR_7_6MA);
    Serial.println("MAX30100 berhasil diinisialisasi!");
  }

  // Inisialisasi LCD
  tcaSelect(2);
  lcd.init();
  lcd.backlight();
  lcd.print("Inisialisasi...");

  sensors.begin(); // DS18B20 tidak menggunakan tcaSelect

  pinMode(AD8232_OUTPUT, INPUT);

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

  server.on("/get_sensor_data/:sensor", HTTP_GET, [](AsyncWebServerRequest *request){
    String sensor = request->pathArg(0);
    DynamicJsonDocument doc(200);

    if (sensor == "heart_rate") {
      tcaSelect(1);
      heart_rate = pox.getHeartRate();
      if (heart_rate > 0) {
        doc["value"] = heart_rate;
        request->send(200, "application/json", "{\"status\":\"sukses\", \"value\":\"" + String(heart_rate) + "\"}");
      } else {
        request->send(500, "application/json", "{\"status\":\"gagal\", \"message\":\"Data sensor tidak valid\"}");
      }
    } else if (sensor == "oxygen_level") {
      tcaSelect(1);
      oxygen_level = pox.getSpO2();
      if (oxygen_level > 0) {
        doc["value"] = oxygen_level;
        request->send(200, "application/json", "{\"status\":\"sukses\", \"value\":\"" + String(oxygen_level) + "\"}");
      } else {
        request->send(500, "application/json", "{\"status\":\"gagal\", \"message\":\"Data sensor tidak valid\"}");
      }
    } else if (sensor == "temperature") {
      sensors.requestTemperatures();
      temperature = sensors.getTempCByIndex(0);
      if (temperature != -127.00) {
        doc["value"] = temperature;
        request->send(200, "application/json", "{\"status\":\"sukses\", \"value\":\"" + String(temperature) + "\"}");
      } else {
        request->send(500, "application/json", "{\"status\":\"gagal\", \"message\":\"Data sensor tidak valid\"}");
      }
    } else if (sensor == "activity_level") {
      tcaSelect(0);
      sensors_event_t accel, gyro;
      mpu.getAccelerometerSensor()->getEvent(&accel);
      mpu.getGyroSensor()->getEvent(&gyro);
      activity_level = sqrt(sq(accel.acceleration.x) + sq(accel.acceleration.y) + sq(accel.acceleration.z));
      doc["value"] = activity_level;
      request->send(200, "application/json", "{\"status\":\"sukses\", \"value\":\"" + String(activity_level) + "\"}");
    } else {
      request->send(400, "application/json", "{\"status\":\"gagal\", \"message\":\"Sensor tidak dikenali\"}");
    }
  });

  server.begin();
}

void loop() {
  pox.update();

  if (WiFi.status() == WL_CONNECTED && user_id != -1) {
    HTTPClient http;
    http.begin("http://192.168.20.136:5000/sensor_data");
    http.addHeader("Content-Type", "application/json");

    tcaSelect(0);
    sensors_event_t accel, gyro;
    mpu.getAccelerometerSensor()->getEvent(&accel);
    mpu.getGyroSensor()->getEvent(&gyro);
    activity_level = sqrt(sq(accel.acceleration.x) + sq(accel.acceleration.y) + sq(accel.acceleration.z));

    tcaSelect(1);
    heart_rate = pox.getHeartRate();
    oxygen_level = pox.getSpO2();

    ecg_value = analogRead(AD8232_OUTPUT);

    sensors.requestTemperatures();
    temperature = sensors.getTempCByIndex(0);

    if (heart_rate == 0 || oxygen_level == 0 || temperature == -127.00) {
      Serial.println("Data sensor tidak valid, mencoba lagi...");
      delay(10000);
      return;
    }

    Serial.println("Data Sensor:");
    Serial.print("Temperature: ");
    Serial.print(temperature);
    Serial.println(" C");
    Serial.print("Heart Rate: ");
    Serial.print(heart_rate);
    Serial.println(" bpm");
    Serial.print("Oxygen Level: ");s
    Serial.print(oxygen_level);
    Serial.println(" %");
    Serial.print("Activity Level: ");
    Serial.println(activity_level);
    Serial.print("ECG Value: ");
    Serial.println(ecg_value);

    String httpRequestData = "{\"user_id\":" + String(user_id) + ",\"temperature\":" + String(temperature)
                            + ",\"heart_rate\":" + String(heart_rate)
                            + ",\"oxygen_level\":" + String(oxygen_level)
                            + ",\"activity_level\":" + String(activity_level)
                            + ",\"ecg_value\":" + String(ecg_value) + "}";

    int httpResponseCode = http.POST(httpRequestData);

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

  delay(10000);
}
