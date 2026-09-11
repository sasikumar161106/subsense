# SubSense Project Comprehensive Code Audit Report

**Audit Date:** September 2026  
**Scope:** Full-repo line-by-line static analysis and bug discovery across all subsystems (Root/Orchestration, Gateway-Bridge, Edge Firmware & TinyML, AI-ML Pipeline, Reference AI-ML, GIS Engine, Alerting Subsystem, Dashboard & BFF Gateway).  
**Severity Definitions:**
- **CRITICAL**: System crash, data loss, unauthenticated access/security vulnerability, silent corruption of telemetry or geotechnical safety alerts.
- **HIGH**: Feature failure under normal or edge conditions, broken API contracts, memory leaks, race conditions, incorrect mathematical calculations.
- **MEDIUM**: Unhandled edge cases, missing error boundaries, improper fallback logic, resource cleanup omissions, performance bottlenecks.
- **LOW**: Inconsistent state management, minor input validation gaps, improper HTTP status codes, unhandled edge types.
- **NEGLIGIBLE**: Typographical errors in logs/strings, unused imports/variables, redundant calculations, minor documentation/code discrepancies.

---

## Executive Summary

The comprehensive, full-codebase line-by-line audit of the **SubSense Real-Time Underground Mine Subsidence Monitoring Platform** has been completed across all 636 source files. Every subsystem—ranging from physical ESP32 C/C++ firmware and hardware drivers, serial gateway bridges, and PyTorch AI/ML models, to GIS spatio-temporal contouring engines, Node.js alerting rule engines, and the Fastify/React multi-tenant dashboard—has been thoroughly examined.

A total of **76 distinct bugs** were identified, categorized, and documented with line-level code references, root cause analyses, failure impacts, and remediation guidance.

### Summary by Severity

| Severity | Count | Primary Impact Characteristics |
| :--- | :---: | :--- |
| **CRITICAL** | **11** | Remote Code Execution (RCE), complete authentication/MFA bypass, false positive emergency evacuations, SRAM wipe in ESP32 sleep, packet truncation in mesh reassembly, delivery status persistence failure. |
| **HIGH** | **25** | Cross-tenant data leakage, zero data fabrication violations, test suite regressions, race conditions in tile caching, double siren physical actuation, cascade desensitization in spatial correlation. |
| **MEDIUM** | **24** | Unhandled out-of-order packets, inverted GIS raster coordinates, thread-safety hazards, uncancelled network operations, broken re-evaluation loops, division-by-zero risks. |
| **LOW** | **16** | Formatting type errors, modulo identifier collisions, dead Airflow DAG declarations, missing feature fields, redundant duplicate repositories, minor documentation mismatches. |
| **TOTAL** | **76** | **Comprehensive Full-System Audit Findings** |

### Summary by Subsystem

| Subsystem | Total Bugs | CRITICAL | HIGH | MEDIUM | LOW |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Root & Orchestration** | 4 | 0 | 1 | 2 | 1 |
| **2. Gateway Bridge** | 7 | 1 | 3 | 2 | 1 |
| **3. Edge Firmware & TinyML** | 16 | 3 | 4 | 6 | 3 |
| **4. AI-ML Subsystem** | 12 | 0 | 4 | 4 | 4 |
| **5. Reference AI-ML** | 8 | 0 | 3 | 3 | 2 |
| **6. GIS Subsystem** | 10 | 2 | 3 | 3 | 2 |
| **7. Alerting Subsystem** | 8 | 2 | 3 | 2 | 1 |
| **8. Dashboard & BFF Gateway** | 11 | 3 | 4 | 2 | 2 |
| **Total** | **76** | **11** | **25** | **24** | **16** |

---

﻿## 1. Root & Orchestration Subsystem

### [BUG-ROOT-001] Missing `devices` Mapping for Serial Port in Docker Compose
- **Severity**: HIGH
- **File & Line**: `docker-compose.yml:188-202`
- **Description**: The `gateway-bridge` service defines `SER_PORT: /dev/ttyUSB0` to read serial telemetry from the physical ESP32 gateway node. However, `docker-compose.yml` does not declare a `devices:` block (`devices: - /dev/ttyUSB0:/dev/ttyUSB0`). In Docker on Linux, unprivileged containers cannot access host character devices without explicit device mapping or privileged flags.
- **Impact**: The gateway bridge container immediately crashes or raises `serial.SerialException: [Errno 2] could not open port /dev/ttyUSB0: [Errno 2] No such file or directory` when running under Docker Compose.
- **Recommendation**: Add device passthrough in `docker-compose.yml`:
  ```yaml
  gateway-bridge:
    ...
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
  ```

### [BUG-ROOT-002] Healthchecks Rely on `curl` in Slim/Alpine Images
- **Severity**: MEDIUM
- **File & Line**: `docker-compose.yml:65, 115, 159`
- **Description**: Healthchecks for `ai-ml` (`python:3.11-slim`), `alerting-backend` (`node:alpine` or `node:slim`), and `bff-gateway` invoke `CMD curl -f http://localhost:...`. Minimal Python and Node Alpine images do not bundle `curl` by default.
- **Impact**: Docker marks the containers as permanently `unhealthy`, which causes dependent containers (`depends_on: { condition: service_healthy }`) to block forever or restart in a loop.
- **Recommendation**: Use Python (`python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"`) or Node (`node -e "require('http').get('http://localhost:3000/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"`), or install `curl` explicitly in the respective Dockerfiles.

### [BUG-ROOT-003] `start_subsense_services.ps1` Runs `vite preview` Without Checking for Built Dist
- **Severity**: MEDIUM
- **File & Line**: `start_subsense_services.ps1:38`
- **Description**: The launcher script executes `npm --workspace=apps/web-dashboard run preview -- --port 5174`. `vite preview` serves the pre-built `dist/` directory. If the user hasn't run `npm run build` beforehand, `vite preview` aborts with `Error: The directory "dist" does not exist. Did you forget to run "vite build"?`.
- **Impact**: Running `start_subsense_services.ps1` out-of-the-box fails to start the Web Dashboard.
- **Recommendation**: Change line 38 to invoke `run dev -- --port 5174` or build `dist` if missing before previewing:
  ```powershell
  Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WorkspaceRoot\dashboard'; npm --workspace=apps/web-dashboard run dev -- --port 5174"
  ```

### [BUG-ROOT-004] Missing `gateway-bridge/test_serial_sim.py` Referenced in Architecture Spec
- **Severity**: NEGLIGIBLE
- **File & Line**: `README.md:116`
- **Description**: `README.md` documents `gateway-bridge/test_serial_sim.py` as the hardware-in-the-loop test transmitter, but the file does not exist in the repository.
- **Impact**: Developers attempting to run the hardware-in-the-loop simulation following README instructions cannot find the script.
- **Recommendation**: Provide `test_serial_sim.py` or update README to reference the `--mock` flag in `bridge.py`.

---

## 2. Gateway Bridge Subsystem

### [BUG-GB-001] Hardcoded Tenant ID Leakage & Assertion Failure in Test Suite
- **Severity**: CRITICAL
- **File & Line**: `gateway-bridge/bridge.py:76, 368`, `gateway-bridge/tests/test_bridge.py:46`
- **Description**: In `bridge.py`, `to_canonical()` sets `tenant_id = raw.get("tenant_id") or "OPCO-ECL-01"`. However, unit test `test_bridge.py` verifies against `"tenant-jharia-01"`, causing `AssertionError: 'OPCO-ECL-01' != 'tenant-jharia-01'`. Moreover, in `forward_reading()`, line 368 unconditionally hardcodes `"tenant_id": "OPCO-ECL-01"` in `bff_payload`, completely ignoring the incoming packet's `tenant_id`.
- **Impact**: The test suite fails out-of-the-box. In production, multi-tenant sensor telemetry from any other mine tenant (e.g. `tenant-jharia-01`, `tenant-bCCL-02`) is forcibly overwritten and broadcast as `OPCO-ECL-01`, causing critical cross-tenant data leakage and breach of tenant isolation.
- **Recommendation**:
  In `to_canonical()`:
  ```python
  tenant_id = raw.get("tenant_id") or "tenant-jharia-01"
  ```
  In `forward_reading()`:
  ```python
  "tenant_id": payload.get("tenant_id", "tenant-jharia-01"),
  ```

### [BUG-GB-002] `TypeError` Crash on Explicit `null` Anomaly Score
- **Severity**: HIGH
- **File & Line**: `gateway-bridge/bridge.py:167`
- **Description**: Line 167 executes:
  `"anomaly_score": float(raw.get("anomaly_score", 0.05 if (tilt_val or 0.0) < 4.0 else 0.95))`
  When an upstream gateway or firmware transmits `{"anomaly_score": null}`, `raw.get("anomaly_score", default)` returns `None`. `float(None)` raises `TypeError: float() argument must be a string or a real number, not 'NoneType'`.
- **Impact**: Any packet with a null anomaly score immediately crashes `to_canonical()` and terminates the serial ingestion pipeline for that frame.
- **Recommendation**:
  ```python
  raw_score = raw.get("anomaly_score")
  if raw_score is None:
      raw_score = 0.05 if (tilt_val or 0.0) < 4.0 else 0.95
  anomaly_score = float(raw_score)
  ```

### [BUG-GB-003] Offset-Naive vs Offset-Aware `TypeError` and Historical Packet Overwrite in `format_timestamp`
- **Severity**: HIGH
- **File & Line**: `gateway-bridge/bridge.py:50-63`
- **Description**: In `format_timestamp()`, `now_dt = datetime.now(timezone.utc)` is timezone-aware. Microcontrollers frequently output standard ISO-8601 strings without offset suffixes (e.g., `2026-09-11T10:00:00`). When parsed with `datetime.fromisoformat()`, `parsed` is timezone-naive. Evaluating `(now_dt - parsed).total_seconds()` raises `TypeError: can't subtract offset-naive and offset-aware datetimes`. The bare `except Exception:` catches this and replaces the edge timestamp with `now_dt`. Furthermore, any queued/buffered packet older than 60 seconds (such as packets drained from the offline queue) has its true capture timestamp overwritten with the gateway arrival time.
- **Impact**: All edge timestamps without timezone offsets are lost and replaced with surface arrival time, skewing angular velocity (`d(tilt)/dt`) calculations in the AI/ML LSTM forecasting layer. Drained offline queue records also lose their true historical timestamps.
- **Recommendation**:
  ```python
  def format_timestamp(raw_ts: Any) -> str:
      now_dt = datetime.now(timezone.utc)
      if isinstance(raw_ts, str) and len(raw_ts) >= 19:
          try:
              clean_ts = raw_ts.replace("Z", "+00:00")
              parsed = datetime.fromisoformat(clean_ts)
              if parsed.tzinfo is None:
                  parsed = parsed.replace(tzinfo=timezone.utc)
              return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
          except Exception:
              pass
      return now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
  ```

