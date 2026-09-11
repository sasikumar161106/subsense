/**
 * @file subsense_features.h
 * @brief SubSense Microcontroller Ring Buffer and Deterministic Feature Extractor.
 * @note Implements exact Phase 1 specification using integer and fixed-point math.
 *       Shared specification between cloud training pipeline and embedded firmware.
 */

#ifndef SUBSENSE_FEATURES_H
#define SUBSENSE_FEATURES_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SUBSENSE_WINDOW_SIZE          32
#define SUBSENSE_NUM_FEATURES         8
#define SUBSENSE_VIB_PEAK_THRESHOLD   3.0f
#define SUBSENSE_CRACK_THRESHOLD      0.50f
#define SUBSENSE_BASELINE_ALPHA       0.01f

/**
 * @brief Circular ring buffer for continuous multi-sensor streams.
 */
typedef struct {
    float tilt_ring[SUBSENSE_WINDOW_SIZE];
    float vib_ring[SUBSENSE_WINDOW_SIZE];
    float disp_ring[SUBSENSE_WINDOW_SIZE];
    float crack_ring[SUBSENSE_WINDOW_SIZE];
    uint16_t head;
    uint16_t count;
    float disp_rolling_baseline;
    bool baseline_initialized;
} SubSenseWindowBuffer;

/**
 * @brief Pre-calibrated Z-score and INT8 quantization parameters.
 */
typedef struct {
    float scaler_mean[SUBSENSE_NUM_FEATURES];
    float scaler_scale[SUBSENSE_NUM_FEATURES];
    float quant_input_scale;
    int8_t quant_input_zp;
} SubSenseFeatureConfig;

/**
 * @brief Initialize the ring buffer.
 */
void subsense_buffer_init(SubSenseWindowBuffer* buf);

/**
 * @brief Push a new raw multi-sensor telemetry sample into the ring buffer.
 * @note Battery and RSSI metadata are intentionally ignored to prevent leakage.
 */
void subsense_buffer_push(
    SubSenseWindowBuffer* buf,
    float tilt,
    float vibration,
    float displacement,
    float crack
);

/**
 * @brief Check if the ring buffer has accumulated a full window (32 samples).
 */
bool subsense_buffer_is_full(const SubSenseWindowBuffer* buf);

/**
 * @brief Extract exactly the 8 deterministic features from the full window.
 *
 * Feature indices:
 *   [0] tilt_current
 *   [1] tilt_rate_of_change
 *   [2] tilt_variance
 *   [3] vibration_rms
 *   [4] vibration_peak_count
 *   [5] displacement_delta_baseline
 *   [6] crack_state
 *   [7] crack_recent_activation_count
 *
 * @param buf Pointer to initialized ring buffer.
 * @param out_features Array of size SUBSENSE_NUM_FEATURES (8).
 */
void subsense_extract_features(
    const SubSenseWindowBuffer* buf,
    float out_features[SUBSENSE_NUM_FEATURES]
);

/**
 * @brief Normalize features and quantize directly to int8_t for model inference.
 * @param features Raw extracted float features (8).
 * @param config Calibration parameters.
 * @param out_int8 Output INT8 quantized tensor (8).
 */
void subsense_features_to_int8(
    const float features[SUBSENSE_NUM_FEATURES],
    const SubSenseFeatureConfig* config,
    int8_t out_int8[SUBSENSE_NUM_FEATURES]
);

#ifdef __cplusplus
}
#endif

#endif // SUBSENSE_FEATURES_H
