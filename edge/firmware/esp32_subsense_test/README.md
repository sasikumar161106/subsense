# SubSense TinyML ESP32 Hardware Test Suite

Turnkey on-device test and benchmarking sketch for validating SubSense TinyML models on a physical **ESP32** microcontroller.

---

## 🚀 Quick Start (Arduino IDE)

### 1. Requirements
* An **ESP32** board (ESP32-WROOM-32, DevKit V1, NodeMCU-32S, ESP32-S3, or ESP32-C3).
* Micro-USB or USB-C data cable (ensure it's a **data** cable, not charge-only).
* **Arduino IDE** (version 1.8.x or 2.x).

### 2. Configure Arduino IDE (if not already done)
1. Open Arduino IDE.
2. Go to **File** -> **Preferences**.
3. In **Additional Boards Manager URLs**, ensure the Espressif ESP32 package URL is added:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Go to **Tools** -> **Board** -> **Boards Manager**, search for `esp32` by **Espressif Systems**, and ensure it is installed.

### 3. Open & Flash the Sketch
1. In Arduino IDE, open:
   `firmware/esp32_subsense_test/esp32_subsense_test.ino`
   *(All required headers and C model files are self-contained in this folder!)*
2. Under **Tools**, configure:
   * **Board**: `ESP32 Dev Module` (or your specific board variant)
   * **Upload Speed**: `921600` (or `115200` if upload fails)
   * **Port**: Select the COM port corresponding to your ESP32
3. Click the **Upload** button (arrow icon).
   *(Tip: If you see `Connecting......._____.....`, press and hold the **BOOT** button on the ESP32 for 2 seconds until uploading begins).*

### 4. Open the Interactive Serial Monitor
1. In Arduino IDE, go to **Tools** -> **Serial Monitor**.
2. Set the baud rate in the bottom-right corner to **`115200 baud`**.
3. Press the **EN / RST** button on the ESP32 to restart the board.

---

## 📋 What the Self-Test Demonstrates

On startup, the ESP32 blinks its onboard LED 3 times and executes three automatic benchmark tests:

1. **Node-Tier Model Benchmark (2-Layer High-Recall Detector)**:
   * Tests calibrated nominal input vs severe hazard input.
   * Measures execution time (typically **~3 to 5 microseconds** at 240 MHz).
   * Verifies immediate local siren triggering without waiting for cloud/mesh roundtrips.

2. **Gateway-Tier Model Benchmark (6-Layer INT8 Autoencoder)**:
   * Evaluates integer reconstruction error (MSE) against the 474 warning threshold and 950 critical threshold.
   * Measures latency (typically **~380 microseconds**).
   * Verifies anomaly scoring and confidence ratings.

3. **End-to-End Pipeline & JSON Serialization**:
   * Pushes 32 sensor telemetry samples into the circular ring buffer.
   * Computes 8 deterministic statistical features (Tilt RoC, Vibration RMS, Crack state, etc.).
   * Runs INT8 quantization and inference.
   * Evaluates the safety rule fallback safeguard.
   * Emits a cloud-conformant JSON Risk Event payload directly to the Serial port.
   * Automatically turns ON the onboard LED (GPIO 2) if a critical alert or siren is fired.

---

## 🎮 Interactive Serial Console Commands

In the Serial Monitor, type any of the following characters and press **Enter**:

| Key | Action |
|:---:|:---|
| `1` | Run **Node Model Benchmark** (measures latency & tests siren trigger) |
| `2` | Run **Gateway Model Benchmark** (reports MSE reconstruction & score) |
| `3` | Run **Full End-to-End Pipeline** & print Cloud JSON Risk Event |
| `4` | **Stream Live Mine Subsidence Simulation** (Watch 40 timesteps from normal strata to catastrophic collapse with real-time LED siren activation) |
| `5` | Print **Power Consumption & 4-Year Battery Lifespan Projections** |
| `6` | **Toggle Hardware Siren / LED Pin** (GPIO 2) manually |
| `7` | Print **Self-Health Telemetry JSON** |
| `?` | Show interactive command menu |

---

## 🔌 Hardware Pin Mapping

| Peripheral | ESP32 Pin | Behavior |
|:---|:---|:---|
| **Siren Indicator / Status LED** | `GPIO 2` | • 3 short flashes on boot<br>• OFF during nominal conditions<br>• Blinks during Early Warning state<br>• Solid ON during Critical Subsidence alert |
| **Buzzer (Optional)** | `GPIO 2` or `GPIO 4` | Connect external active 3.3V/5V piezo buzzer between pin and GND |

---

## 🛠️ Troubleshooting

* **No COM port appears in Arduino IDE**:
  * Check your USB cable: many cheap cables are "charging only" with no data wires.
  * Install the USB-to-UART bridge driver for your board:
    * Silicon Labs **CP2102 / CP2104**: [Download CP210x Driver](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)
    * WCH **CH340 / CH341**: [Download CH340 Driver](http://www.wch-ic.com/downloads/CH341SER_EXE.html)
* **`A fatal error occurred: Failed to connect to ESP32: No serial data received`**:
  * Hold down the **BOOT** button on the ESP32 while the upload tool says `Connecting........_____.....` until the flashing progress percentage starts.
* **Garbled text in Serial Monitor**:
  * Ensure the Serial Monitor baud rate is set to exactly **`115200`**.
