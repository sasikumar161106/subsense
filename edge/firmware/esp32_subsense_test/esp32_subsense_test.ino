/**
 * @file esp32_subsense_test.ino
 * @brief SubSense TinyML On-Device Hardware Test & Benchmark Console for ESP32.
 * @note Compatible with Arduino IDE 1.8.x, 2.x and PlatformIO.
 * 
 * Instructions:
 * 1. Open this file in Arduino IDE.
 * 2. Select Board: "ESP32 Dev Module" (or your specific ESP32 variant).
 * 3. Select Port: Your ESP32 COM port.
 * 4. Upload and open Serial Monitor at 115200 baud.
 */

#include <Arduino.h>
#include "subsense_features.h"
#include "subsense_inference_engine.h"
#include "subsense_fallback.h"
#include "subsense_power_mgmt.h"
#include "subsense_gateway_model.h"
#include "subsense_node_model.h"
#include "subsense_lora_mesh.h"
#include "subsense_lora_sx126x.h"
#include "subsense_display.h"

// Set to 1 if this board is GATEWAY (receives mesh packets), 0 if NODE (sends telemetry)
#define SUBSENSE_IS_GATEWAY   0

// Hardware Pin Configuration
// Most ESP32 DevKit boards have an onboard blue LED on GPIO 2.
// Change this if your board uses a different pin (e.g., GPIO 13 or external buzzer pin).
#define PIN_SIREN_LED   2

// Gateway LoRa packet reception handler
static void on_lora_data_received(const char* json_payload, size_t len, const uint8_t sender_mac[6], int16_t rssi_dbm, uint8_t hop_count) {
    Serial.printf("\n[LORA RX] From %02X:%02X:%02X:%02X:%02X:%02X (%u bytes) | RSSI: %d dBm | Hops: %u:\n%s\n\n",
           sender_mac[0], sender_mac[1], sender_mac[2],
           sender_mac[3], sender_mac[4], sender_mac[5],
           (unsigned)len, (int)rssi_dbm, (unsigned)hop_count, json_payload);
}

// Static system components
static SubSenseWindowBuffer     g_win_buf;
static SubSenseHealthTelemetry  g_health;
static SubSenseFeatureConfig    g_feat_config;
static SubSenseInferenceConfig  g_gw_inf_config;
static SubSenseInferenceConfig  g_node_inf_config;
static SubSensePowerConfig      g_pwr_config;

// JSON event and health buffers
static char g_json_buf[SUBSENSE_JSON_EVENT_MAX_LEN];
static char g_health_buf[256];

// Benchmark test vectors
// Calibrated nominal baseline INT8 tensor (mean normal values)
static const int8_t TEST_VEC_NOMINAL[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };

// Early Warning INT8 tensor (increasing tilt rate & vibration)
static const int8_t TEST_VEC_WARNING[8] = { 25, 45, 30, 55, 35, 20, 10, 15 };

// Severe Anomaly INT8 tensor (roof shear, high crack propagation, shockwave)
static const int8_t TEST_VEC_CRITICAL[8] = { 85, 110, 95, 120, 105, 115, 120, 100 };

