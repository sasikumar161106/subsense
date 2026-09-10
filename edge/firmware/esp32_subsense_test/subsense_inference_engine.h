/**
 * @file subsense_inference_engine.h
 * @brief SubSense On-Device Inference Engine, Anomaly Scoring & JSON Event Emitter.
 * @note Emits structured risk events matching cloud Risk Event schema.
 *       Zero dynamic heap allocation (static buffer serialization).
 */

#ifndef SUBSENSE_INFERENCE_ENGINE_H
#define SUBSENSE_INFERENCE_ENGINE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SUBSENSE_NODE_ID_MAX_LEN      16
#define SUBSENSE_VERSION_MAX_LEN      32
#define SUBSENSE_TIMESTAMP_MAX_LEN    32
#define SUBSENSE_JSON_EVENT_MAX_LEN   512

/**
 * @brief Structured detection event matching the platform's exact cloud schema.
 */
typedef struct {
    char node_id[SUBSENSE_NODE_ID_MAX_LEN];
    char model_version[SUBSENSE_VERSION_MAX_LEN];
    char window_end_ts[SUBSENSE_TIMESTAMP_MAX_LEN];
    float anomaly_score;
    float local_confidence;
    const char* contributing_features[4];
    uint8_t num_contributing_features;
    const char* threshold_breached;   // "none", "warning", or "critical"
    bool siren_triggered;
    const char* source_tier;          // "gateway" or "node"
} SubSenseDetectionEvent;

/**
 * @brief Self-health telemetry object reported over mesh health channel.
 */
typedef struct {
    char model_version[SUBSENSE_VERSION_MAX_LEN];
    uint32_t last_inference_timestamp;
    uint32_t total_inferences;
    uint32_t inference_failures;
    uint32_t watchdog_resets;
    uint32_t fallback_activations;
    int8_t battery_percent;
    int8_t rssi_dbm;
} SubSenseHealthTelemetry;

/**
 * @brief Configuration thresholds for Gateway/Node inference.
 */
typedef struct {
    uint32_t warning_threshold;
    uint32_t critical_threshold;
    const char* node_id;
    const char* model_version;
    const char* source_tier;
} SubSenseInferenceConfig;

/**
 * @brief Initialize the inference engine and health telemetry.
 */
void subsense_inference_init(
    const SubSenseInferenceConfig* config,
    SubSenseHealthTelemetry* health
);

/**
 * @brief Run inference on extracted features, score anomaly, and populate event.
 * @param in_features_int8 INT8 normalized feature vector (8).
 * @param raw_features Raw unnormalized float features (8) for explainability.
 * @param timestamp_iso ISO8601 timestamp string (e.g. "2026-09-09T05:11:58Z").
 * @param config Active inference configuration and thresholds.
 * @param out_event Destination detection event struct.
 * @param health Health telemetry tracker to update.
 * @return True if warning/critical threshold was breached, false otherwise.
 */
bool subsense_run_inference(
    const int8_t in_features_int8[8],
    const float raw_features[8],
    const char* timestamp_iso,
    const SubSenseInferenceConfig* config,
    SubSenseDetectionEvent* out_event,
    SubSenseHealthTelemetry* health
);

/**
 * @brief Serialize SubSenseDetectionEvent to exact JSON schema.
 * @param event Input detection event.
 * @param out_json Destination buffer for JSON string.
 * @param max_len Maximum length of destination buffer.
 * @return Number of characters written.
 */
int subsense_serialize_event_json(
    const SubSenseDetectionEvent* event,
    char* out_json,
    size_t max_len
);

/**
 * @brief Serialize SubSenseHealthTelemetry to JSON string.
 */
int subsense_serialize_health_json(
    const SubSenseHealthTelemetry* health,
    char* out_json,
    size_t max_len
);

#ifdef __cplusplus
}
#endif

#endif // SUBSENSE_INFERENCE_ENGINE_H