### [BUG-GB-004] Serial Stream Corruption in `SerialJSONExtractor` due to Unescaped Braces in Strings
- **Severity**: HIGH
- **File & Line**: `gateway-bridge/bridge.py:299-323`
- **Description**: `SerialJSONExtractor` tracks brace nesting depth (`self._brace_depth`) character-by-char without checking whether `{` or `}` appears inside a string literal (`"..."`) or accounting for escaped quotes (`\"`).
- **Impact**: If any telemetry packet, status banner, or error log contains `{` or `}` inside a string value (e.g., `"status": "sensor {MPU6050} calibrated"`), the brace counter desynchronizes. The parser attempts to decode a partial string, throws a `JSONDecodeError`, clears `self._buffer`, and permanently drops both that packet and adjacent packets.
- **Recommendation**: Track `inside_string` and escape states in the character scanner before altering `self._brace_depth`.

### [BUG-GB-005] SQLite Database Cursor Concurrency Hazard in `OfflineQueue.fetch_batch`
- **Severity**: MEDIUM
- **File & Line**: `gateway-bridge/bridge.py:242-245`
- **Description**: In `fetch_batch()`, while iterating over rows returned by `conn.execute("SELECT ...").fetchall()`, a corrupt record triggers `conn.execute("DELETE FROM offline_telemetry WHERE id = ?", (r["id"],))` on the same connection handle.
- **Impact**: Modifying a table while an active row iterator is reading from it can raise `sqlite3.OperationalError: database is locked` on SQLite or invalidate cursor states.
- **Recommendation**: Collect corrupt IDs in a list first, and execute deletes outside the iteration loop.

### [BUG-GB-006] Serial Port Handle Leak on Unexpected Exceptions in `run_serial_loop`
- **Severity**: MEDIUM
- **File & Line**: `gateway-bridge/bridge.py:474-499`
- **Description**: In `run_serial_loop()`, if an unhandled exception occurs inside `process_serial_line()` or during packet parsing, execution jumps to `except Exception as e:` at line 497. The inner loop does not break cleanly and `ser.close()` is never reached. In the subsequent outer loop iteration, a new `serial.Serial()` is allocated.
- **Impact**: Leaks the open serial file descriptor on the host OS, leading to `serial.SerialException: PermissionError / Device or resource busy` on Windows/Linux on subsequent connection attempts until the entire process is killed.
- **Recommendation**: Wrap the inner loop in a `try...finally: ser.close()` block.

### [BUG-GB-007] Missing CLI Parameter and Environment Variable for BFF URL
- **Severity**: LOW
- **File & Line**: `gateway-bridge/bridge.py:41, 507-520`
- **Description**: `DEFAULT_BFF_URL` is hardcoded to `http://localhost:3001/api/v1/telemetry/broadcast`. `main()` accepts `--port`, `--baud`, `--ingest-url`, and `--db-path`, but does not define `--bff-url` or inspect `os.getenv("BFF_URL")`.
- **Impact**: In containerized environments where the BFF gateway runs on a different host or container name (`http://bff-gateway:3001`), the bridge cannot be configured to forward telemetry to the BFF, causing connection refused errors.
- **Recommendation**: Add `--bff-url` argument to `argparse` and check `os.getenv("BFF_URL", DEFAULT_BFF_URL)`.

---


﻿## 3. Edge Firmware, TinyML & Hardware Subsystem

### [BUG-EDGE-001] Dangerous Parameter Mismatch in Fallback Evaluation Sounding False Siren
- **Severity**: CRITICAL
- **File & Line**: `edge/firmware/subsense_app.c:110-118`
- **Description**: In `subsense_step()`, the call to `subsense_fallback_evaluate()` passes:
  ```c
  bool raw_hazard = subsense_fallback_evaluate(
      raw_features[0],
      raw_features[1],
      raw_features[4], // BUG: raw_features[4] is vibration_peak_count!
      raw_features[5],
      raw_features[6],
      fallback_reason,
      sizeof(fallback_reason),
      &fallback_siren
  );
  ```
  In `subsense_fallback.h`, parameter 3 is `float vib_peak` (Peak raw vibration in g), which is evaluated as:
  `if (fabsf(vib_peak) >= G_SUBSENSE_DEFAULT_FALLBACK.max_vibration_g)` where `max_vibration_g = 1.2f`.
  However, `raw_features[4]` in `subsense_features.h` is `vibration_peak_count` (an integer count of peaks, e.g. 1.0, 2.0, 3.0).
- **Impact**: If just 2 minor vibration peaks occur within a 32-sample window, `raw_features[4]` evaluates to `2.0f >= 1.2f`. The system misinterprets a peak count of 2 as a violent 2.0g seismic shockwave, triggers `RAW_VIB_PEAK_EXCEEDED`, and immediately fires the physical mine evacuation siren (`event.siren_triggered = true`).
- **Recommendation**: Pass peak vibration acceleration (`raw_features[3]` for RMS or a dedicated peak magnitude channel) into parameter 3, or align the fallback evaluation parameters with the feature vector layout:
  ```c
  subsense_fallback_evaluate(
      raw_features[0],
      raw_features[1],
      raw_features[3], // RMS vibration or true peak acceleration
      raw_features[5],
      raw_features[6],
      ...
  );
  ```

### [BUG-EDGE-002] Deep Sleep Wipes Ring Buffer Memory in Battery Duty-Cycle Mode
- **Severity**: CRITICAL
- **File & Line**: `edge/firmware/subsense_power_mgmt.c:58`, `edge/firmware/subsense_app.c:17`
- **Description**: In `POWER_MODE_BATTERY_DUTY_CYCLE`, the node calls `subsense_power_enter_sleep()` which invokes `esp_deep_sleep_start()`. On ESP32, deep sleep shuts down main power to standard SRAM, causing a complete system reset on wakeup (`app_main()` runs again). The ring buffer in `subsense_app.c` is declared as standard static SRAM:
  `static SubSenseWindowBuffer s_window_buf;`
- **Impact**: On every wakeup, `s_window_buf` is wiped clean and re-initialized to 0. The node pushes 1 sample (`count = 1`), checks `if (!subsense_buffer_is_full(&s_window_buf)) return;`, and goes back to sleep. The buffer count never reaches 32, meaning on-device inference and feature extraction can never execute when duty-cycling is active.
- **Recommendation**: Store persistent state in RTC slow memory using the ESP-IDF `RTC_DATA_ATTR` attribute:
  ```c
  #ifdef ESP_PLATFORM
  static RTC_DATA_ATTR SubSenseWindowBuffer s_window_buf;
  static RTC_DATA_ATTR SubSenseHealthTelemetry s_health;
  #else
  static SubSenseWindowBuffer s_window_buf;
  static SubSenseHealthTelemetry s_health;
  #endif
  ```

### [BUG-EDGE-003] Premature Message Reassembly and Truncation on Duplicate ESP-NOW Fragments
- **Severity**: CRITICAL
- **File & Line**: `edge/firmware/subsense_wifi_mesh.cpp:200-216`
- **Description**: In the ESP-NOW receive handler `on_esp_now_recv()`, fragment reassembly increments a simple counter:
  `slot->chunks_received++;`
  Because ESP-NOW packets are broadcast and forwarded across relays, the gateway frequently receives duplicate copies of the same fragment (e.g. directly from Node, and repeated 20ms later by Relay).
- **Impact**: For a 2-chunk message, if chunk 0 is received twice before chunk 1 arrives, `slot->chunks_received` reaches 2 (`>= slot->total_chunks`). The gateway prematurely marks the message as fully reassembled, null-terminates the incomplete buffer (containing only chunk 0 followed by zeroes), and invokes `s_rx_callback`. The surface gateway receives malformed JSON and drops it with `JSONDecodeError`. When chunk 1 finally arrives, its original slot has already been freed (`slot->in_use = false`), causing chunk 1 to be orphaned and dropped.
- **Recommendation**: Replace `chunks_received` counter with a bitmask tracking individual chunk indices:
  ```cpp
  uint32_t chunk_bit = (1U << pkt->chunk_index);
  if (!(slot->received_chunk_mask & chunk_bit)) {
      slot->received_chunk_mask |= chunk_bit;
      slot->chunks_received++;
  }
  ```

### [BUG-EDGE-004] Premature Feature Extraction on Unfilled Ring Buffer in Sensor Node
- **Severity**: HIGH
- **File & Line**: `edge/subsense_sensor_node/subsense_sensor_node.ino:282-290`
- **Description**: In `subsense_sensor_node.ino`, the main `loop()` pushes a sample into `g_win_buf` and immediately invokes `subsense_extract_features(&g_win_buf, raw_features)` on the very first iteration, without checking `subsense_buffer_is_full(&g_win_buf)`.
- **Impact**: During the first 31 seconds after boot, `g_win_buf.count < 32`. The feature extractor computes mean, variance, RMS, and rate of change over uninitialized zero-valued buffer elements, generating invalid feature vectors and producing garbage inference scores.
- **Recommendation**: Guard feature extraction with a buffer fullness check:
  ```cpp
  subsense_buffer_push(&g_win_buf, tilt, vib, 0.0f, 0.0f);
  if (!subsense_buffer_is_full(&g_win_buf)) {
      delay(1000);
      return;
  }
  ```

### [BUG-EDGE-005] Violation of Zero Data Fabrication Invariant in Inference Attribution
- **Severity**: HIGH
- **File & Line**: `edge/firmware/subsense_inference_engine.c:114-119`
- **Description**: In `subsense_run_inference()`, the feature attribution logic checks:
  ```c
  if (fabsf(raw_features[5]) > 0.50f && out_event->num_contributing_features < 4) {
      out_event->contributing_features[out_event->num_contributing_features++] = "displacement_delta";
  }
  if (raw_features[6] > 0.30f && out_event->num_contributing_features < 4) {
      out_event->contributing_features[out_event->num_contributing_features++] = "crack_state";
  }
  ```
  This directly violates the platform's core zero-fabrication mandate, which requires that uninstrumented physical sensors (displacement and crack gauges) never be attributed in alarms.
- **Impact**: When running on physical hardware with uninstrumented channels or noise on floating pins, the firmware attributes non-existent displacement or crack sensors in the emitted JSON event, failing automated safety audits and corrupting downstream explainability dashboards.
- **Recommendation**: Check sensor availability flags before attributing features, or suppress displacement and crack attribution on MPU6050-only nodes.