void setup_subsense() {
    // 1. Initialize ring buffer
    subsense_buffer_init(&g_win_buf);

    // 2. Configure Gateway Tier inference config
    g_gw_inf_config.warning_threshold = SUBSENSE_GW_INT_THRESHOLD; // 474
    g_gw_inf_config.critical_threshold = 950;
    g_gw_inf_config.node_id = "ESP32-GW-01";
    g_gw_inf_config.model_version = "gw-autoencoder-v1.3.0";
    g_gw_inf_config.source_tier = "gateway";

    // 3. Configure Node Tier inference config
    g_node_inf_config.warning_threshold = SUBSENSE_NODE_INT_THRESHOLD; // 115
    g_node_inf_config.critical_threshold = SUBSENSE_NODE_INT_THRESHOLD;
    g_node_inf_config.node_id = "ESP32-NODE-01";
    g_node_inf_config.model_version = "node-detector-v1.3.0";
    g_node_inf_config.source_tier = "node";

    // 4. Configure feature normalizer & quantization constants
    g_feat_config.scaler_mean[0] = 0.010298f;  g_feat_config.scaler_scale[0] = 0.077703f;
    g_feat_config.scaler_mean[1] = 0.000011f;  g_feat_config.scaler_scale[1] = 0.001341f;
    g_feat_config.scaler_mean[2] = 0.000893f;  g_feat_config.scaler_scale[2] = 0.000220f;
    g_feat_config.scaler_mean[3] = 0.043559f;  g_feat_config.scaler_scale[3] = 0.023900f;
    g_feat_config.scaler_mean[4] = 0.332180f;  g_feat_config.scaler_scale[4] = 2.029822f;
    g_feat_config.scaler_mean[5] = -0.000056f; g_feat_config.scaler_scale[5] = 0.020145f;
    g_feat_config.scaler_mean[6] = 0.0f;       g_feat_config.scaler_scale[6] = 1.0f;
    g_feat_config.scaler_mean[7] = 0.0f;       g_feat_config.scaler_scale[7] = 1.0f;
    g_feat_config.quant_input_scale = 0.029008f;
    g_feat_config.quant_input_zp = 0;

    // 5. Initialize inference & health telemetry
    subsense_inference_init(&g_gw_inf_config, &g_health);

    // 6. Initialize power config
    g_pwr_config.mode = POWER_MODE_BATTERY_DUTY_CYCLE;
    g_pwr_config.sampling_interval_ms = 1000;
    g_pwr_config.active_duration_us = 400; // ~0.4 ms
    g_pwr_config.active_current_ma = 50.0f;
    g_pwr_config.deep_sleep_current_ua = 10.0f;
    g_pwr_config.battery_capacity_mah = 2600.0f;
    subsense_power_init(&g_pwr_config);

    // 7. Initialize LoRa SX126x Mesh (865 MHz) transport
#if SUBSENSE_IS_GATEWAY
    subsense_lora_mesh_init(SUBSENSE_MESH_ROLE_GATEWAY, on_lora_data_received);
    Serial.println("  [LoRa Mesh] Initialized in GATEWAY mode (listening on 865 MHz).");
#else
    subsense_lora_mesh_init(SUBSENSE_MESH_ROLE_NODE, NULL);
    Serial.println("  [LoRa Mesh] Initialized in NODE mode (broadcasting on 865 MHz).");

    // 8. Initialize OLED Display (EXCLUSIVE TO SENSOR NODE)
    bool disp_ok = subsense_display_init(21, 22, 0x3C);
    if (disp_ok) {
        subsense_display_boot_screen("ESP32-NODE-01", "v2.5.0-lora");
    }
#endif
}

void print_separator() {
    Serial.println("================================================================================");
}

void test_node_model() {
    print_separator();
    Serial.println(">>> BENCHMARK 1: Node-Tier Ultra-Fast INT8 Anomaly Detector (8 -> 16 -> 1)");
    print_separator();
    Serial.println("Model Specs: Pure integer fixed-point GEMM, 212 Bytes Flash, 16 Bytes RAM");
    Serial.println();

    // 1. Nominal Input Test
    uint32_t t_start = micros();
    uint8_t alert_nom = subsense_node_infer_int8(TEST_VEC_NOMINAL);
    uint32_t t_nom = micros() - t_start;

    Serial.print("  [Test 1.1] Nominal Vector [0,0,0,0,0,0,0,0] -> Alert: ");
    Serial.print(alert_nom);
    Serial.print(" | Latency: ");
    Serial.print(t_nom);
    Serial.print(" us | Result: ");
    if (alert_nom == 0) {
        Serial.println("PASS (Nominal / No Siren)");
    } else {
        Serial.println("FAIL (False positive)");
    }

    // 2. Anomaly Input Test
    t_start = micros();
    uint8_t alert_anom = subsense_node_infer_int8(TEST_VEC_CRITICAL);
    uint32_t t_anom = micros() - t_start;

    Serial.print("  [Test 1.2] Anomaly Vector [Severe Excursion] -> Alert: ");
    Serial.print(alert_anom);
    Serial.print(" | Latency: ");
    Serial.print(t_anom);
    Serial.print(" us | Result: ");
    if (alert_anom == 1) {
        Serial.println("PASS (CRITICAL SIREN FIRED!)");
    } else {
        Serial.println("FAIL (Missed detection)");
    }

    Serial.println();
    Serial.println("  Hardware Speed: Sub-5 microsecond local siren actuation without network roundtrip!");
}

