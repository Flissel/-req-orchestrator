# 📋 IoT/Embedded (Wokwi) - Projekt-Fragebogen
## Template: 15-iot-wokwi (Arduino/ESP32 + Wokwi Emulator)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **Projekt Name** | |
| **Board** | Arduino Uno, ESP32, Raspberry Pi Pico |
| **Zweck** | Sensor, Aktor, Gateway, Display |

---

## A. HARDWARE-PLATTFORM

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| A1 | Microcontroller? | [ ] ESP32 (empfohlen) [ ] Arduino Uno [ ] Arduino Mega [ ] Raspberry Pi Pico | |
| A2 | Variant? | [ ] ESP32-DevKit [ ] ESP32-C3 [ ] ESP32-S3 | |
| A3 | Nur Emulation? | [ ] Ja (Wokwi only) [ ] Auch echte Hardware | |
| A4 | Battery Powered? | [ ] Ja [ ] Nein (USB/Netzteil) | |

---

## B. SENSOREN

| # | Sensor | Benötigt? | Details |
|---|--------|-----------|---------|
| B1 | Temperatur? | [ ] Ja [ ] Nein | DHT22, DS18B20, BME280 | |
| B2 | Luftfeuchtigkeit? | [ ] Ja [ ] Nein | DHT22, BME280 | |
| B3 | Luftdruck? | [ ] Ja [ ] Nein | BMP280, BME280 | |
| B4 | Bewegung (PIR)? | [ ] Ja [ ] Nein | HC-SR501 | |
| B5 | Distanz (Ultrasonic)? | [ ] Ja [ ] Nein | HC-SR04 | |
| B6 | Licht (LDR)? | [ ] Ja [ ] Nein | Photoresistor | |
| B7 | Accelerometer/Gyro? | [ ] Ja [ ] Nein | MPU6050 | |
| B8 | GPS? | [ ] Ja [ ] Nein | NEO-6M | |
| B9 | RFID? | [ ] Ja [ ] Nein | RC522 | |
| B10 | Touch? | [ ] Ja [ ] Nein | Capacitive Touch | |

---

## C. AKTOREN & OUTPUT

| # | Aktor | Benötigt? | Details |
|---|-------|-----------|---------|
| C1 | LEDs? | [ ] Ja [ ] Nein | Single, RGB, WS2812 | |
| C2 | LCD Display? | [ ] Ja [ ] Nein | 16x2, 20x4, I2C | |
| C3 | OLED Display? | [ ] Ja [ ] Nein | SSD1306 128x64 | |
| C4 | Buzzer? | [ ] Ja [ ] Nein | Passive, Active | |
| C5 | Servo Motor? | [ ] Ja [ ] Nein | SG90, MG996R | |
| C6 | DC Motor? | [ ] Ja [ ] Nein | L298N Driver | |
| C7 | Relay? | [ ] Ja [ ] Nein | 1, 2, 4 Channel | |
| C8 | 7-Segment? | [ ] Ja [ ] Nein | TM1637 | |

---

## D. KOMMUNIKATION

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D1 | WiFi? | [ ] Ja [ ] Nein | ESP32/ESP8266 | |
| D2 | Bluetooth? | [ ] Ja [ ] Nein | BLE, Classic | |
| D3 | MQTT? | [ ] Ja [ ] Nein | Broker URL | |
| D4 | HTTP API? | [ ] Ja [ ] Nein | REST Client/Server | |
| D5 | WebSocket? | [ ] Ja [ ] Nein | Real-time | |
| D6 | Serial (UART)? | [ ] Ja [ ] Nein | Debugging, Kommunikation | |
| D7 | I2C Devices? | [ ] Ja [ ] Nein | Welche Adressen | |
| D8 | SPI Devices? | [ ] Ja [ ] Nein | | |

---

## E. TECH-STACK ENTSCHEIDUNGEN

### Entwicklungsumgebung

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | IDE? | [ ] PlatformIO (empfohlen) [ ] Arduino IDE [ ] ESP-IDF | |
| E2 | Sprache? | [ ] C/C++ (Arduino) [ ] MicroPython [ ] CircuitPython | |
| E3 | Framework? | [ ] Arduino Framework [ ] ESP-IDF [ ] Zephyr | |
| E4 | Emulator? | [ ] Wokwi (empfohlen) [ ] SimulIDE | |

### Code-Struktur

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E5 | Code-Struktur? | [ ] Single File [ ] Multi-File [ ] Library Pattern | |
| E6 | State Machine? | [ ] Ja [ ] Nein | |
| E7 | RTOS? | [ ] Nein [ ] FreeRTOS | |
| E8 | OTA Updates? | [ ] Ja [ ] Nein | ESP32 | |

### Cloud & Backend

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E9 | Cloud Platform? | [ ] Keine [ ] Home Assistant [ ] AWS IoT [ ] Blynk | |
| E10 | Data Logging? | [ ] Keine [ ] InfluxDB [ ] ThingSpeak | |
| E11 | Dashboard? | [ ] Keine [ ] Grafana [ ] Node-RED | |

---

## F. POWER MANAGEMENT

| # | Frage | Antwort |
|---|-------|---------|
| F1 | Power Source? | USB, Battery, Solar |
| F2 | Battery Type? | LiPo, 18650, AA |
| F3 | Deep Sleep? | Ja/Nein |
| F4 | Wake-up Source? | Timer, GPIO, Touch |
| F5 | Target Battery Life? | Stunden, Tage, Wochen |

---

## G. WOKWI SIMULATION

| # | Frage | Antwort |
|---|-------|---------|
| G1 | diagram.json vorhanden? | Ja/Nein |
| G2 | Custom Parts? | Welche |
| G3 | Serial Monitor? | Baud Rate |
| G4 | Virtual Sensors? | Slider, Button |
| G5 | Network Simulation? | WiFi Mock |

---

## H. TESTING & DEBUGGING

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | Serial Debug? | [ ] Ja [ ] Nein | |
| H2 | LED Indicators? | [ ] Ja [ ] Nein | |
| H3 | Unit Tests? | [ ] Keine [ ] PlatformIO Test | |
| H4 | Integration Tests? | [ ] Wokwi CI [ ] None | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] Main Sketch (main.cpp)
- [ ] platformio.ini
- [ ] diagram.json (Wokwi)
- [ ] Sensor Libraries
- [ ] WiFi/MQTT Setup
- [ ] Display Handler
- [ ] State Machine
- [ ] Power Management
- [ ] OTA Update Setup
- [ ] README mit Schaltplan

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "15-iot-wokwi",
  "hardware": {
    "platform": "ESP32 / Arduino",
    "emulator": "Wokwi"
  },
  "development": {
    "ide": "PlatformIO",
    "framework": "Arduino",
    "language": "C/C++"
  },
  "communication": {
    "wifi": true,
    "mqtt": true,
    "protocols": ["I2C", "SPI", "UART"]
  },
  "cloud": {
    "platform": "Home Assistant / MQTT Broker",
    "dashboard": "Grafana (optional)"
  }
}
```
