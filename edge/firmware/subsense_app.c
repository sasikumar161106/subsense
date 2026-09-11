/**
 * @file subsense_app.c
 * @brief SubSense Top-Level Embedded Application Entry Point for ESP32.
 * @note Compatible with ESP-IDF `app_main()` and Arduino `setup()` / `loop()`.
 */

#include <stdio.h>
#include <string.h>

#include "subsense_features.h"
#include "subsense_inference_engine.h"
#include "subsense_fallback.h"
#include "subsense_ota_manager.h"
#include "subsense_lora_mesh.h"  

#if defined(ESP_PLATFORM) || defined(ARDUINO_ARCH_ESP32)
#include "esp_attr.h"
static RTC_DATA_ATTR SubSenseWindowBuffer     s_window_buf;
static RTC_DATA_ATTR SubSenseHealthTelemetry  s_health;
#else
// Statically allocated system components
static SubSenseWindowBuffer     s_window_buf;
static SubSenseHealthTelemetry  s_health;
#endif

static SubSenseOTAManager       s_ota;
static SubSenseFeatureConfig    s_feat_config;
static SubSenseInferenceConfig  s_inf_config;
static SubSensePowerConfig      s_pwr_config;

// Static event buffers
static char s_json_event_buffer[SUBSENSE_JSON_EVENT_MAX_LEN];
static char s_json_health_buffer[256];

void subsense_system_init(void) {
    // 1. Initialize ring buffer if uninitialized
    if (s_window_buf.count > SUBSENSE_WINDOW_SIZE) {
        subsense_buffer_init(&s_window_buf);
    }

    // 2. Initialize OTA manager
    subsense_ota_init(&s_ota, "gw-autoencoder-v1.3.0");

    // 3. Configure inference parameters
    s_inf_config.warning_threshold = 474;
    s_inf_config.critical_threshold = 950;
    s_inf_config.node_id = "N-021";
    s_inf_config.model_version = "gw-autoencoder-v1.3.0";
    s_inf_config.source_tier = "gateway"; // or "node"

    // 4. Configure feature normalizer
    s_feat_config.scaler_mean[0] = 0.010298f;  s_feat_config.scaler_scale[0] = 0.077703f;
    s_feat_config.scaler_mean[1] = 0.000011f;  s_feat_config.scaler_scale[1] = 0.001341f;
    s_feat_config.scaler_mean[2] = 0.000893f;  s_feat_config.scaler_scale[2] = 0.000220f;
    s_feat_config.scaler_mean[3] = 0.043559f;  s_feat_config.scaler_scale[3] = 0.023900f;
    s_feat_config.scaler_mean[4] = 0.332180f;  s_feat_config.scaler_scale[4] = 2.029822f;
    s_feat_config.scaler_mean[5] = -0.000056f; s_feat_config.scaler_scale[5] = 0.020145f;
    s_feat_config.scaler_mean[6] = 0.0f;       s_feat_config.scaler_scale[6] = 1.0f;
    s_feat_config.scaler_mean[7] = 0.0f;       s_feat_config.scaler_scale[7] = 1.0f;
    s_feat_config.quant_input_scale = 0.029008f;
    s_feat_config.quant_input_zp = 0;

    // 5. Initialize inference & health telemetry
    subsense_inference_init(&s_inf_config, &s_health);

    // 6. Configure power profile (e.g. 1 Hz duty cycle)
    s_pwr_config.mode = POWER_MODE_BATTERY_DUTY_CYCLE;
    s_pwr_config.sampling_interval_ms = 1000;
    s_pwr_config.active_duration_us = 400; // ~0.4 ms
    s_pwr_config.active_current_ma = 50.0f;
    s_pwr_config.deep_sleep_current_ua = 10.0f;
    s_pwr_config.battery_capacity_mah = 2600.0f;
    subsense_power_init(&s_pwr_config);

    // 7. Initialize LoRa SX126x mesh transport (Board 1 - Sensor Node role)
    subsense_lora_mesh_init(SUBSENSE_MESH_ROLE_NODE, NULL);
}

/**
 * @brief Main duty-cycle step invoked on every timer wakeup.
 */
void subsense_step(
    float raw_tilt,
    float raw_vib,
    float raw_disp,
    float raw_crack,
    const char* timestamp_iso
) {
    // 1. Push raw sample into ring buffer
    subsense_buffer_push(&s_window_buf, raw_tilt, raw_vib, raw_disp, raw_crack);

    // Wait until full window is accumulated
    if (!subsense_buffer_is_full(&s_window_buf)) {
        return;
    }

    // 2. Extract deterministic features
    float raw_features[SUBSENSE_NUM_FEATURES];
    subsense_extract_features(&s_window_buf, raw_features);

    // 3. Convert to INT8 input tensor
    int8_t in_features_int8[SUBSENSE_NUM_FEATURES];
    subsense_features_to_int8(raw_features, &s_feat_config, in_features_int8);

    // 4. Primary path: run INT8 TinyML inference
    SubSenseDetectionEvent event;
    bool breached = subsense_run_inference(
        in_features_int8,
        raw_features,
        timestamp_iso,
        &s_inf_config,
        &event,
        &s_health
    );

    // 5. Failure safeguard: check fallback if ML inference flagged warning/critical or error
    char fallback_reason[64];
    bool fallback_siren = false;
    bool raw_hazard = subsense_fallback_evaluate(
        raw_features[0],
        raw_features[1],
        raw_features[3],
        raw_features[5],
        raw_features[6],
        fallback_reason,
        sizeof(fallback_reason),
        &fallback_siren
    );

    if (raw_hazard) {
        event.siren_triggered = true;
        s_health.fallback_activations++;
    }

    // 6. If threshold breached or raw hazard detected, emit event over LoRa Mesh
    if (breached || raw_hazard) {
        int json_len = subsense_serialize_event_json(&event, s_json_event_buffer, sizeof(s_json_event_buffer));
        if (subsense_lora_mesh_is_ready()) {
            subsense_lora_mesh_send(s_json_event_buffer, (size_t)json_len);
        }
    }

    // 7. Periodic self-health reporting over LoRa Mesh
    if (s_health.total_inferences % 60 == 0) {
        int health_len = subsense_serialize_health_json(&s_health, s_json_health_buffer, sizeof(s_json_health_buffer));
        if (subsense_lora_mesh_is_ready()) {
            subsense_lora_mesh_send(s_json_health_buffer, (size_t)health_len);
        }
    }
}

#if defined(ESP_PLATFORM) && !defined(ARDUINO)
void app_main(void) {
    subsense_system_init();
    // Hardware timer / sampling loop...
}
#endif