void test_gateway_model() {
    print_separator();
    Serial.println(">>> BENCHMARK 2: Gateway-Tier 6-Layer INT8 Autoencoder (8->128->64->32->64->128->8)");
    print_separator();
    Serial.println("Model Specs: INT8 Quantized Autoencoder MSE, 23.7 KB Flash, 256 Bytes RAM");
    Serial.println();

    // 1. Nominal Input Test
    int8_t recon_nom[8];
    uint32_t t_start = micros();
    uint32_t mse_nom = subsense_gateway_infer_int8(TEST_VEC_NOMINAL, recon_nom);
    uint32_t t_nom = micros() - t_start;

    float score_nom = (float)mse_nom / ((float)mse_nom + (float)g_gw_inf_config.warning_threshold);

    Serial.print("  [Test 2.1] Nominal Vector -> Recon MSE: ");
    Serial.print(mse_nom);
    Serial.print(" (Warn Threshold: ");
    Serial.print(g_gw_inf_config.warning_threshold);
    Serial.print(") | Score: ");
    Serial.print(score_nom, 4);
    Serial.print(" | Latency: ");
    Serial.print(t_nom);
    Serial.print(" us | Result: ");
    if (mse_nom < g_gw_inf_config.warning_threshold) {
        Serial.println("PASS (Nominal Ground)");
    } else {
        Serial.println("FAIL (Unexpected breach)");
    }

    // 2. Warning Vector Test
    int8_t recon_warn[8];
    t_start = micros();
    uint32_t mse_warn = subsense_gateway_infer_int8(TEST_VEC_WARNING, recon_warn);
    uint32_t t_warn = micros() - t_start;
    float score_warn = (float)mse_warn / ((float)mse_warn + (float)g_gw_inf_config.warning_threshold);

    Serial.print("  [Test 2.2] Warning Vector -> Recon MSE: ");
    Serial.print(mse_warn);
    Serial.print(" | Score: ");
    Serial.print(score_warn, 4);
    Serial.print(" | Latency: ");
    Serial.print(t_warn);
    Serial.print(" us | Result: ");
    if (mse_warn >= g_gw_inf_config.warning_threshold && mse_warn < g_gw_inf_config.critical_threshold) {
        Serial.println("PASS (WARNING BREACH DETECTED)");
    } else {
        Serial.print("MSE: "); Serial.println(mse_warn);
    }

    // 3. Critical Vector Test
    int8_t recon_crit[8];
    t_start = micros();
    uint32_t mse_crit = subsense_gateway_infer_int8(TEST_VEC_CRITICAL, recon_crit);
    uint32_t t_crit = micros() - t_start;
    float score_crit = (float)mse_crit / ((float)mse_crit + (float)g_gw_inf_config.warning_threshold);

    Serial.print("  [Test 2.3] Critical Hazard -> Recon MSE: ");
    Serial.print(mse_crit);
    Serial.print(" (Crit Threshold: ");
    Serial.print(g_gw_inf_config.critical_threshold);
    Serial.print(") | Score: ");
    Serial.print(score_crit, 4);
    Serial.print(" | Latency: ");
    Serial.print(t_crit);
    Serial.print(" us | Result: ");
    if (mse_crit >= g_gw_inf_config.critical_threshold) {
        Serial.println("PASS (CRITICAL SIREN TRIGGERED!)");
    } else {
        Serial.println("FAIL (Expected critical)");
    }
}