### [BUG-EDGE-006] Duplicate Mesh Chunks Permanently Invalidate OTA Firmware Transfers
- **Severity**: HIGH
- **File & Line**: `edge/firmware/subsense_ota_manager.c:86, 95`
- **Description**: In `subsense_ota_receive_chunk()`, `staging->bytes_received += chunk_len` is incremented on every chunk received. If a chunk is retransmitted over the mesh due to packet retry, `staging->bytes_received` increases beyond `staging->payload_size`.
- **Impact**: In `subsense_ota_validate_staging()`, the condition `if (staging->bytes_received != staging->payload_size)` fails because `bytes_received > payload_size`. The OTA staging slot is rejected as invalid (`staging->state = OTA_SLOT_EMPTY`), preventing OTA updates from succeeding whenever any packet is re-sent.
- **Recommendation**: Track received chunks with a chunk bitmap or range list so duplicate chunk receipts do not inflate `bytes_received`.

### [BUG-EDGE-007] Blocking Delays Inside ESP-NOW Radio Callbacks Causing Watchdog Resets
- **Severity**: HIGH
- **File & Line**: `edge/subsense_relay_node/subsense_relay_node_standalone.ino:90`, `edge/subsense_gateway_node/subsense_gateway_node.ino:44`
- **Description**: In `handle_forward()` and `on_mesh_data_received()`, `delay(20)` and `delay(30)` are called directly inside functions executed from `on_esp_now_recv()`. On ESP-IDF, ESP-NOW receive callbacks execute in the context of the high-priority WiFi driver task.
- **Impact**: Calling blocking delays inside the WiFi callback blocks the network driver task, triggers Task Watchdog Timer (TWDT) crashes, and causes packet drops for all other incoming mesh traffic.
- **Recommendation**: Remove blocking delays from radio callbacks, and handle LED blinks or printouts asynchronously or in the main `loop()`.

### [BUG-EDGE-008] Missing `#include <WiFi.h>` in Relay Node Sketch
- **Severity**: MEDIUM
- **File & Line**: `edge/subsense_relay_node/subsense_relay_node.ino:33`
- **Description**: Line 33 calls `WiFi.macAddress()`, but `subsense_relay_node.ino` only includes `<Arduino.h>` and `"subsense_wifi_mesh.h"`. Neither file includes `<WiFi.h>`.
- **Impact**: Compiling `subsense_relay_node.ino` with PlatformIO, CMake, or strict Arduino CLI configurations fails with error: `'WiFi' was not declared in this scope`.
- **Recommendation**: Add `#include <WiFi.h>` at top of `subsense_relay_node.ino`.

### [BUG-EDGE-009] Synthetic Timestamps in Sensor Node Emits Invalid UTC Time and Fixed Date
- **Severity**: MEDIUM
- **File & Line**: `edge/subsense_sensor_node/subsense_sensor_node.ino:294-298`
- **Description**: Timestamps are generated using:
  ```cpp
  snprintf(ts_str, sizeof(ts_str), "2026-09-10T%02u:%02u:%02uZ",
           (unsigned)(millis() / 3600000) % 24,
           (unsigned)(millis() / 60000) % 60,
           (unsigned)(millis() / 1000) % 60);
  ```
  This hardcodes the date to `2026-09-10` and uses milliseconds since boot as the hour of the day.
- **Impact**: Sensor packets on boot emit timestamps like `2026-09-10T00:00:01Z`. The surface gateway bridge compares this with surface UTC time; because the discrepancy exceeds 60 seconds, the gateway bridge silently discards the node timestamp and stamps surface arrival time.
- **Recommendation**: Provide an RTC sync mechanism over the mesh or omit the timestamp from the node so the gateway explicitly stamps arrival time.

### [BUG-EDGE-010] Dimensional Inconsistency in Vibration Acceleration vs Velocity
- **Severity**: MEDIUM
- **File & Line**: `edge/subsense_sensor_node/subsense_sensor_node.ino:188-191`
- **Description**: In `read_mpu6050()`, the vibration deviation is computed as `diff = fabsf(cur_mag - 1.0f)` (in g). It is then multiplied by `98.0665f` and stored as `*out_vib` in `mm/s`. Acceleration in g multiplied by `9.80665 m/s²` is acceleration in m/s² (or `9806.65 mm/s²`), not velocity in mm/s.
- **Impact**: Acceleration magnitude is labeled as velocity RMS (`mm/s`) with an incorrect scaling constant (`98.0665f` instead of `9806.65f` or true velocity integration).
- **Recommendation**: Properly integrate acceleration to velocity over `dt`, or label the variable and contract field as dynamic acceleration peak (`g` or `mm/s²`).

### [BUG-EDGE-011] Unchecked `critical_threshold == 0` Triggers Permanent Emergency Siren
- **Severity**: MEDIUM
- **File & Line**: `edge/firmware/subsense_inference_engine.c:74`
- **Description**: While `warning_threshold` checks `if (warn_th <= 0.0f) warn_th = 400.0f;`, `critical_threshold` has no zero check. If `config->critical_threshold` is uninitialized (0), `int_error >= config->critical_threshold` evaluates to `true` (since `int_error >= 0` is always true).
- **Impact**: Uninitialized or zero-configured nodes permanently breach the critical threshold and sound the evacuation siren on every single inference.
- **Recommendation**: Add default fallback for `critical_threshold <= 0`.

### [BUG-EDGE-012] Division-by-Zero Risk in Feature Normalization
- **Severity**: MEDIUM
- **File & Line**: `edge/firmware/subsense_features.c:131`
- **Description**: In `subsense_features_to_int8()`, `float normalized = (features[i] - config->scaler_mean[i]) / config->scaler_scale[i];`. If a feature has zero variance during calibration, `scaler_scale[i]` will be 0.0f.
- **Impact**: Causes division by zero resulting in `NaN` or `+Inf`, leading to undefined behavior or floating-point exceptions on embedded microcontrollers.
- **Recommendation**: Add epsilon guard: `float scale = config->scaler_scale[i] > 1e-6f ? config->scaler_scale[i] : 1.0f;`.

### [BUG-EDGE-013] Hardware Test Runner Truncates Multi-Line Nested JSON
- **Severity**: MEDIUM
- **File & Line**: `edge/scripts/test_esp32_hardware.py:115`
- **Description**: The serial reader stops collecting on the first line that starts with `}`:
  `if line.startswith("}"): collecting_json = False; break`
- **Impact**: Any nested JSON object (such as `node_health: { ... }`) whose inner block ends with a closing brace `}` causes premature termination of collection, corrupting the JSON payload and failing the hardware-in-the-loop test with `JSONDecodeError`.
- **Recommendation**: Track brace depth `{` and `}` instead of breaking on the first closing brace.

### [BUG-EDGE-014] Missing `sys.path` Bootstrapping in Edge Unit Tests
- **Severity**: LOW
- **File & Line**: `edge/tests/test_firmware_logic.py:15`, `edge/tests/test_pipeline.py:16`, `edge/tests/test_quantization.py:16`
- **Description**: The unit tests in `edge/tests/` import `from subsense.data_generator import ...` directly without setting `sys.path`.
- **Impact**: Running `pytest edge/tests` from the workspace root crashes during test collection with `ModuleNotFoundError: No module named 'subsense'`.
- **Recommendation**: Add `sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))` to test files.

### [BUG-EDGE-015] Static Array Memory Allocation Inside Header Files
- **Severity**: LOW
- **File & Line**: `edge/firmware/subsense_gateway_model.h:107-108`, `edge/firmware/subsense_node_model.h:241`
- **Description**: Static buffers (`s_subsense_gw_buf_a`, `s_subsense_node_hidden`, `subsense_gw_w0`) are defined directly in header files without `extern`.
- **Impact**: Multiple translation units including these headers each instantiate private copies of the arrays, unnecessarily duplicating flash and RAM consumption.
- **Recommendation**: Declare them as `extern` in `.h` and define them in a single `.c` compilation unit.

### [BUG-EDGE-016] Unthrottled Packet Bursting in `subsense_wifi_mesh_send`
- **Severity**: LOW
- **File & Line**: `edge/firmware/subsense_wifi_mesh.cpp:278-301`
- **Description**: Multi-fragment messages send all chunks in a tight `for` loop with zero inter-packet delay.
- **Impact**: On ESP32, the WiFi MAC transmit queue can hold only 4-5 packets. Rapid bursts cause `esp_now_send()` to return `ESP_ERR_ESPNOW_NO_MEM`, dropping fragments.
- **Recommendation**: Add a minimal 3-5ms delay between fragment transmissions or monitor the ESP-NOW TX callback.

---



## 4. AI-ML Subsystem Bug Findings

### [BUG-AIML-001] Physical Bounds Configuration Mismatch in `physical_bounds.yaml` Breaking Ingestion Invariant
- **Severity**: HIGH
- **Location**: `ai-ml/config/physical_bounds.yaml:4-8`, `ai-ml/tests/test_canonical_ingest.py:77`, `ai-ml/tests/test_ingestion_validation.py:79, 136, 176`
- **Description**: 
  `ai-ml/config/physical_bounds.yaml` defines:
  ```yaml
  tilt_deg:
    min: -90.0
    max: 90.0
    max_rate_deg_per_sec: 90.0
  ```
  However, the geotechnical specifications and validation test suites assert that tilt angles beyond $\pm 45.0^\circ$ represent physical node inversion/falloff and rate-of-change cannot exceed $5.0^\circ/\text{s}$. As a consequence, running `pytest ai-ml/tests/` triggers 4 test failures (`test_canonical_ingest_tilt_bounds`, `test_validation_rate_limits`, etc.). More critically, deployed nodes that physically detach from borehole anchors or tip past $45^\circ$ are treated as valid strata tilt rather than sensor displacement/fault events.
- **Impact**: Ingestion gate allows corrupt, fallen, or inverted sensor packets into model training and inference pipelines. Four core CI test cases fail out of the box.
- **Recommendation**:
  Update `ai-ml/config/physical_bounds.yaml` to enforce:
  ```yaml
  tilt_deg:
    min: -45.0
    max: 45.0
    max_rate_deg_per_sec: 5.0
  ```

---

### [BUG-AIML-002] Zero Data Fabrication Mandate Violated in Attention Fallback Attribution
- **Severity**: HIGH
- **Location**: `ai-ml/explainability/shap_explainer.py:114`
- **Description**: 
  In `explain_attention()`, when GAT attention weights indicate spatial neighborhood correlation without a dominant single-node feature driver, the fallback code unconditionally writes:
  ```python
  if not contributing_sensors:
      contributing_sensors = ["displacement_mm"]
  ```
  In SubSense hardware deployments, many nodes (such as the standard low-cost wireless sensor node running MPU6050) do not possess displacement or crackmeter transducers. Fabricating `displacement_mm` as the contributing sensor for an accelerometer/gyro-only node violates DGMS safety audit rules and the system's "Zero Data Fabrication" architectural guarantee.
