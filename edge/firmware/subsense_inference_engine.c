/**
 * @file subsense_inference_engine.c
 * @brief SubSense On-Device Inference Engine Implementation.
 */

#include "subsense_inference_engine.h"
#include "subsense_gateway_model.h"
#include "subsense_node_model.h"

#include <stdio.h>
#include <string.h>
#include <math.h>

void subsense_inference_init(
    const SubSenseInferenceConfig* config,
    SubSenseHealthTelemetry* health
) {
    if (health && config) {
        strncpy(health->model_version, config->model_version, SUBSENSE_VERSION_MAX_LEN - 1);
        health->model_version[SUBSENSE_VERSION_MAX_LEN - 1] = '\0';
        health->last_inference_timestamp = 0;
        health->total_inferences = 0;
        health->inference_failures = 0;
        health->watchdog_resets = 0;
        health->fallback_activations = 0;
        health->battery_percent = 95;
        health->rssi_dbm = -72;
    }
}

bool subsense_run_inference(
    const int8_t in_features_int8[8],
    const float raw_features[8],
    const char* timestamp_iso,
    const SubSenseInferenceConfig* config,
    SubSenseDetectionEvent* out_event,
    SubSenseHealthTelemetry* health
) {
    if (!in_features_int8 || !raw_features || !config || !out_event) return false;

    // Populate static metadata
    strncpy(out_event->node_id, config->node_id, SUBSENSE_NODE_ID_MAX_LEN - 1);
    out_event->node_id[SUBSENSE_NODE_ID_MAX_LEN - 1] = '\0';

    strncpy(out_event->model_version, config->model_version, SUBSENSE_VERSION_MAX_LEN - 1);
    out_event->model_version[SUBSENSE_VERSION_MAX_LEN - 1] = '\0';

    strncpy(out_event->window_end_ts, timestamp_iso ? timestamp_iso : "1970-01-01T00:00:00Z", SUBSENSE_TIMESTAMP_MAX_LEN - 1);
    out_event->window_end_ts[SUBSENSE_TIMESTAMP_MAX_LEN - 1] = '\0';

    out_event->source_tier = config->source_tier ? config->source_tier : "gateway";

    bool is_gateway = (strcmp(out_event->source_tier, "gateway") == 0);
    uint32_t int_error = 0;
    float score = 0.0f;
    float confidence = 0.50f;
    bool siren = false;
    const char* breach = "none";

    if (is_gateway) {
        // Run Gateway INT8 Autoencoder forward pass
        int8_t out_recon[8];
        int_error = subsense_gateway_infer_int8(in_features_int8, out_recon);

        // Normalize score to [0.0, 1.0] using warning threshold
        float warn_th = (float)config->warning_threshold;
        if (warn_th <= 0.0f) warn_th = 400.0f;

        score = (float)int_error / ((float)int_error + warn_th);
        // Confidence increases with distance from decision boundary
        float margin = fabsf((float)int_error - warn_th) / warn_th;
        confidence = 0.50f + 0.50f * (margin > 1.0f ? 1.0f : margin);

        if (int_error >= config->critical_threshold) {
            breach = "critical";
            siren = true;
        } else if (int_error >= config->warning_threshold) {
            breach = "warning";
            siren = false;
        } else {
            breach = "none";
            siren = false;
        }
    } else {
        // Run Node INT8 Single-Layer Detector
        uint8_t alert = subsense_node_infer_int8(in_features_int8);
        if (alert) {
            score = 0.95f;
            confidence = 0.88f;
            breach = "critical";
            siren = true; // Local siren fires immediately without mesh/cloud roundtrip!
        } else {
            score = 0.05f;
            confidence = 0.92f;
            breach = "none";
            siren = false;
        }
    }

    out_event->anomaly_score = score;
    out_event->local_confidence = confidence;
    out_event->threshold_breached = breach;
    out_event->siren_triggered = siren;

    // Identify Contributing Features based on deviations in raw sensor features
    // [0] tilt_cur, [1] tilt_roc, [2] tilt_var, [3] vib_rms, [4] vib_peaks, [5] disp_delta, [6] crack_state, [7] crack_count
    out_event->num_contributing_features = 0;
    if (fabsf(raw_features[1]) > 0.04f && out_event->num_contributing_features < 4) {
        out_event->contributing_features[out_event->num_contributing_features++] = "tilt_rate";
    }
    if (raw_features[3] > 0.12f && out_event->num_contributing_features < 4) {
        out_event->contributing_features[out_event->num_contributing_features++] = "vibration_rms";
    }
    if (fabsf(raw_features[5]) > 0.50f && out_event->num_contributing_features < 4) {
        out_event->contributing_features[out_event->num_contributing_features++] = "displacement_delta";
    }
    if (raw_features[6] > 0.30f && out_event->num_contributing_features < 4) {
        out_event->contributing_features[out_event->num_contributing_features++] = "crack_state";
    }
    if (raw_features[4] > 4.0f && out_event->num_contributing_features < 4) {
        out_event->contributing_features[out_event->num_contributing_features++] = "vibration_peak_count";
    }
    if (raw_features[2] > 0.003f && out_event->num_contributing_features < 4) {
        out_event->contributing_features[out_event->num_contributing_features++] = "tilt_variance";
    }
    if (out_event->num_contributing_features == 0) {
        out_event->contributing_features[out_event->num_contributing_features++] = "nominal_baseline";
    }

    // Update health telemetry
    if (health) {
        health->total_inferences++;
    }

    return (strcmp(breach, "none") != 0);
}

