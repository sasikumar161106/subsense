/**
 * SubSense Layer 4 - TinyML On-Device Edge Anomaly Inference Engine
 * Target: ESP32-S3 (Xtensa dual-core LX7 @ 240MHz)
 * Constraints: <38KB SRAM footprint, ~4.8ms reference latency
 */

#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SUBSENSE_FEATURE_DIM 12
#define SUBSENSE_MAX_SRAM_BUDGET_BYTES 38912 // 38 KB

typedef struct {
    float anomaly_score;            // Composite score [0.0, 1.0]
    float reconstruction_error;     // MSE between input and output
    bool is_anomaly;                // Score >= 0.65 threshold
    uint32_t estimated_cycles;      // Simulated cycle count on Xtensa LX7
    float estimated_latency_ms;     // Estimated latency at 240MHz
    size_t sram_footprint_bytes;    // Total static + dynamic SRAM consumption
} TinyMLEdgeResult;

/**
 * Initializes the TinyML engine and validates SRAM bounds.
 */
bool tinyml_init(void);

/**
 * Performs on-device int8 quantized inference on a 12-dimensional feature vector.
 */
TinyMLEdgeResult tinyml_infer(const float input[SUBSENSE_FEATURE_DIM]);

/**
 * Returns exact SRAM footprint in bytes.
 */
size_t tinyml_get_sram_footprint(void);

#ifdef __cplusplus
}
#endif