- **Impact**: Generates synthetic, false attribution reports presented to DGMS safety officers, claiming displacement sensor drift on nodes that lack displacement sensors.
- **Recommendation**:
  Cross-reference node capability before assigning fallback attribution:
  ```python
  if not contributing_sensors:
      available = [k for k, v in sensor_availability.items() if v]
      contributing_sensors = [available[0]] if available else ["accelerometer_tilt"]
  ```

---

### [BUG-AIML-003] Premature Dropping of Critical Warning Tier for "ACCELERATING" Creep Regimes
- **Severity**: HIGH
- **Location**: `ai-ml/fusion/decision_engine.py:76`
- **Description**: 
  In the multi-tier safety fusion decision matrix, the warning tier condition checks:
  ```python
  cond_lstm = bool(signals.lstm_regime.strip().upper() == "SUSTAINED")
  ```
  In Fukuzono tertiary creep mechanics, the creep regime transitions from `STABLE` $\rightarrow$ `SUSTAINED` (secondary creep) $\rightarrow$ `ACCELERATING` (tertiary creep leading to imminent slope/roof collapse). Because `cond_lstm` strictly compares against `"SUSTAINED"` via equality, if the LSTM forecaster detects an `ACCELERATING` regime, `cond_lstm` evaluates to `False`! This causes the decision engine to bypass the Warning tier and fail to satisfy Branch C1 Critical escalation requirements.
- **Impact**: The most critical geotechnical failure state (`ACCELERATING` creep) fails the multi-channel conjunction check, potentially suppressing warnings immediately before roof falls.
- **Recommendation**:
  Update the check to recognize all elevated creep regimes:
  ```python
  cond_lstm = bool(signals.lstm_regime.strip().upper() in ("SUSTAINED", "ACCELERATING"))
  ```

---

### [BUG-AIML-004] Out-of-Order Packet Arrival Corrupts Differential Velocity Tracking
- **Severity**: MEDIUM
- **Location**: `ai-ml/ingestion/validator.py:232`
- **Description**: 
  `PhysicalBoundsValidator` tracks differential rates of change using `self._last_readings[node_id] = (curr_timestamp, reading)`. When wireless mesh packets arrive delayed or out of chronological order (e.g. during mesh route re-establishment or after flushing gateway offline buffers), `validator.py` unconditionally updates `self._last_readings[node_id]` with the timestamp of the arriving packet even if it is older than the currently tracked state:
  ```python
  dt = (curr_ts - last_ts).total_seconds()
  if dt <= 0:
      return False, "Non-increasing timestamp"
  self._last_readings[node_id] = (curr_ts, reading)
  ```
  If a stale packet arrives after a valid newer packet, it is rejected, but subsequent packets will be checked against the stale timestamp, distorting velocity calculations.
- **Impact**: Mesh routing latency fluctuations create artificial rate-of-change spikes or freeze velocity tracking.
- **Recommendation**:
  Only update `self._last_readings[node_id]` when `curr_ts > last_ts`.

---

### [BUG-AIML-005] Unhandled Empty Filtered Sensor Set in Anomaly Ensemble Fallback
- **Severity**: MEDIUM
- **Location**: `ai-ml/models/anomaly/ensemble.py:164-171`
- **Description**: 
  In `AnomalyEnsemble.predict()`, feature attribution filters sensor weights against `sensor_availability`:
  ```python
  if sensor_availability is not None:
      filtered_weights = {k: v for k, v in sensor_weights.items() if sensor_availability.get(k, True)}
      if filtered_weights:
          sensor_weights = filtered_weights
  ```
  If all sensors mapped in `sensor_weights` are marked unavailable (`False`), `filtered_weights` evaluates to an empty dictionary `{}`. Because `if filtered_weights:` evaluates to `False`, the code retains the original unfiltered `sensor_weights` and attributes the anomaly to non-existent or faulty channels.
- **Impact**: Defective or offline sensors receive anomaly attribution despite explicit health flags marking them disconnected.
- **Recommendation**:
  Handle the empty availability case explicitly:
  ```python
  if sensor_availability is not None:
      filtered_weights = {k: v for k, v in sensor_weights.items() if sensor_availability.get(k, True)}
      sensor_weights = filtered_weights if filtered_weights else {"uncalibrated_topology": 1.0}
  ```

---

### [BUG-AIML-006] Registered PyTorch Buffer Overwritten by Python Attribute in LSTM Forecaster
- **Severity**: MEDIUM
- **Location**: `ai-ml/forecasting/lstm_model.py:209`
- **Description**: 
  In `MineLSTMForecaster`, `self.quantile_offsets` is registered as a persistent PyTorch buffer during initialization (`self.register_buffer("quantile_offsets", ...)`). However, in the post-calibration step:
  ```python
  self.quantile_offsets = torch.tensor(offsets, dtype=torch.float32)
  ```
  Direct reassignment to `self.quantile_offsets` destroys the registered module buffer and replaces it with a normal instance attribute. Consequently, subsequent calls to `model.state_dict()`, `torch.save()`, or `model.to(device)` omit or fail to transfer the calibrated offsets.
- **Impact**: Quantile calibration offsets are lost upon model serialization, reverting inference to uncalibrated predictions in production serving.
- **Recommendation**:
  Use buffer copy or in-place assignment:
  ```python
  self.quantile_offsets.copy_(torch.tensor(offsets, dtype=torch.float32))
  ```

---

### [BUG-AIML-007] Type Mismatch in Isolation Forest Unfitted Fallback Return
- **Severity**: LOW
- **Location**: `ai-ml/models/anomaly/isoforest.py:62`
- **Description**: 
  When `score_samples()` is called on an unfitted `MineIsolationForest`, the fallback returns:
  ```python
  if not self.is_fitted:
      return np.array([0.1]) if X.ndim == 1 else np.full(len(X), 0.1)
  ```
  For single-sample 1D vector input `X.ndim == 1`, callers (such as ensemble scoring) expect a float scalar (matching standard scikit-learn convention for scalar evaluations). Returning a 1D NumPy array `np.array([0.1])` causes downstream float conversions and logging formatters (`f"{score:.3f}"`) to raise `TypeError: unsupported format string`.
- **Impact**: Single-node prediction calls during cold-start or fallback mode crash with formatting type errors.
- **Recommendation**:
  Return a scalar float when `X.ndim == 1`:
  ```python
  if not self.is_fitted:
      return 0.1 if X.ndim == 1 else np.full(len(X), 0.1)
  ```

---

### [BUG-AIML-008] Hardcoded Synthetic Feature Constants in Real-Time Ingest Pipeline
- **Severity**: LOW
- **Location**: `ai-ml/models/serving/app.py:288-290`
- **Description**: 
  In the FastAPI real-time ingest endpoint (`/api/v1/telemetry/ingest`), the 12-dimensional feature vector assembly contains hardcoded constants:
  ```python
  features_12d[4] = 0.15  # Fixed synthetic displacement rate
  features_12d[10] = float(payload.battery_pct) / 100.0
  features_12d[11] = float(payload.mesh_hop_count) / 3.0
  ```
  Feature index 4 represents `disp_rate_mm_h` according to `features/constants.py`. Overwriting it with a constant `0.15` masks real displacement rates computed by the rolling window buffer, attenuating real-time anomaly detection sensitivity.
- **Impact**: Suppresses rapid displacement spikes during dynamic ground movement in live ingest.
- **Recommendation**:
  Pull displacement velocity directly from the rolling feature pipeline or default to 0.0 if unmeasured.

---

### [BUG-AIML-009] Cascade Desensitization Flaw in Spatio-Temporal Cross-Correlation Engine
- **Severity**: HIGH
- **Location**: `ai-ml/correlation/engine.py:149, 162, 191`
- **Description**: 
  When a node triggers an anomaly, `evaluate()` checks whether any neighboring nodes within $R \le 120\text{m}$ and $\tau \le 45\text{min}$ have an active event (`evt.is_anomaly == True`). When Node 1 triggers first, it has no active neighbors yet, so it is marked isolated and penalized:
  `corroborated_score = raw * 0.25`
  Because `corroborated_score < 0.65`, its recorded event history sets:
  `is_anomaly = bool(corroborated_score >= 0.65 and true_movement)  # Evaluates to False!`
  When Node 2 (50m away) triggers 5 minutes later, it searches for neighboring events with `evt.is_anomaly == True`. Node 1's record is stored with `is_anomaly == False`. Consequently, Node 2 ALSO finds 0 active neighbors and is ALSO penalized with $0.25\times$. Neither node ever validates the other.
- **Impact**: Multi-node ground movement across adjacent borehole arrays fails to correlate, suppressing emergency alerts across the entire cluster.
- **Recommendation**:
  Record `raw_is_anomaly` in `event_history` and re-evaluate prior unconfirmed events in the cluster when a new concordant neighbor triggers.

---

### [BUG-AIML-010] Unhandled Broadcast Shape Mismatch in TinyML Distiller Calibration
- **Severity**: MEDIUM
- **Location**: `ai-ml/edge_firmware/distillation/distill.py:108`
- **Description**: 
  In `TinyMLDistiller.distill()`, calibration data is generated as:
  ```python
  calib_anom = X_train[:40] + np.random.normal(loc=2.0, scale=0.5, size=(40, FEATURE_VECTOR_DIM)).astype(np.float32)
  ```
  If `len(X_train) < 40` (e.g. during small unit tests, test bench calibrations, or virgin site boots), `X_train[:40]` has fewer than 40 rows. Adding a matrix of fixed shape `(40, 12)` raises an unhandled `ValueError: operands could not be broadcast together with shapes (N, 12) (40, 12)`.
- **Impact**: Knowledge distillation crashes when training on datasets with fewer than 40 samples.
- **Recommendation**:
  Dynamically size the noise array:
  ```python
  n_anom = min(40, len(X_train))
  calib_anom = X_train[:n_anom] + np.random.normal(loc=2.0, scale=0.5, size=(n_anom, FEATURE_VECTOR_DIM)).astype(np.float32)
  ```

---

### [BUG-AIML-011] Empty Airflow DAG Declaration Missing Task Operators
- **Severity**: LOW
- **Location**: `ai-ml/dags/weekly_subsense_retraining.py:190-197`
- **Description**: 
  The file defines individual Python worker functions (`extract_negative_samples_task`, `retrain_isolation_forest_task`, etc.) and instantiates `dag = DAG(...)`, but never instantiates `PythonOperator` tasks or wires task dependencies (`t1 >> t2 >> t3...`). When scanned by an Apache Airflow scheduler, the DAG displays 0 tasks and fails to execute any retraining.
- **Impact**: Automated weekly active learning pipeline is non-functional in standard Airflow environments.
- **Recommendation**:
  Wrap all steps in `PythonOperator(dag=dag)` and declare the dependency sequence.

---