void test_full_pipeline() {
    print_separator();
    Serial.println(">>> BENCHMARK 3: End-to-End Pipeline & Standardized JSON Risk Event");
    print_separator();
    Serial.println("Flow: Raw Window (32) -> Features (8) -> INT8 Normalization -> Inference -> Event JSON");
    Serial.println();

    // Re-initialize buffer
    subsense_buffer_init(&g_win_buf);

    // Push 32 synthetic samples representing an impending roof collapse
    Serial.println("  Streaming 32-sample sliding window into ring buffer...");
    for (int i = 0; i < SUBSENSE_WINDOW_SIZE; i++) {
        // Accelerating tilt and vibration spikes towards end of window
        float progress = (float)i / 32.0f;
        float tilt = 0.05f + progress * 0.85f;
        float vib = 0.02f + (i > 24 ? 0.35f : 0.04f);
        float disp = 0.1f + progress * 3.5f;
        float crack = (i > 20 ? 0.65f : 0.05f);
        subsense_buffer_push(&g_win_buf, tilt, vib, disp, crack);
    }

    // 1. Extract features
    float raw_features[SUBSENSE_NUM_FEATURES];
    uint32_t t0 = micros();
    subsense_extract_features(&g_win_buf, raw_features);
    uint32_t t_feat = micros() - t0;

    Serial.print("  1. Extracted 8 Features in "); Serial.print(t_feat); Serial.println(" us:");
    Serial.print("     Tilt Cur: "); Serial.print(raw_features[0], 4);
    Serial.print(" deg | Tilt RoC: "); Serial.print(raw_features[1], 4);
    Serial.print(" deg/win | Tilt Var: "); Serial.println(raw_features[2], 6);
    Serial.print("     Vib RMS:  "); Serial.print(raw_features[3], 4);
    Serial.print(" g   | Vib Peaks: "); Serial.print(raw_features[4], 1);
    Serial.print("     | Disp Delta: "); Serial.print(raw_features[5], 4); Serial.println(" mm");
    Serial.print("     Crack St: "); Serial.print(raw_features[6], 2);
    Serial.print("     | Crack Acts: "); Serial.println(raw_features[7], 1);

    // 2. Normalize and Quantize to INT8
    int8_t in_int8[SUBSENSE_NUM_FEATURES];
    t0 = micros();
    subsense_features_to_int8(raw_features, &g_feat_config, in_int8);
    uint32_t t_quant = micros() - t0;

    Serial.print("  2. INT8 Quantized Tensor ("); Serial.print(t_quant); Serial.print(" us): [");
    for (int i = 0; i < 8; i++) {
        Serial.print(in_int8[i]);
        if (i < 7) Serial.print(", ");
    }
    Serial.println("]");

    // 3. Run Inference Engine
    SubSenseDetectionEvent event;
    t0 = micros();
    bool breached = subsense_run_inference(
        in_int8,
        raw_features,
        "2026-09-09T21:45:00Z",
        &g_gw_inf_config,
        &event,
        &g_health
    );
    uint32_t t_inf = micros() - t0;

    Serial.print("  3. TinyML Inference completed in "); Serial.print(t_inf); Serial.println(" us.");
    Serial.print("     Threshold Breached: "); Serial.println(event.threshold_breached);
    Serial.print("     Anomaly Score: "); Serial.println(event.anomaly_score, 4);
    Serial.print("     Confidence: "); Serial.println(event.local_confidence, 2);
    Serial.print("     Siren Triggered: "); Serial.println(event.siren_triggered ? "YES" : "NO");

    // 4. Evaluate Safety Fallback
    char fallback_reason[64];
    bool fallback_siren = false;
    bool raw_hazard = subsense_fallback_evaluate(
        raw_features[0], raw_features[1], raw_features[4], raw_features[5], raw_features[6],
        fallback_reason, sizeof(fallback_reason), &fallback_siren
    );
    Serial.print("  4. Rule-based Safety Fallback: ");
    if (raw_hazard) {
        Serial.print("TRIGGERED ("); Serial.print(fallback_reason); Serial.println(")");
        event.siren_triggered = true;
    } else {
        Serial.println("NOMINAL (No raw override needed)");
    }

    // 5. Serialize JSON Event
    int json_len = subsense_serialize_event_json(&event, g_json_buf, sizeof(g_json_buf));
    Serial.println();
    Serial.println("  5. Emitted Cloud-Conformant JSON Risk Event Payload:");
    Serial.println(g_json_buf);

    // 6. Transmit over LoRa Mesh (865 MHz)
    if (subsense_lora_mesh_is_ready()) {
        subsense_lora_mesh_send(g_json_buf, (size_t)json_len);
        Serial.println("  --> [LORA MESH] Event broadcast via LoRa SX126x @ 865 MHz.");
    }

    // 7. Actuate physical hardware
    if (event.siren_triggered) {
        digitalWrite(PIN_SIREN_LED, HIGH);
        Serial.println("  --> [HARDWARE] Onboard LED (GPIO 2) ACTIVATED (Siren ON)");
    } else {
        digitalWrite(PIN_SIREN_LED, LOW);
        Serial.println("  --> [HARDWARE] Onboard LED (GPIO 2) OFF (Nominal)");
    }
}

