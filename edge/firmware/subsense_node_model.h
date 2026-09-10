/**
 * @file subsense_node_model.h
 * @brief SubSense Node-Tier High-Recall INT8 Anomaly Detector.
 * @note Auto-generated for ESP32/Arduino sensor nodes. Ultra-compact footprint.
 *       Pure integer arithmetic (zero FPU dependency). Zero dynamic heap allocation.
 */

#ifndef SUBSENSE_NODE_MODEL_H
#define SUBSENSE_NODE_MODEL_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SUBSENSE_NODE_INPUT_DIM      8
#define SUBSENSE_NODE_INT_THRESHOLD  115
#define SUBSENSE_NODE_INPUT_SCALE_F  0.029008f
#define SUBSENSE_NODE_INPUT_ZP       0

// Layer 0: Linear 8 -> 16
#define SUBSENSE_NODE_L0_IN_DIM   8
#define SUBSENSE_NODE_L0_OUT_DIM  16
#define SUBSENSE_NODE_L0_M0       1214904767
#define SUBSENSE_NODE_L0_SHIFT    35
#define SUBSENSE_NODE_L0_IN_ZP    0
#define SUBSENSE_NODE_L0_OUT_ZP   0
#define SUBSENSE_NODE_L0_RELU     1
    static const int8_t subsense_node_w0[128] = {
          -3,    1,  -11,    6,    0,    1,  -79,    4,  -13,    9,    2,   12,   14,   13,  113,    6,
           2,    0,  -11,    5,   -6,    0,  -41,    7,  -12,    0,   -1,    1,    7,   -9,   80,    0,
          -6,    4,    1,    6,  -12,   15,  127,   -5,   13,   -4,    0,   -5,   -7,   -1,  -41,  -11,
           3,    0,   -8,    2,   -3,    2,  -29,    4,   21,    1,    0,  -20,  -13,    0,  -70,  -16,
         -20,    7,    3,   -3,   -6,    3,   91,    0,    9,   -6,   -2,   -8,   -5,   -2,   -1,    6,
         -27,    6,    3,    8,   15,    3,  125,    4,   -5,    4,   -1,    2,    8,    8,  -38,   -7,
           0,    3,    0,   -3,   -8,   13,   54,  -12,    4,    0,   -1,  -15,  -10,    0,    7,    0,
           0,    0,   -9,  -11,    9,    0,  -51,   -5,   -5,   -2,   -3,   -5,   -9,    0,  -61,   -8
    };
    static const int32_t subsense_node_b0[16] = {
            2776,      891,     1048,     1162,    -1528,     -931,      891,    -1791,
            1433,      561,     1731,      197,     -970,     -662,      697,      418
    };

// Layer 1: Linear 16 -> 1
#define SUBSENSE_NODE_L1_IN_DIM   16
#define SUBSENSE_NODE_L1_OUT_DIM  1
#define SUBSENSE_NODE_L1_M0       1998356987
#define SUBSENSE_NODE_L1_SHIFT    34
#define SUBSENSE_NODE_L1_IN_ZP    0
#define SUBSENSE_NODE_L1_OUT_ZP   0
#define SUBSENSE_NODE_L1_RELU     0
    static const int8_t subsense_node_w1[16] = {
        -127,    6,   69,   -2,   57,    0,   42,   -1,  -13,   -7,   22,  -21,   -1,    0,   11,   -8
    };
    static const int32_t subsense_node_b1[1] = {
            7717
    };

/* Static Activation RAM Buffer (Zero Heap Allocation) */
static int8_t s_subsense_node_hidden[16];

static inline void subsense_node_dense_int8(
    const int8_t* in_buf, int in_dim, int in_zp,
    const int8_t* weights, const int32_t* bias, int out_dim,
    int32_t m0, int shift, int out_zp, bool apply_relu,
    int8_t* out_buf
) {
    for (int i = 0; i < out_dim; i++) {
        int32_t acc = bias[i];
        const int8_t* w_row = &weights[i * in_dim];
        for (int j = 0; j < in_dim; j++) {
            acc += ((int32_t)in_buf[j] - in_zp) * (int32_t)w_row[j];
        }
        int64_t scaled = ((int64_t)acc * (int64_t)m0) >> shift;
        int32_t out_val = (int32_t)scaled + out_zp;
        if (apply_relu && out_val < out_zp) {
            out_val = out_zp;
        }
        if (out_val > 127) out_val = 127;
        if (out_val < -128) out_val = -128;
        out_buf[i] = (int8_t)out_val;
    }
}

/**
 * @brief Fast on-device inference for local siren triggering.
 * @param in_features Exactly 8 INT8 quantized sensor features.
 * @return 1 if anomaly detected (FIRE SIREN), 0 if nominal.
 */
static inline uint8_t subsense_node_infer_int8(const int8_t in_features[8]) {
    // Layer 0: 8 -> 16 (ReLU)
    subsense_node_dense_int8(
        in_features, SUBSENSE_NODE_L0_IN_DIM, SUBSENSE_NODE_L0_IN_ZP,
        subsense_node_w0, subsense_node_b0, SUBSENSE_NODE_L0_OUT_DIM,
        SUBSENSE_NODE_L0_M0, SUBSENSE_NODE_L0_SHIFT, SUBSENSE_NODE_L0_OUT_ZP,
        SUBSENSE_NODE_L0_RELU, s_subsense_node_hidden
    );

    // Layer 1: 16 -> 1 (Linear score)
    int8_t out_score;
    subsense_node_dense_int8(
        s_subsense_node_hidden, SUBSENSE_NODE_L1_IN_DIM, SUBSENSE_NODE_L1_IN_ZP,
        subsense_node_w1, subsense_node_b1, SUBSENSE_NODE_L1_OUT_DIM,
        SUBSENSE_NODE_L1_M0, SUBSENSE_NODE_L1_SHIFT, SUBSENSE_NODE_L1_OUT_ZP,
        SUBSENSE_NODE_L1_RELU, &out_score
    );

    // Threshold check for local siren activation
    return (out_score >= SUBSENSE_NODE_INT_THRESHOLD) ? 1 : 0;
}

#ifdef __cplusplus
}
#endif

#endif // SUBSENSE_NODE_MODEL_H