### [BUG-AIML-012] Misleading False Alarm Mining State Returned on Missing Feature Vector
- **Severity**: LOW
- **Location**: `ai-ml/active_learning/feedback_api.py:78`
- **Description**: 
  When an operator submits a false alarm label without an associated feature vector (`submission.feature_vector is None`), the sample cannot be ingested into the negative mining repository. However, the JSON response returns:
  ```python
  "is_false_alarm_mined": is_false_alarm,
  "mined_sample_id": mined_sample_id  # None
  ```
  `is_false_alarm` is `True`, so the client receives `"is_false_alarm_mined": True`, despite the sample not being mined.
- **Impact**: UI and operator logs indicate successful sample mining when the sample was silently discarded.
- **Recommendation**:
  Set `"is_false_alarm_mined": bool(mined_sample_id is not None)`.



## 5. Reference AI-ML Subsystem Bug Findings

### [BUG-REFAIML-001] Pydantic Validation Crash on Empty Telemetry List in Node Health Fallback
- **Severity**: HIGH
- **Location**: `reference_aiml/src/ingestion/fault_filter.py:81`, `reference_aiml/src/schemas/sensor_contracts.py:17`
- **Description**: 
  In `SensorFaultFilter.filter_mesh_batch()`, when a node is present in `node_readings_map` but contains an empty list of readings (`readings = []`), the fallback metadata constructor executes:
  ```python
  health = node_health_map.get(
      node_id,
      NodeHealthMetadata(
          node_id=node_id,
          timestamp=readings[-1].timestamp if readings else None,
          battery_voltage=3.3,
          rssi_dbm=-75.0,
      )
  )
  ```
  In `src/schemas/sensor_contracts.py`, `NodeHealthMetadata.timestamp` is defined as `timestamp: datetime = Field(...)` (a required non-null field). Passing `None` raises a Pydantic `ValidationError`, immediately crashing the entire batch ingestion cycle.
- **Impact**: Any node registered without readings aborts batch filtering for all other valid nodes in the mesh.
- **Recommendation**:
  Default `timestamp` to `datetime.now(timezone.utc)` when `readings` is empty:
  ```python
  timestamp=readings[-1].timestamp if readings else datetime.now(timezone.utc)
  ```

---

### [BUG-REFAIML-002] Multi-Node Sequence Length Desynchronization Crash in LSTM Temporal Matrix
- **Severity**: HIGH
- **Location**: `reference_aiml/src/pipeline/inference_pipeline.py:121-131`
- **Description**: 
  During progression forecasting for a spatial zone, the inference pipeline constructs a temporal matrix over all nodes in the cluster:
  ```python
  first_node_readings = valid_readings[cluster_nodes[0]]
  seq_len = len(first_node_readings)
  temporal_matrix = np.zeros((seq_len, 4), dtype=np.float32)

  for step_i in range(seq_len):
      tilts = [valid_readings[nid][step_i].tilt_deg for nid in cluster_nodes]
      vibes = [valid_readings[nid][step_i].vibration_g for nid in cluster_nodes]
      disps = [valid_readings[nid][step_i].displacement_mm for nid in cluster_nodes]
  ```
  If different nodes deliver different buffer lengths (e.g., node 1 has 30 samples, while node 2 has 25 due to wireless packet drops or recent node wake-up), accessing `valid_readings[nid][step_i]` for `step_i >= 25` raises an unhandled `IndexError: list index out of range`.
- **Impact**: Multi-node risk event generation crashes whenever sensor nodes have uneven buffer lengths.
- **Recommendation**:
  Align sequences to minimum common length:
  ```python
  min_len = min(len(valid_readings[nid]) for nid in cluster_nodes)
  if min_len == 0:
      continue
  seq_len = min_len
  ```

---

### [BUG-REFAIML-003] Untrained Randomly-Initialized Neural Weights in Mesh GNN Correlator
- **Severity**: HIGH
- **Location**: `reference_aiml/src/models/mesh_gnn_correlator.py:65-68`
- **Description**: 
  In `MeshGNNCorrelator.__init__()`:
  ```python
  torch.manual_seed(42)
  self.gnn = MeshSpatialGNN(in_features=9, hidden_dim=16, out_dim=8)
  self.gnn.eval()
  ```
  The spatial graph neural network is instantiated with random weights (`xavier_uniform_` and constant biases) and is never loaded from checkpoint weights or trained on historical mine deformation graphs. Its forward pass outputs arbitrary random projections that are combined 50/50 with raw anomaly scores (`0.5 * raw_a + 0.5 * gnn_val`), injecting pseudo-random noise into spatial cluster detection.
- **Impact**: Spatial risk zone demarcation depends on untrained random matrix multiplications rather than true geomechanical graph learning.
- **Recommendation**:
  Load pretrained model weights from disk or replace random forward projections with deterministic graph Laplacian spectral smoothing.

---

### [BUG-REFAIML-004] Inverted North-South Coordinate Orientation in Ordinary Kriging Raster
- **Severity**: MEDIUM
- **Location**: `reference_aiml/src/geostats/ordinary_kriging.py:37, 83, 109-110`
- **Description**: 
  In `OrdinaryKrigingInterpolator.interpolate_raster()`:
  ```python
  ys = np.arange(min_y, max_y + self.grid_resolution_m, self.grid_resolution_m)
  ...
  grid_x, grid_y = np.meshgrid(xs, ys)
  ...
  risk_grid = z_hat.reshape((grid_height, grid_width))
  ```
  `ys` increases from South (`min_y`) to North (`max_y`). In standard geospatial raster conventions (GeoTIFF, Leaflet/Mapbox image overlays, GIS matrices), row 0 corresponds to the top edge (North/`max_y`). Because `risk_grid` is not flipped vertically via `np.flipud()`, row 0 contains the southernmost coordinates, resulting in a vertically mirrored risk surface in GIS maps.
- **Impact**: Subsidence risk heatmaps are displayed upside-down along the North-South axis in GIS viewers.
- **Recommendation**:
  Invert Y indexing or apply `np.flipud()` prior to matrix serialization:
  ```python
  risk_grid = np.flipud(z_hat.reshape((grid_height, grid_width)))
  variance_grid = np.flipud(var_k.reshape((grid_height, grid_width)))
  ```

---

### [BUG-REFAIML-005] Hardcoded Mine Coordinates in InSAR Satellite Cross-Validator
- **Severity**: MEDIUM
- **Location**: `reference_aiml/src/insar/insar_cross_validator.py:63-64, 103-116`
- **Description**: 
  In `InSARCrossValidator.cross_validate()`, coordinates are converted from UTM to geographic coordinates via hardcoded linear approximations:
  ```python
  lat = 23.7915 + (pt_y - 2631700.0) * 0.000009
  lon = 86.4335 + (pt_x - 442450.0) * 0.000010
  ```
  Furthermore, the satellite pass boundary `hatched_polygon_geojson` contains static coordinates fixed to Jharia `[[86.430, 23.788], [86.440, 23.788], ...]`. For any mine deployment outside Jharia (e.g. Raniganj, Singrauli, Korba), the discrepancy markers and hatched overlay polygons are plotted in the wrong coalfield thousands of kilometers away.
- **Impact**: Multi-site InSAR validation is completely inaccurate outside Jharia; overlay polygons cannot be used on non-Jharia sites.
- **Recommendation**:
  Use `pyproj.Transformer` with `utm_epsg` to convert UTM coordinates to WGS84 and construct the polygon dynamically from `bounds_utm`.

---

### [BUG-REFAIML-006] Retraining Buffer Never Emptied Triggering Continuous Retrain Cascade
- **Severity**: MEDIUM
- **Location**: `reference_aiml/src/feedback_loop/feedback_consumer.py:37-40`
- **Description**: 
  When operator feedback events arrive, `FeedbackConsumer.consume_event()` checks:
  ```python
  if len(self._buffer) >= self.retrain_trigger_count:
      if self.on_retrain_callback:
          self.on_retrain_callback(list(self._buffer))
          triggered_retrain = True
  ```
  After triggering the retraining callback at count 30, `self._buffer` is not cleared. Consequently, every single subsequent feedback event (count 31, 32, 33...) triggers retraining again on every event arrival.
- **Impact**: Floods background workers and compute resources with redundant retraining jobs on every operator interaction.
- **Recommendation**:
  Clear the buffer or advance a watermark after firing the callback:
  ```python
  if len(self._buffer) >= self.retrain_trigger_count:
      if self.on_retrain_callback:
          self.on_retrain_callback(list(self._buffer))
          self._buffer.clear()
          triggered_retrain = True
  ```

---

### [BUG-REFAIML-007] Subscripting Builtin Function `any` in Return Type Annotations
- **Severity**: LOW
- **Location**: `reference_aiml/src/tinyml_bridge/edge_reconciler.py:24`, `reference_aiml/src/feedback_loop/feedback_consumer.py:25`
- **Description**: 
  Methods declare return type hints using `Dict[str, any]`:
  ```python
  def record_comparison(self, ...) -> Dict[str, any]:
  def consume_event(self, ...) -> Dict[str, any]:
  ```
  `any` is the Python built-in boolean function, not `typing.Any`. In static analysis and runtime reflection tools, subscripting the built-in function triggers type errors or lint failures.
- **Impact**: Static type checkers fail; runtime type inspection libraries may raise `TypeError: 'builtin_function_or_method' object is not subscriptable`.
- **Recommendation**:
  Import `Any` from `typing` and declare `Dict[str, Any]`.

---

### [BUG-REFAIML-008] Crack Gauge Feature Omitted from Feature Vector Serialization
- **Severity**: LOW
- **Location**: `reference_aiml/src/schemas/sensor_contracts.py:46, 48-58`
- **Description**: 
  `EngineeredFeatureVector` defines `crack_active_ratio: float` as a core geotechnical field. However, `to_feature_list()` serializes only 8 features:
  ```python
  def to_feature_list(self) -> List[float]:
      return [
          self.tilt_mean,
          self.tilt_rate,
          self.tilt_var_short,
          self.tilt_var_long,
          self.vibration_rms,
          self.vibration_peak_ratio,
          self.displacement_delta,
          self.displacement_cum_drift,
      ]
  ```
  `crack_active_ratio` is completely omitted. As a result, anomaly detectors and machine learning models trained on `to_feature_list()` never receive crack gauge signals.
- **Impact**: Tensile crack openings fail to feed tabular anomaly detectors.
- **Recommendation**:
  Include `self.crack_active_ratio` in `to_feature_list()`.



## 6. GIS Subsystem Bug Findings