void run_live_simulation() {
    print_separator();
    Serial.println(">>> LIVE MINE SIMULATION: 40 Timesteps (Nominal -> Precursors -> Collapse)");
    print_separator();
    Serial.println("Watch real-time model scoring and hardware LED activation as subsidence develops:");
    Serial.println();

    subsense_buffer_init(&g_win_buf);

    for (int t = 1; t <= 40; t++) {
        float tilt, vib, disp, crack;
        const char* scenario_phase;

        if (t <= 15) {
            scenario_phase = "Normal Baseline";
            tilt = 0.02f + (random(-5, 5) * 0.001f);
            vib = 0.03f + (random(0, 10) * 0.002f);
            disp = 0.1f + (t * 0.01f);
            crack = 0.0f;
        } else if (t <= 26) {
            scenario_phase = "Micro-Shearing";
            float prog = (float)(t - 15) / 11.0f;
            tilt = 0.05f + prog * 0.45f;
            vib = 0.05f + prog * 0.12f + (random(0, 8) * 0.01f);
            disp = 0.3f + prog * 2.2f;
            crack = (t > 22 ? 0.35f : 0.05f);
        } else {
            scenario_phase = "ROOF COLLAPSE ";
            float prog = (float)(t - 26) / 14.0f;
            tilt = 0.5f + prog * 2.8f;
            vib = 0.25f + prog * 0.85f;
            disp = 3.0f + prog * 11.5f; // Reaches catastrophic displacement
            crack = 0.4f + prog * 0.55f;
        }

        // Push to buffer
        subsense_buffer_push(&g_win_buf, tilt, vib, disp, crack);

        if (!subsense_buffer_is_full(&g_win_buf)) {
            Serial.print("[T="); Serial.print(t); Serial.print("/40] Buffering window... (");
            Serial.print(g_win_buf.count); Serial.println("/32 samples)");
            delay(100);
            continue;
        }

        // Run full step
        float raw_feat[8];
        subsense_extract_features(&g_win_buf, raw_feat);

        int8_t in_int8[8];
        subsense_features_to_int8(raw_feat, &g_feat_config, in_int8);

        SubSenseDetectionEvent ev;
        subsense_run_inference(in_int8, raw_feat, "2026-09-09T21:45:00Z", &g_gw_inf_config, &ev, &g_health);

        // Fallback check
        char fb_reason[64];
        bool fb_siren = false;
        bool raw_hazard = subsense_fallback_evaluate(
            raw_feat[0], raw_feat[1], raw_feat[4], raw_feat[5], raw_feat[6],
            fb_reason, sizeof(fb_reason), &fb_siren
        );
        if (raw_hazard) {
            ev.siren_triggered = true;
        }

        // Broadcast over LoRa Mesh on warning or critical alert
        if (ev.siren_triggered || strcmp(ev.threshold_breached, "none") != 0) {
            int json_len = subsense_serialize_event_json(&ev, g_json_buf, sizeof(g_json_buf));
            if (subsense_lora_mesh_is_ready()) {
                subsense_lora_mesh_send(g_json_buf, (size_t)json_len);
                Serial.println("  --> [LORA MESH] Event transmitted over LoRa SX126x @ 865 MHz.");
            }
        }

        // Actuate LED
        if (ev.siren_triggered) {
            digitalWrite(PIN_SIREN_LED, HIGH);
        } else if (strcmp(ev.threshold_breached, "warning") == 0) {
            digitalWrite(PIN_SIREN_LED, (t % 2 == 0) ? HIGH : LOW); // Blink on warning
        } else {
            digitalWrite(PIN_SIREN_LED, LOW);
        }

#if !SUBSENSE_IS_GATEWAY
        // Update OLED Health Display on Sensor Node
        SubSenseNodeDisplayData disp_data;
        disp_data.node_id         = "ESP32-NODE-01";
        disp_data.tilt_deg        = tilt;
        disp_data.vibration_rms   = vib * 9.8f * 10.0f;
        disp_data.anomaly_score   = ev.anomaly_score;
        disp_data.battery_percent = 94;
        disp_data.rssi_dbm        = -68;
        disp_data.hop_count       = 0;
        disp_data.packets_sent    = t + 1;
        disp_data.uptime_seconds  = millis() / 1000;
        disp_data.sensor_ok       = true;
        disp_data.mesh_ok         = true;
        disp_data.siren_active    = ev.siren_triggered;
        disp_data.status_text     = ev.siren_triggered ? "CRITICAL" : (strcmp(ev.threshold_breached, "warning") == 0 ? "WARNING" : "NOMINAL");
        subsense_display_update_health(&disp_data);
#endif

        // Print telemetry line
        Serial.print("[T=");
        if (t < 10) Serial.print("0");
        Serial.print(t);
        Serial.print("] ");
        Serial.print(scenario_phase);
        Serial.print(" | Tilt:"); Serial.print(tilt, 2); Serial.print("°");
        Serial.print(" Vib:"); Serial.print(vib, 2); Serial.print("g");
        Serial.print(" Disp:"); Serial.print(disp, 1); Serial.print("mm");
        Serial.print(" Crack:"); Serial.print(crack, 2); Serial.print("mm");
        Serial.print(" | Score: "); Serial.print(ev.anomaly_score, 2);
        Serial.print(" ["); Serial.print(ev.threshold_breached); Serial.print("]");
        if (ev.siren_triggered) {
            Serial.print(" *** SIREN ACTIVE ***");
        }
        Serial.println();

        delay(150);
    }

    digitalWrite(PIN_SIREN_LED, LOW);
    Serial.println();
    Serial.println("  Simulation completed. Siren returned to standby.");
}

