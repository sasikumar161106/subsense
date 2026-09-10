/**
 * @file subsense_features.c
 * @brief SubSense Feature Extractor Implementation.
 * @note Zero train/serve skew implementation matching Python reference 1:1.
 */

#include "subsense_features.h"
#include <math.h>

void subsense_buffer_init(SubSenseWindowBuffer* buf) {
    if (!buf) return;
    buf->head = 0;
    buf->count = 0;
    buf->disp_rolling_baseline = 0.0f;
    buf->baseline_initialized = false;
    for (int i = 0; i < SUBSENSE_WINDOW_SIZE; i++) {
        buf->tilt_ring[i] = 0.0f;
        buf->vib_ring[i] = 0.0f;
        buf->disp_ring[i] = 0.0f;
        buf->crack_ring[i] = 0.0f;
    }
}

void subsense_buffer_push(
    SubSenseWindowBuffer* buf,
    float tilt,
    float vibration,
    float displacement,
    float crack
) {
    if (!buf) return;

    if (!buf->baseline_initialized) {
        buf->disp_rolling_baseline = displacement;
        buf->baseline_initialized = true;
    } else {
        // Slow exponential moving average baseline tracking:
        // B_t = (1 - alpha) * B_{t-1} + alpha * disp_t
        buf->disp_rolling_baseline = 
            (1.0f - SUBSENSE_BASELINE_ALPHA) * buf->disp_rolling_baseline + 
            SUBSENSE_BASELINE_ALPHA * displacement;
    }

    buf->tilt_ring[buf->head] = tilt;
    buf->vib_ring[buf->head] = vibration;
    buf->disp_ring[buf->head] = displacement;
    buf->crack_ring[buf->head] = crack;

    buf->head = (buf->head + 1) % SUBSENSE_WINDOW_SIZE;
    if (buf->count < SUBSENSE_WINDOW_SIZE) {
        buf->count++;
    }
}

bool subsense_buffer_is_full(const SubSenseWindowBuffer* buf) {
    return (buf && buf->count >= SUBSENSE_WINDOW_SIZE);
}

void subsense_extract_features(
    const SubSenseWindowBuffer* buf,
    float out_features[SUBSENSE_NUM_FEATURES]
) {
    if (!buf || !out_features) return;

    const float inv_w = 1.0f / (float)SUBSENSE_WINDOW_SIZE;
    uint16_t last_idx = (buf->head + SUBSENSE_WINDOW_SIZE - 1) % SUBSENSE_WINDOW_SIZE;
    uint16_t first_idx = buf->head;

    // 1. Tilt features
    float tilt_current = buf->tilt_ring[last_idx];
    float tilt_first = buf->tilt_ring[first_idx];
    float tilt_roc = (tilt_current - tilt_first) * inv_w;

    float tilt_sum = 0.0f;
    for (int i = 0; i < SUBSENSE_WINDOW_SIZE; i++) {
        tilt_sum += buf->tilt_ring[i];
    }
    float tilt_mean = tilt_sum * inv_w;

    float tilt_var = 0.0f;
    for (int i = 0; i < SUBSENSE_WINDOW_SIZE; i++) {
        float diff = buf->tilt_ring[i] - tilt_mean;
        tilt_var += diff * diff;
    }
    tilt_var *= inv_w;

    // 2. Vibration features
    float vib_sq_sum = 0.0f;
    float vib_peaks = 0.0f;
    for (int i = 0; i < SUBSENSE_WINDOW_SIZE; i++) {
        float v = buf->vib_ring[i];
        vib_sq_sum += v * v;
        if (fabsf(v) > SUBSENSE_VIB_PEAK_THRESHOLD) {
            vib_peaks += 1.0f;
        }
    }
    float vib_rms = sqrtf(vib_sq_sum * inv_w);

    // 3. Displacement feature: delta from rolling baseline
    float disp_current = buf->disp_ring[last_idx];
    float disp_delta = disp_current - buf->disp_rolling_baseline;

    // 4. Crack features
    float crack_state = buf->crack_ring[last_idx];
    float crack_count = 0.0f;
    for (int i = 0; i < SUBSENSE_WINDOW_SIZE; i++) {
        if (buf->crack_ring[i] >= SUBSENSE_CRACK_THRESHOLD) {
            crack_count += 1.0f;
        }
    }

    out_features[0] = tilt_current;
    out_features[1] = tilt_roc;
    out_features[2] = tilt_var;
    out_features[3] = vib_rms;
    out_features[4] = vib_peaks;
    out_features[5] = disp_delta;
    out_features[6] = crack_state;
    out_features[7] = crack_count;
}

void subsense_features_to_int8(
    const float features[SUBSENSE_NUM_FEATURES],
    const SubSenseFeatureConfig* config,
    int8_t out_int8[SUBSENSE_NUM_FEATURES]
) {
    if (!features || !config || !out_int8) return;

    for (int i = 0; i < SUBSENSE_NUM_FEATURES; i++) {
        // Z-score normalization
        float normalized = (features[i] - config->scaler_mean[i]) / config->scaler_scale[i];
        // Symmetric/Asymmetric INT8 quantization
        float q_val = roundf(normalized / config->quant_input_scale) + (float)config->quant_input_zp;
        if (q_val > 127.0f) q_val = 127.0f;
        if (q_val < -128.0f) q_val = -128.0f;
        out_int8[i] = (int8_t)q_val;
    }
}