int subsense_serialize_event_json(
    const SubSenseDetectionEvent* event,
    char* out_json,
    size_t max_len
) {
    if (!event || !out_json || max_len == 0) return 0;

    // Build contributing features JSON array
    char feat_buf[128] = "[";
    for (int i = 0; i < event->num_contributing_features; i++) {
        strcat(feat_buf, "\"");
        strcat(feat_buf, event->contributing_features[i]);
        strcat(feat_buf, "\"");
        if (i < event->num_contributing_features - 1) {
            strcat(feat_buf, ", ");
        }
    }
    strcat(feat_buf, "]");

    // Format exact JSON schema
    int written = snprintf(
        out_json,
        max_len,
        "{\n"
        "  \"node_id\": \"%s\",\n"
        "  \"model_version\": \"%s\",\n"
        "  \"window_end_ts\": \"%s\",\n"
        "  \"anomaly_score\": %.2f,\n"
        "  \"local_confidence\": %.2f,\n"
        "  \"contributing_features\": %s,\n"
        "  \"threshold_breached\": \"%s\",\n"
        "  \"siren_triggered\": %s,\n"
        "  \"source_tier\": \"%s\"\n"
        "}",
        event->node_id,
        event->model_version,
        event->window_end_ts,
        event->anomaly_score,
        event->local_confidence,
        feat_buf,
        event->threshold_breached,
        event->siren_triggered ? "true" : "false",
        event->source_tier
    );

    return written;
}

int subsense_serialize_health_json(
    const SubSenseHealthTelemetry* health,
    char* out_json,
    size_t max_len
) {
    if (!health || !out_json || max_len == 0) return 0;

    return snprintf(
        out_json,
        max_len,
        "{\n"
        "  \"model_version\": \"%s\",\n"
        "  \"last_inference_ts\": %lu,\n"
        "  \"total_inferences\": %lu,\n"
        "  \"inference_failures\": %lu,\n"
        "  \"watchdog_resets\": %lu,\n"
        "  \"fallback_activations\": %lu,\n"
        "  \"battery_percent\": %d,\n"
        "  \"rssi_dbm\": %d\n"
        "}",
        health->model_version,
        (unsigned long)health->last_inference_timestamp,
        (unsigned long)health->total_inferences,
        (unsigned long)health->inference_failures,
        (unsigned long)health->watchdog_resets,
        (unsigned long)health->fallback_activations,
        health->battery_percent,
        health->rssi_dbm
    );
}