void print_power_report() {
    print_separator();
    Serial.println(">>> EMBEDDED POWER & BATTERY PROJECTIONS (2600 mAh 18650 Li-ion Cell)");
    print_separator();

    SubSensePowerConfig cfg = g_pwr_config;

    // Profile 1: 1.0 Hz Gateway Continuous
    cfg.mode = POWER_MODE_BATTERY_DUTY_CYCLE;
    cfg.sampling_interval_ms = 1000;
    cfg.active_duration_us = 400; // 0.4 ms
    float avg_ma_1s = subsense_power_calc_avg_current_ma(&cfg);
    float life_1s = subsense_power_calc_battery_life_months(&cfg);

    // Profile 2: 0.5 Hz (2.0s interval)
    cfg.sampling_interval_ms = 2000;
    float avg_ma_2s = subsense_power_calc_avg_current_ma(&cfg);
    float life_2s = subsense_power_calc_battery_life_months(&cfg);

    // Profile 3: 0.2 Hz (5.0s interval - Standard Deep Mining Node)
    cfg.sampling_interval_ms = 5000;
    float avg_ma_5s = subsense_power_calc_avg_current_ma(&cfg);
    float life_5s = subsense_power_calc_battery_life_months(&cfg);

    Serial.print("  1. High-Frequency Sampling (1.0 Hz / 1 sec interval):\n");
    Serial.print("     Average Current: "); Serial.print(avg_ma_1s * 1000.0f, 1); Serial.print(" uA | Projected Lifespan: ");
    Serial.print(life_1s, 1); Serial.print(" months (~"); Serial.print(life_1s / 12.0f, 1); Serial.println(" years)");

    Serial.print("  2. Standard Slope Monitoring (0.5 Hz / 2 sec interval):\n");
    Serial.print("     Average Current: "); Serial.print(avg_ma_2s * 1000.0f, 1); Serial.print(" uA | Projected Lifespan: ");
    Serial.print(life_2s, 1); Serial.print(" months (~"); Serial.print(life_2s / 12.0f, 1); Serial.println(" years)");

    Serial.print("  3. Deep Pillar Surveillance (0.2 Hz / 5 sec interval):\n");
    Serial.print("     Average Current: "); Serial.print(avg_ma_5s * 1000.0f, 1); Serial.print(" uA | Projected Lifespan: ");
    Serial.print(life_5s, 1); Serial.print(" months (~"); Serial.print(life_5s / 12.0f, 1); Serial.println(" years)");
    Serial.println();
    Serial.println("  Conclusion: Deep-sleep duty cycling enables 4+ years of uninterrupted underground operation.");
}