### [BUG-GIS-001] Disconnected MultiTenantTileCache Instances and Stale Disk Cache Retention
- **Severity**: CRITICAL
- **Location**: `gis/src/api/router_raster.py:59, 101-102`, `gis/src/api/router_tiles.py:18, 55-64`, `gis/src/delivery/tile_cache.py:68-74`
- **Description**: 
  `MultiTenantTileCache` is instantiated separately in two modules:
  - `router_raster.py`: `tile_cache = MultiTenantTileCache()`
  - `router_tiles.py`: `tile_cache = MultiTenantTileCache()`
  Because `MultiTenantTileCache` is not a singleton, when `/api/v1/raster/ingest` runs `tile_cache.invalidate_site_cache()`, it clears its own empty cache dictionary, leaving `router_tiles.py`'s `_mem_cache` untouched.
  More critically, `invalidate_site_cache()` only removes keys from memory:
  ```python
  def invalidate_site_cache(self, tenant_id: str, site_id: str):
      prefix = f"{tenant_id}:{site_id}:"
      keys_to_remove = [k for k in self._mem_cache if k.startswith(prefix)]
      for k in keys_to_remove:
          del self._mem_cache[k]
  ```
  It never deletes the rendered `.png` files from disk! In `router_tiles.py:59`, `get_tile()` checks `if path.exists(): return data`. Even if memory is invalidated, `router_tiles.py` permanently serves the old tile from disk.
- **Impact**: Map tiles are never updated when new Universal Kriging rasters arrive from Layer 4. Web dashboards display frozen, obsolete subsidence heatmaps indefinitely.
- **Recommendation**:
  Convert `MultiTenantTileCache` to a singleton and remove the corresponding filesystem directory tree during `invalidate_site_cache()`:
  ```python
  import shutil
  site_dir = self.base_dir / tenant_id / site_id
  if site_dir.exists():
      shutil.rmtree(site_dir)
  ```

---

### [BUG-GIS-002] Inadequate ETag Keying Allowing False 304 Not Modified Responses
- **Severity**: CRITICAL
- **Location**: `gis/src/api/router_tiles.py:46-53`
- **Description**: 
  The HTTP ETag is computed strictly from query parameters and static SLA constants:
  ```python
  cycle_bucket = int(data_age_seconds // settings.INGESTION_SLA_SECONDS)
  etag = f'W/"{hashlib.md5(f"{tenant_id}:{site_id}:{z}:{x}:{y}:{cycle_bucket}".encode()).hexdigest()}"'
  ```
  The ETag does not include the raster grid version, updated timestamp, or hash of the underlying spatial deformation data. If a client queries tiles using the default `data_age_seconds=12.0`, `cycle_bucket` remains 0. When subsequent telemetry arrives and updates the site grid, the server generates the exact same ETag. When the browser sends `If-None-Match`, `router_tiles.py` responds with `304 Not Modified`, suppressing updated risk tiles in the client UI.
- **Impact**: Browsers and mobile GIS clients refuse to refresh heatmap tiles after ground movement occurs.
- **Recommendation**:
  Incorporate the active raster's `updated_at` timestamp or hash into the ETag calculation:
  ```python
  updated_ts = active_grid["updated_at"].isoformat() if active_grid else "base"
  etag = f'W/"{hashlib.md5(f"{tenant_id}:{site_id}:{z}:{x}:{y}:{updated_ts}".encode()).hexdigest()}"'
  ```

---

### [BUG-GIS-003] Zero Data Fabrication Mandate Violated in Risk Zone Sensor Attribution
- **Severity**: HIGH
- **Location**: `gis/src/risk_zones/zone_tracker.py:118`
- **Description**: 
  When associating sensor nodes with risk polygons, `ZoneTracker.process_cycle()` specifies:
  ```python
  props = RiskZoneProperties(
      ...
      affected_node_ids=affected_nodes or [f"SS-{self.site_id}-N042", f"SS-{self.site_id}-N043"],
      ...
  )
  ```
  If `affected_nodes` is empty (e.g., an unmonitored goaf void or satellite InSAR discrepancy basin where no physical ground sensors exist), the code fabricates fake sensor IDs (`SS-<site>-N042` and `SS-<site>-N043`). This directly violates DGMS audit guidelines and the project's strict Zero Data Fabrication architecture.
- **Impact**: Fabricated sensor IDs are embedded in official statutory GeoJSON risk collections and dispatched to alerting services.
- **Recommendation**:
  Leave `affected_node_ids` empty when no sensors are located within the zone:
  ```python
  affected_node_ids=affected_nodes if affected_nodes else []
  ```

---

### [BUG-GIS-004] Thread Concurrency Race Condition in In-Memory Tile Cache Eviction
- **Severity**: HIGH
- **Location**: `gis/src/delivery/tile_cache.py:37-41`
- **Description**: 
  `MultiTenantTileCache._mem_cache` is a standard Python dictionary accessed without a mutex/lock. In `put_tile()`:
  ```python
  if len(self._mem_cache) >= self.max_memory_tiles:
      oldest_key = min(self._mem_cache, key=lambda k: self._mem_cache[k][1])
      del self._mem_cache[oldest_key]
  ```
  When Mapbox, Cesium, or Leaflet loads a grid of 16-32 tiles in parallel over HTTP/2, multiple asynchronous request worker threads execute `min(self._mem_cache, ...)` while other threads insert new entries. This triggers `RuntimeError: dictionary changed size during iteration`, crashing tile delivery requests.
- **Impact**: High concurrency tile requests fail intermittently with HTTP 500 internal server errors.
- **Recommendation**:
  Guard all reads and writes to `_mem_cache` with `threading.Lock()` or use an `OrderedDict` with atomic `popitem(last=False)`.

---

### [BUG-GIS-005] Live Risk Zone Endpoint Completely Bypasses Ingested Raster and Contour Extraction
- **Severity**: HIGH
- **Location**: `gis/src/api/router_zones.py:27-51`
- **Description**: 
  The primary production risk zone endpoint `/api/v1/zones/{tenant_id}/{site_id}/live` contains hardcoded mock geometry:
  ```python
  # Synthetic candidate isoline polygons in UTM for demonstration
  poly_crit = Polygon([(442400, 2631600), (442550, 2631620), ...])
  poly_warn = Polygon([(442300, 2631500), (442650, 2631530), ...])
  poly_advi = Polygon([(442200, 2631400), (442750, 2631450), ...])
  ```
  The endpoint never queries `raster_state` and never invokes `ContourExtractor.extract_isolines()`. Regardless of what data is ingested into Layer 5, this endpoint returns the exact same hardcoded polygons located in Jharia.
- **Impact**: Live risk zone boundaries are completely detached from real telemetry and geostatistical models.
- **Recommendation**:
  Retrieve the active raster from `raster_state.get_grid(site_id)` and pass it through `ContourExtractor.extract_isolines()` before feeding `tracker.process_cycle()`.

---

### [BUG-GIS-006] Open Contour Boundary Distortion and Matplotlib Thread Concurrency Risk
- **Severity**: MEDIUM
- **Location**: `gis/src/risk_zones/contour_extractor.py:45-75`
- **Description**: 
  In `ContourExtractor.extract_isolines()`:
  1. `ax.contour()` extracts open contour lines rather than closed regions. When a subsidence depression intersects the grid boundary, `path.to_polygons()` joins the line's start and end points directly, generating invalid chord artifacts cutting across the interior.
  2. `matplotlib.use('Agg')` is never invoked, and `plt.subplots()` is called inside request handling threads. Without the headless Agg backend, matplotlib raises `UserWarning: Starting a Matplotlib GUI outside of the main thread will likely fail` and can crash in multi-threaded serving.
- **Impact**: Degraded contour geometry accuracy at raster borders and server crashes on non-main worker threads.
- **Recommendation**:
  Set `matplotlib.use('Agg')` at module load and use `ax.contourf()` or clamp open contour paths along grid edges.

---

### [BUG-GIS-007] Disconnected Mock SSE Stream Emitting Constant Emergency Evacuations
- **Severity**: MEDIUM
- **Location**: `gis/src/api/router_stream.py:23-48`
- **Description**: 
  The Server-Sent Events (SSE) push endpoint `/api/v1/stream/{tenant_id}/{site_id}/events` generates static hardcoded payloads:
  ```python
  payload = {
      ...
      "critical_ttc_hours": 1.8
  }
  if payload["critical_ttc_hours"] <= 2.0:
      alert_payload = {
          "event_type": "EMERGENCY_TTC_WARNING",
          ...
      }
      yield f"event: emergency_alert\ndata: {json.dumps(alert_payload)}\n\n"
  ```
  Because `critical_ttc_hours` is hardcoded to `1.8`, an emergency evacuation warning is pushed every 15 seconds to all connected clients, regardless of actual site safety status.
- **Impact**: Production dashboards receive continuous false emergency alerts over SSE.
- **Recommendation**:
  Connect the SSE generator to real-time events published by `raster_state` or `spatial_repo`.

---

### [BUG-GIS-008] Potential ZeroDivisionError in Surface DEM Mesh Generation
- **Severity**: MEDIUM
- **Location**: `gis/src/digital_twin/dem_draper.py:49-50`
- **Description**: 
  In `generate_surface_dem_mesh()`:
  ```python
  u = (x_val - min_x) / (max_x - min_x)
  v = (y_val - min_y) / (max_y - min_y)
  ```
  If degenerate bounds where `min_x == max_x` or `min_y == max_y` are passed in `bounds_utm`, Python raises an unhandled `ZeroDivisionError: float division by zero`.
- **Impact**: API crash on invalid or degenerate bounding box inputs.
- **Recommendation**:
  Validate `max_x > min_x` and `max_y > min_y` and add `max(1e-6, max_x - min_x)` safeguards.

---

### [BUG-GIS-009] Modulo 26 Letter Wraparound Producing Risk Zone ID Collisions
- **Severity**: LOW
- **Location**: `gis/src/risk_zones/zone_tracker.py:84-85`
- **Description**: 
  `ZoneTracker` generates zone letter codes using:
  ```python
  letter_code = letters[(idx - 1) % len(letters)]
  zone_id = f"ZONE-{self.site_id}-{letter_code}"
  ```
  Once more than 26 risk zones have been created over time, `(idx - 1) % 26` wraps around to 'A'. If zone 'A' is still active, the new zone overwrites the prior zone in `self.prior_zones` and clashes with active alert tracking.
- **Impact**: Zone tracking identifier instability after 26 zones.
- **Recommendation**:
  Use multi-letter or numeric suffixes (`A`, `B`, ... `Z`, `AA`, `AB` or `Z01`, `Z02`).

---

### [BUG-GIS-010] Unhandled MultiPolygon Geometry in Spatial Viewport Query
- **Severity**: LOW
- **Location**: `gis/src/delivery/postgis_repository.py:66`
- **Description**: 
  `query_zones_in_viewport()` parses polygon coordinates with:
  ```python
  coords = feature.geometry.coordinates[0]
  poly = Polygon(coords)
  ```
  If a risk zone is represented as a `MultiPolygon` or contains interior boundary rings (donut holes), indexing `coordinates[0]` extracts an inner ring or raises `ValueError: A linearring requires at least 4 coordinates`.
- **Impact**: Viewport spatial queries fail when complex multi-part risk polygons are present.
- **Recommendation**:
  Use `shapely.geometry.shape(feature.geometry.model_dump())` to safely construct Shapely geometries.



## 7. Alerting Subsystem Bug Findings

### [BUG-ALERT-001] Missing Delivery Persistence After Concurrent Dispatch Completion
- **Severity**: CRITICAL
- **Location**: `alerting/backend/src/channels/dispatcher.ts:216-222`, `alerting/backend/src/db/repository.ts:301-319`
- **Description**: 
  In `dispatch_concurrent()`:
  ```typescript
  // Save initial Queued records to repository
  await repository.saveDeliveries(deliveries);

  // Execute all channel adapters concurrently
  await Promise.allSettled(tasks);

  return deliveries;
  ```
  `repository.saveDeliveries(deliveries)` is called *before* the asynchronous adapter tasks complete, when all records have `delivery_status: DeliveryStatus.Queued`.
  As tasks finish, each task mutates its local in-memory object (`deliveryRecord.delivery_status = res.status`), but `repository.updateDelivery()` or a secondary batch save is NEVER invoked after `Promise.allSettled(tasks)`.
  In a real PostgreSQL database with Prisma, the rows in table `AlertDelivery` remain permanently in status `'Queued'`.
- **Impact**: Database delivery audit logs show 100% of alerts indefinitely stuck in `'Queued'`, creating false non-compliance records during DGMS statutory audits.
- **Recommendation**:
  Update delivery records in the database after `Promise.allSettled(tasks)` completes:
  ```typescript
  await Promise.allSettled(tasks);
  for (const d of deliveries) {
    await repository.updateDelivery(d.delivery_id, {
      delivery_status: d.delivery_status,
      delivered_at: d.delivered_at,
      error: d.error
    });
  }
  ```

---