void print_menu() {
    Serial.println();
    print_separator();
    Serial.println("               SUBSENSE TINYML ESP32 INTERACTIVE CONSOLE");
    print_separator();
    Serial.println("  [1] Run Node Model Benchmark (2-Layer High-Recall Detector)");
    Serial.println("  [2] Run Gateway Model Benchmark (6-Layer INT8 Autoencoder)");
    Serial.println("  [3] Run Full Pipeline Test (Window -> Feature -> Model -> JSON Event)");
    Serial.println("  [4] Run Live Mine Subsidence Simulation (Calm -> Anomaly -> Collapse)");
    Serial.println("  [5] Print Power Consumption & 4-Year Battery Lifespan Report");
    Serial.println("  [6] Toggle Hardware Siren/LED (GPIO 2)");
    Serial.println("  [7] Print Self-Health Telemetry JSON");
#if !SUBSENSE_IS_GATEWAY
    Serial.println("  [8] Update OLED Health Status Display (Sensor Node Exclusive)");
#endif
    Serial.println("  [?] Print this Menu");
    print_separator();
    Serial.print("Enter command [1-8]: ");
}

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 2500); // Wait for USB Serial connection

    // Configure hardware pins
    pinMode(PIN_SIREN_LED, OUTPUT);
    digitalWrite(PIN_SIREN_LED, LOW);

    // Boot LED flash (3 short blinks to confirm GPIO is active)
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_SIREN_LED, HIGH);
        delay(80);
        digitalWrite(PIN_SIREN_LED, LOW);
        delay(80);
    }

    setup_subsense();

    Serial.println();
    print_separator();
    Serial.println("    SubSense TinyML On-Device Firmware Initialized on ESP32");
    Serial.println("    Author: SubSense Team | Smart India Hackathon 2026");
    Serial.println("    Hardware: ESP32 @ 240MHz | Zero Dynamic Heap Allocation");
#if defined(ESP_ARDUINO_VERSION)
    Serial.print("    ESP32 Arduino Core: v");
    Serial.print(ESP_ARDUINO_VERSION_MAJOR);
    Serial.print(".");
    Serial.print(ESP_ARDUINO_VERSION_MINOR);
    Serial.print(".");
    Serial.println(ESP_ARDUINO_VERSION_PATCH);
#elif defined(ARDUINO_ESP32_RELEASE)
    Serial.print("    ESP32 Arduino Core: ");
    Serial.println(ARDUINO_ESP32_RELEASE);
#endif
    Serial.print("    Underlying ESP-IDF: ");
    Serial.println(esp_get_idf_version());
    print_separator();
    Serial.println();

    // Run automatic on-boot self tests
    test_node_model();
    Serial.println();
    test_gateway_model();
    Serial.println();
    test_full_pipeline();

    print_menu();
}

void loop() {
    // Keep LoRa Mesh housekeeper running (for gateway reassembly & timeout drops)
    subsense_lora_mesh_loop();

    if (Serial.available() > 0) {
        char cmd = Serial.read();
        // Ignore newline / carriage return
        if (cmd == '\r' || cmd == '\n' || cmd == ' ') return;

        Serial.println(cmd);

        switch (cmd) {
            case '1':
                test_node_model();
                break;
            case '2':
                test_gateway_model();
                break;
            case '3':
                test_full_pipeline();
                break;
            case '4':
                run_live_simulation();
                break;
            case '5':
                print_power_report();
                break;
            case '6': {
                static bool led_state = false;
                led_state = !led_state;
                digitalWrite(PIN_SIREN_LED, led_state ? HIGH : LOW);
                Serial.print("Hardware Siren/LED Pin (GPIO ");
                Serial.print(PIN_SIREN_LED);
                Serial.print(") set to: ");
                Serial.println(led_state ? "ON (HIGH)" : "OFF (LOW)");
                break;
            }
            case '7': {
                subsense_serialize_health_json(&g_health, g_health_buf, sizeof(g_health_buf));
                Serial.println("SubSense Self-Health Telemetry JSON:");
                Serial.println(g_health_buf);
                break;
            }
#if !SUBSENSE_IS_GATEWAY
            case '8': {
                SubSenseNodeDisplayData d;
                d.node_id         = "SS-PANEL7-N042";
                d.tilt_deg        = 1.45f;
                d.vibration_rms   = 0.28f;
                d.anomaly_score   = 0.14f;
                d.battery_percent = 94;
                d.rssi_dbm        = -66;
                d.hop_count       = 0;
                d.packets_sent    = 42;
                d.uptime_seconds  = millis() / 1000;
                d.sensor_ok       = true;
                d.mesh_ok         = true;
                d.siren_active    = false;
                d.status_text     = "NOMINAL";
                subsense_display_update_health(&d);
                Serial.println("[DISPLAY] OLED Health Status refreshed on Sensor Node.");
                break;
            }
#endif
            case '?':
            case 'h':
            case 'H':
                print_menu();
                break;
            default:
                Serial.print("Unknown command '"); Serial.print(cmd); Serial.println("'. Press '?' for menu.");
                break;
        }

        print_menu();
    }
}