### [BUG-ALERT-002] Default-Enabled Termux SSH Triggering 6-Second Connection Hangs and Test Timeouts
- **Severity**: CRITICAL
- **Location**: `alerting/backend/src/channels/adapters/sms.ts:28-35`
- **Description**: 
  In `PrimarySmsAdapter.send()`:
  ```typescript
  if (process.env.ENABLE_TERMUX_SMS !== 'false' && recipient.startsWith('+')) {
    const cmd = `ssh -p ${port} -o StrictHostKeyChecking=no -o ConnectTimeout=6 ${host} "termux-sms-send ...`;
    exec(cmd, ...);
  }
  ```
  `process.env.ENABLE_TERMUX_SMS !== 'false'` evaluates to `true` whenever `ENABLE_TERMUX_SMS` is unset. In test runners and standard server deployments where no Android Termux SSH daemon is running on port 8022, `ssh` hangs attempting to connect for 6 seconds (`ConnectTimeout=6`). Because Jest's default test timeout is 5000ms, this causes unit and integration tests (`tests/api.test.ts`, `tests/feedback-retract.test.ts`) to fail with timeout errors.
- **Impact**: Test suite failures in standard CI/CD environments; 6-second latency spikes in API endpoints when processing SMS dispatches to phone numbers starting with `+`.
- **Recommendation**:
  Default Termux SMS to disabled unless explicitly opted in:
  ```typescript
  if (process.env.ENABLE_TERMUX_SMS === 'true' && recipient.startsWith('+')) {
  ```

---

### [BUG-ALERT-003] Database Crash on Duplicate Feedback Due to Hardcoded Empty `feedback_id`
- **Severity**: HIGH
- **Location**: `alerting/backend/src/api/routes/alerts.ts:177`, `alerting/backend/src/db/repository.ts:413`
- **Description**: 
  In `alertsRouter.post('/:id/feedback')`:
  ```typescript
  const feedback = await repository.createFeedback({
    feedback_id: '',
    alert_id: alertId,
    operator_id,
    verdict,
    notes: notes || null,
    feedback_hash: feedbackHash,
    submitted_at: new Date()
  });
  ```
  `feedback_id` is passed as an empty string `''`.
  In `repository.ts:413`, the database insertion sets:
  ```typescript
  const created = await prisma.alertFeedback.create({
    data: {
      feedback_id: feedback.feedback_id, // ''
      ...
    }
  });
  ```
  When the first feedback verdict is recorded, it succeeds with `feedback_id = ''`. When any subsequent feedback verdict is submitted, PostgreSQL throws a fatal primary key unique constraint error (`Unique constraint failed on the fields: (feedback_id)`), returning HTTP 500.
- **Impact**: Only one feedback verdict can ever be submitted in a production database deployment; all subsequent feedback submissions crash.
- **Recommendation**:
  Generate a UUID if `feedback_id` is missing or empty:
  ```typescript
  feedback_id: feedback.feedback_id || randomUUID(),
  ```

---

### [BUG-ALERT-004] Double Siren Actuation for Edge Autonomous Critical Alerts
- **Severity**: HIGH
- **Location**: `alerting/backend/src/rule-engine/index.ts:72-78, 140-146`, `alerting/backend/src/models/types.ts:158`
- **Description**: 
  In `on_new_risk_event()`:
  ```typescript
  // Step 7: Trigger on-ground siren autonomously
  if (severity === AlertSeverity.Critical && event.source === AlertSource.Edge) {
    await sirenActuator.send(alert, 'on_ground_local_siren');
  }

  // Step 8: Dispatch notifications according to severity channel matrix
  const channels = SEVERITY_CHANNEL_MATRIX[severity];
  await dispatch_concurrent(alert, channels);
  ```
  `SEVERITY_CHANNEL_MATRIX[AlertSeverity.Critical]` explicitly contains `DeliveryChannel.Siren`. Inside `dispatch_concurrent()`, `sirenActuator.send()` is invoked a second time. The exact same duplication exists in the telemetry merge escalation path (lines 72-78).
- **Impact**: Hardware sirens and strobe actuators are triggered twice in rapid succession; duplicate delivery records are logged in database tables.
- **Recommendation**:
  Exclude `DeliveryChannel.Siren` from `dispatch_concurrent` if it was already triggered in Step 7, or deduplicate channel dispatch.

---

### [BUG-ALERT-005] Uncancelled Async Operations on Circuit Breaker Timeout
- **Severity**: HIGH
- **Location**: `alerting/backend/src/channels/circuit-breaker.ts:75-88`
- **Description**: 
  In `CircuitBreaker.executeWithTimeout()`:
  ```typescript
  return await Promise.race([action(), timeoutPromise]);
  ```
  When `timeoutPromise` rejects after `timeoutMs` (8000ms), `action()` is never cancelled or aborted via an `AbortController`. The primary network request continues executing in the background, consuming sockets and memory while the secondary provider has already been dispatched.
- **Impact**: Socket descriptor leaks and duplicate out-of-order delivery dispatches when high-latency primary networks recover.
- **Recommendation**:
  Pass an `AbortSignal` into `action()` and invoke `abort()` in `finally` if the timeout fires.

---

### [BUG-ALERT-006] Aggressive Viewport Snapping in Leaflet MineMap on Every Telemetry Update
- **Severity**: MEDIUM
- **Location**: `alerting/frontend/src/components/Map.tsx:152-154`
- **Description**: 
  In `MineMap`:
  ```typescript
  if (zones.length > 0 && bounds.isValid()) {
    mapInstanceRef.current.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 });
  }
  ```
  The effect hook re-runs whenever `activeAlerts` or `activeSirenZoneId` changes. Every incoming WebSocket message or polling cycle triggers `fitBounds()`, forcibly resetting the map view and zoom level while an operator is attempting to pan and inspect a specific sector.
- **Impact**: Severe UX frustration; safety officers cannot zoom into specific borehole sensors without the viewport being continually reset.
- **Recommendation**:
  Only call `fitBounds()` on initial map load or when the selected tenant/zone filter explicitly changes.

---

### [BUG-ALERT-007] Hardcoded Backend API and WebSocket URLs in Frontend App
- **Severity**: MEDIUM
- **Location**: `alerting/frontend/src/App.tsx:17-18`
- **Description**: 
  The frontend application declares:
  ```typescript
  const API_BASE = 'http://localhost:3000/api/v1';
  const WS_URL = 'ws://localhost:3000/ws/alerts';
  ```
  These values are hardcoded and do not inspect `window.location.host` or Vite environment variables (`import.meta.env.VITE_API_URL`).
- **Impact**: The frontend fails to connect when deployed behind reverse proxies, LAN subnets, Docker, or staging domains.
- **Recommendation**:
  Use relative paths or environment variables:
  ```typescript
  const API_BASE = import.meta.env.VITE_API_BASE || `${window.location.origin}/api/v1`;
  const WS_URL = import.meta.env.VITE_WS_URL || `ws://${window.location.host}/ws/alerts`;
  ```

---

### [BUG-ALERT-008] Redundant Double Persistence of Delivery Records in Re-Evaluation Sweep
- **Severity**: LOW
- **Location**: `alerting/backend/src/rule-engine/reevaluation.ts:47-48`
- **Description**: 
  In `reevaluate_single_alert()`:
  ```typescript
  const deliveries = await notification_dispatcher.dispatch_concurrent(saved, criticalChannels);
  await repository.saveDeliveries(deliveries);
  ```
  `dispatch_concurrent()` already internally invokes `await repository.saveDeliveries(deliveries)` at line 217. Calling `repository.saveDeliveries()` again causes duplicate rows to be inserted into `prisma.alertDelivery`.
- **Impact**: Duplicate delivery rows clutter database tables for auto-escalated re-evaluation events.
- **Recommendation**:
  Remove the redundant call to `repository.saveDeliveries(deliveries)` in `reevaluation.ts`.



## 8. Dashboard & BFF Gateway Subsystem Bug Findings

### [BUG-DASH-001] Complete Authentication and MFA Bypass via Insecure Header Fallback
- **Severity**: CRITICAL
- **Location**: `dashboard/services/bff-gateway/src/app.ts:49-65`
- **Description**: 
  In the Fastify global `onRequest` authentication interceptor:
  ```typescript
  } else {
    // Support tenant header or test role header for developer convenience
    const roleHeader = request.headers["x-user-role"] as string;
    const tenantHeader = request.headers["x-tenant-id"] as string;
    const userHeader = request.headers["x-user-id"] as string;

    if (roleHeader) {
      (request as any).userSession = {
        userId: userHeader || "USR-OP-8492",
        email: "operator.ecl@subsense.gov.in",
        name: "Rajesh Kumar",
        role: roleHeader,
        tenantId: tenantHeader || "OPCO-ECL-01",
        jurisdictionId: "JUR-DGMS-EAST",
        mfaVerified: true,
      };
    }
  }
  ```
  This backdoor exists in production code without any `NODE_ENV === "development"` or test environment guard. Any unauthenticated client can send arbitrary HTTP requests with `x-user-role: dgms_regulator` or `x-user-role: site_admin`, and the server automatically fabricates an active session with full privileges and `mfaVerified: true`.
- **Impact**: Total authorization compromise; any external attacker can read all tenant mine data, provision infrastructure, and silence emergency sirens.
- **Recommendation**:
  Delete the header-based session fabrication or strictly guard it behind `process.env.NODE_ENV === "test"`.

---

### [BUG-DASH-002] Unauthenticated SSH Gateway Configuration Leading to Remote Code Execution (RCE)
- **Severity**: CRITICAL
- **Location**: `dashboard/services/bff-gateway/src/routes/sms-contacts.ts:113-121`, `dashboard/services/bff-gateway/src/notifications/termux-sms.ts:96-103, 125`
- **Description**: 
  The endpoint `POST /api/v1/sms/config` has zero authentication or authorization checks. Any user can update `TermuxSmsService.host`, `port`, `user`, or `password`.
  In `TermuxSmsService.sendSms()`:
  ```typescript
  const target = this.user ? `${this.user}@${this.host}` : this.host;
  ...
  const cmd = `ssh -p ${this.port} ${keyFlag} -o StrictHostKeyChecking=no -o ConnectTimeout=10 ${target} "termux-sms-send -n ${sanitizedPhone} '${escapedMsg}'"`;
  ...
  exec(cmd, { env, timeout: 20000 }, ...);
  ```
  Because `target` is constructed from unvalidated `this.host` and `this.user`, an attacker can send a request with `{"host": "127.0.0.1; whoami > rce.txt"}`. When `sendSms` or `/api/v1/sms/send-test` executes, the shell command injects and executes arbitrary OS commands with the privileges of the Node.js server.
- **Impact**: Full server takeover and arbitrary remote code execution via unauthenticated HTTP API calls.
- **Recommendation**:
  Enforce strict RBAC authentication on `/api/v1/sms/config`, sanitize IP/hostname inputs against regex `^[a-zA-Z0-9.-]+$`, and use `execFile` with an argument array instead of shell interpolation via `exec`.

---

### [BUG-DASH-003] Cross-Tenant Data Leakage in Site Provisioning Endpoint
- **Severity**: CRITICAL
- **Location**: `dashboard/services/bff-gateway/src/routes/provisioning.ts:119-136`
- **Description**: 
  In `GET /api/v1/tenants/:tenantId/sites`:
  ```typescript
  const session = (request as any).userSession as UserSession;
  const { tenantId } = request.params;
  const isRegulator = session?.role === "dgms_regulator";

  return await withTenantScope(
    {
      tenantId: isRegulator ? null : tenantId,
      userId: session?.userId || "USR-OP-8492",
      isRegulator,
    },
    async (client) => {
      const res = await client.query("SELECT * FROM sites ORDER BY created_at DESC;");
      return { sites: res.rows };
    }
  );
  ```
  The handler sets PostgreSQL's current tenant session to `request.params.tenantId` without verifying that the authenticated user's `session.tenantId` matches the requested `tenantId`. An operator from Coalfield A can access Coalfield B's entire private infrastructure, CAD boundaries, and gateway credentials by requesting `/api/v1/tenants/tenant-B/sites`.
- **Impact**: Complete breakdown of multi-tenant data isolation and breach of statutory concession confidentiality.
- **Recommendation**:
  Verify tenant ownership:
  ```typescript
  if (!isRegulator && session.tenantId !== tenantId) {
    return reply.status(403).send({ error: "Forbidden: Cross-tenant access denied" });
  }
  ```

---

### [BUG-DASH-004] Hardcoded Static KPI Counts in Operations Cockpit View
- **Severity**: HIGH
- **Location**: `dashboard/apps/web-dashboard/src/views/OperationsCockpit.tsx:84-89`
- **Description**: 
  In the primary operator dashboard view `OperationsCockpit`:
  ```tsx
  {/* Under Sensor Table: 4 Compact KPI Cards */}
  <SensorSummaryKpis
    totalNodes={24}
    healthyNodes={21}
    atRiskNodes={2}
    offlineNodes={1}
  />
  ```
  The values for total, healthy, at-risk, and offline nodes are hardcoded integers (24, 21, 2, 1). They are completely decoupled from the live `sensors` state array and telemetry stream.
- **Impact**: Operators and inspectors see false, static hardware health statistics regardless of how many sensor nodes are actually active or failing in the mine.
- **Recommendation**:
  Compute KPIs dynamically from the `sensors` array:
  ```tsx
  const total = sensors.length;
  const healthy = sensors.filter(s => s.status === "online").length;
  const atRisk = sensors.filter(s => s.status === "warning").length;
  const offline = sensors.filter(s => s.status === "offline" || s.status === "stale").length;
  ```

---

### [BUG-DASH-005] Role Inconsistency Blocking Mine Operators from Manually Triggering Evacuation Sirens
- **Severity**: HIGH
- **Location**: `dashboard/services/bff-gateway/src/routes/alerts.ts:286`, `dashboard/services/bff-gateway/src/auth/service.ts:39-42`
- **Description**: 
  In `POST /api/v1/siren/trigger`:
  ```typescript
  if (session && session.role !== "mine_operator") {
    return reply.status(403).send({ error: "Forbidden: Only Mine Operators can manually trigger sirens" });
  }
  ```
  In `auth/service.ts`, JWT verification normalizes roles:
  ```typescript
  let role = (decoded.role || "safety_officer") as UserRole;
  if (decoded.role === "mine_safety_officer") role = "safety_officer" as UserRole;
  ```
  Because the system uses `"safety_officer"` as the standard operator role, checking strictly for `"mine_operator"` causes all safety officers to be rejected with HTTP 403 when attempting to manually sound evacuation sirens during emergencies.
- **Impact**: Safety officers on duty are blocked from manually activating emergency evacuation sirens through the web dashboard.
- **Recommendation**:
  Allow both `"safety_officer"` and `"mine_operator"`:
  ```typescript
  if (session && !["mine_operator", "safety_officer"].includes(session.role)) {
  ```

---

### [BUG-DASH-006] Phantom S3 Report Downloads Delivering HTTP 404
- **Severity**: HIGH
- **Location**: `dashboard/services/bff-gateway/src/routes/regulator.ts:119-130, 185-188`
- **Description**: 
  In `POST /api/v1/regulator/reports/generate`:
  `TenantS3Storage.generatePresignedUrl()` is called to construct a presigned URL string for `filename`. However, the PDF compilation and S3 upload are never implemented. The endpoint records `status: "ready"` and `file_size_bytes: 421950` (hardcoded fake size), returning the download URL to the client.
- **Impact**: Regulators clicking the download link receive an immediate HTTP 404 NoSuchKey from Amazon S3 / MinIO.
- **Recommendation**:
  Invoke a PDF report generation worker to compile the document and upload it to S3 before marking the report status as `"ready"`.

---

### [BUG-DASH-007] Mocked Mesh Health Endpoint Returning Static Topology
- **Severity**: HIGH
- **Location**: `dashboard/services/bff-gateway/src/routes/mesh.ts:56-157`
- **Description**: 
  `GET /api/v1/mesh/health` returns hardcoded static arrays for nodes (`GW-ECL-JH-007`, `SS-PANEL7-N042` to `N045`) and links. Although `withTenantScope` is imported, it is never executed to query the `nodes` table or gateway status from the database.
- **Impact**: Mesh health and battery life decay curves are non-functional simulations rather than live telemetry views.
- **Recommendation**:
  Query the active nodes and telemetry store from PostgreSQL to assemble the real mesh graph.

---

### [BUG-DASH-008] Client Hostname Fallback Disconnecting WebSockets on Non-Localhost Access
- **Severity**: MEDIUM
- **Location**: `dashboard/apps/web-dashboard/src/services/socket.ts:114-116`
- **Description**: 
  In `WebSocketService.connect()`:
  ```typescript
  const host = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? `${window.location.hostname}:3001`
    : window.location.host;
  ```
  When accessing the dashboard from a mobile device or LAN test bench (e.g. `http://192.168.1.50:5173`), `window.location.hostname` is `192.168.1.50`. Because it is not `"localhost"`, `host` resolves to `window.location.host` (`192.168.1.50:5173` — the frontend Vite dev server). The WebSocket tries to connect to Vite instead of the BFF gateway on port 3001, failing to establish the live data stream.
- **Impact**: Live telemetry streaming and real-time alerts fail on all non-localhost devices.
- **Recommendation**:
  Use `import.meta.env.VITE_WS_URL` or dynamically swap the port to `3001` for IP-based URLs.

---

### [BUG-DASH-009] Plain-Text Password Script Written to Shared OS Temporary Directory
- **Severity**: MEDIUM
- **Location**: `dashboard/services/bff-gateway/src/notifications/termux-sms.ts:75-79`
- **Description**: 
  `TermuxSmsService.getAskpassScript()` creates `subsense_askpass.bat` (or `.sh`) in `os.tmpdir()` containing `@echo ${this.password}`. The file is never deleted after SSH execution. In multi-user operating systems or shared container environments, any process can read the temporary file to steal SSH credentials.
- **Impact**: Credential exposure of the SMS gateway host password in the OS temporary directory.
- **Recommendation**:
  Use SSH public key authentication (`~/.ssh/id_ed25519`) exclusively and avoid writing plain-text passwords to disk.

---

### [BUG-DASH-010] Redundant Duplicate Directory `new dasboard` with Typo
- **Severity**: LOW
- **Location**: `new dasboard/`
- **Description**: 
  The root repository contains a full copy of `dashboard/` inside `new dasboard/` (with a spelling error in "dasboard"). Having two identical codebases leads to developer divergence, broken build paths, and wasted storage.
- **Impact**: Repository clutter and danger of engineers modifying the wrong dashboard directory.
- **Recommendation**:
  Consolidate all changes into `dashboard/` and delete `new dasboard/`.

---

### [BUG-DASH-011] Potential Division by Zero in Sensor Summary KPIs
- **Severity**: LOW
- **Location**: `dashboard/apps/web-dashboard/src/components/SensorSummaryKpis.tsx:17-19`
- **Description**: 
  `const healthyPct = ((healthyNodes / totalNodes) * 100).toFixed(1);`
  If `totalNodes` is passed as 0 (e.g. during site initialization before sensors are provisioned), the expression evaluates to `NaN%`.
- **Impact**: UI visual glitch displaying `(NaN%)` on unpopulated mine panels.
- **Recommendation**:
  Guard with `totalNodes > 0 ? ... : "0.0"`.

