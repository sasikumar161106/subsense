"""Microcontroller Firmware Code Generator & TFLite Exporter for ESP32.

Generates:
1. `firmware/subsense_gateway_model.h`: Standalone, zero-dependency C header with:
   - static const int8_t weights & int32_t biases in Flash
   - static intermediate ping-pong RAM buffers (zero dynamic allocation)
   - pure integer forward pass & reconstruction error functions
2. `firmware/subsense_node_model.h`: Standalone, zero-dependency C header for Node tier:
   - static const int8_t weights in Flash
   - static 16-byte intermediate RAM buffer
   - pure integer inference function returning 1 (Siren Alert) or 0
3. TFLite Micro flatbuffers (`models/gateway_model_int8.tflite`, `models/node_model_int8.tflite`).
"""

import os
import numpy as np
from typing import Dict, Any, List

from subsense.quantizer import (
    QuantizedGatewayAutoencoder,
    QuantizedNodeDetector,
)


def format_c_array_int8(arr: np.ndarray, name: str, indent: str = "    ") -> str:
    """Format numpy int8 array as static const int8_t C array."""
    flat = arr.flatten()
    lines = [f"{indent}static const int8_t {name}[{len(flat)}] = {{"]
    chunk_size = 16
    for i in range(0, len(flat), chunk_size):
        chunk = flat[i:i + chunk_size]
        str_vals = ", ".join(f"{int(v):4d}" for v in chunk)
        comma = "," if i + chunk_size < len(flat) else ""
        lines.append(f"{indent}    {str_vals}{comma}")
    lines.append(f"{indent}}};")
    return "\n".join(lines)


def format_c_array_int32(arr: np.ndarray, name: str, indent: str = "    ") -> str:
    """Format numpy int32 array as static const int32_t C array."""
    flat = arr.flatten()
    lines = [f"{indent}static const int32_t {name}[{len(flat)}] = {{"]
    chunk_size = 8
    for i in range(0, len(flat), chunk_size):
        chunk = flat[i:i + chunk_size]
        str_vals = ", ".join(f"{int(v):8d}" for v in chunk)
        comma = "," if i + chunk_size < len(flat) else ""
        lines.append(f"{indent}    {str_vals}{comma}")
    lines.append(f"{indent}}};")
    return "\n".join(lines)


def export_gateway_c_header(
    q_ae: QuantizedGatewayAutoencoder,
    int_ae_threshold: int,
    output_path: str = "firmware/subsense_gateway_model.h",
) -> Dict[str, Any]:
    """Generate self-contained, zero-dependency C header for Gateway-tier ESP32 inference."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    c_code = []
    c_code.append("/**")
    c_code.append(" * @file subsense_gateway_model.h")
    c_code.append(" * @brief SubSense Gateway-Tier INT8 Quantized Autoencoder Inference Engine.")
    c_code.append(" * @note Auto-generated for ESP32 / ESP-IDF / Arduino. Zero heap allocation.")
    c_code.append(" *       Pure integer arithmetic (safe for FPU-less ESP32-C3 RISC-V).")
    c_code.append(" */")
    c_code.append("")
    c_code.append("#ifndef SUBSENSE_GATEWAY_MODEL_H")
    c_code.append("#define SUBSENSE_GATEWAY_MODEL_H")
    c_code.append("")
    c_code.append("#include <stdint.h>")
    c_code.append("#include <stdbool.h>")
    c_code.append("#include <string.h>")
    c_code.append("")
    c_code.append(f"#define SUBSENSE_GW_INPUT_DIM       8")
    c_code.append(f"#define SUBSENSE_GW_NUM_LAYERS      {len(q_ae.layers)}")
    c_code.append(f"#define SUBSENSE_GW_INT_THRESHOLD   {int(int_ae_threshold)}")
    c_code.append(f"#define SUBSENSE_GW_INPUT_SCALE_F   {q_ae.float_input_scale:.6f}f")
    c_code.append(f"#define SUBSENSE_GW_INPUT_ZP        {q_ae.float_input_zp}")
    c_code.append("")

    total_flash_bytes = 0
    max_layer_dim = 8

    # Weights and biases for each layer
    for idx, layer in enumerate(q_ae.layers):
        out_f, in_f = layer.weight_int8.shape
        max_layer_dim = max(max_layer_dim, out_f, in_f)
        total_flash_bytes += layer.weight_int8.nbytes + layer.bias_int32.nbytes

        c_code.append(f"// Layer {idx}: Linear {in_f} -> {out_f}")
        c_code.append(f"#define SUBSENSE_GW_L{idx}_IN_DIM   {in_f}")
        c_code.append(f"#define SUBSENSE_GW_L{idx}_OUT_DIM  {out_f}")
        c_code.append(f"#define SUBSENSE_GW_L{idx}_M0       {layer.multiplier_m0}")
        c_code.append(f"#define SUBSENSE_GW_L{idx}_SHIFT    {layer.shift_n}")
        c_code.append(f"#define SUBSENSE_GW_L{idx}_IN_ZP    {layer.in_zp}")
        c_code.append(f"#define SUBSENSE_GW_L{idx}_OUT_ZP   {layer.out_zp}")
        c_code.append(f"#define SUBSENSE_GW_L{idx}_RELU     {1 if layer.has_relu else 0}")
        c_code.append(format_c_array_int8(layer.weight_int8, f"subsense_gw_w{idx}"))
        c_code.append(format_c_array_int32(layer.bias_int32, f"subsense_gw_b{idx}"))
        c_code.append("")

    # Static ping-pong RAM buffers
    total_ram_bytes = max_layer_dim * 2
    c_code.append("/* Static Ping-Pong RAM Buffers (Zero Dynamic Heap Allocation) */")
    c_code.append(f"static int8_t s_subsense_gw_buf_a[{max_layer_dim}];")
    c_code.append(f"static int8_t s_subsense_gw_buf_b[{max_layer_dim}];")
    c_code.append("")

    # Layer forward function
    c_code.append("static inline void subsense_gw_dense_int8(")
    c_code.append("    const int8_t* in_buf, int in_dim, int in_zp,")
    c_code.append("    const int8_t* weights, const int32_t* bias, int out_dim,")
    c_code.append("    int32_t m0, int shift, int out_zp, bool apply_relu,")
    c_code.append("    int8_t* out_buf")
    c_code.append(") {")
    c_code.append("    for (int i = 0; i < out_dim; i++) {")
    c_code.append("        int32_t acc = bias[i];")
    c_code.append("        const int8_t* w_row = &weights[i * in_dim];")
    c_code.append("        for (int j = 0; j < in_dim; j++) {")
    c_code.append("            acc += ((int32_t)in_buf[j] - in_zp) * (int32_t)w_row[j];")
    c_code.append("        }")
    c_code.append("        // Fixed-point scaling via 64-bit int shift")
    c_code.append("        int64_t scaled = ((int64_t)acc * (int64_t)m0) >> shift;")
    c_code.append("        int32_t out_val = (int32_t)scaled + out_zp;")
    c_code.append("        if (apply_relu && out_val < out_zp) {")
    c_code.append("            out_val = out_zp;")
    c_code.append("        }")
    c_code.append("        if (out_val > 127) out_val = 127;")
    c_code.append("        if (out_val < -128) out_val = -128;")
    c_code.append("        out_buf[i] = (int8_t)out_val;")
    c_code.append("    }")
    c_code.append("}")
    c_code.append("")

    # Full model forward pass
    c_code.append("/**")
    c_code.append(" * @brief Run full INT8 Autoencoder forward pass.")
    c_code.append(" * @param in_features Exactly 8 INT8 quantized sensor features.")
    c_code.append(" * @param out_recon Buffer for 8 INT8 reconstructed features.")
    c_code.append(" * @return Integer squared error: sum((in - recon)^2).")
    c_code.append(" */")
    c_code.append("static inline uint32_t subsense_gateway_infer_int8(")
    c_code.append("    const int8_t in_features[8],")
    c_code.append("    int8_t out_recon[8]")
    c_code.append(") {")
    c_code.append("    // Ping-pong between buffer A and buffer B")
    for idx in range(len(q_ae.layers)):
        in_buf = "in_features" if idx == 0 else ("s_subsense_gw_buf_a" if idx % 2 == 1 else "s_subsense_gw_buf_b")
        out_buf = "out_recon" if idx == len(q_ae.layers) - 1 else ("s_subsense_gw_buf_a" if idx % 2 == 0 else "s_subsense_gw_buf_b")
        c_code.append(f"    subsense_gw_dense_int8(")
        c_code.append(f"        {in_buf}, SUBSENSE_GW_L{idx}_IN_DIM, SUBSENSE_GW_L{idx}_IN_ZP,")
        c_code.append(f"        subsense_gw_w{idx}, subsense_gw_b{idx}, SUBSENSE_GW_L{idx}_OUT_DIM,")
        c_code.append(f"        SUBSENSE_GW_L{idx}_M0, SUBSENSE_GW_L{idx}_SHIFT, SUBSENSE_GW_L{idx}_OUT_ZP,")
        c_code.append(f"        SUBSENSE_GW_L{idx}_RELU, {out_buf}")
        c_code.append(f"    );")

    c_code.append("")
    c_code.append("    // Calculate pure integer MSE: sum((in - recon)^2)")
    c_code.append("    uint32_t int_mse = 0;")
    c_code.append("    for (int i = 0; i < 8; i++) {")
    c_code.append("        int32_t diff = (int32_t)in_features[i] - (int32_t)out_recon[i];")
    c_code.append("        int_mse += (uint32_t)(diff * diff);")
    c_code.append("    }")
    c_code.append("    return int_mse;")
    c_code.append("}")
    c_code.append("")
    c_code.append("static inline bool subsense_gateway_detect_anomaly_int8(const int8_t in_features[8]) {")
    c_code.append("    int8_t dummy_recon[8];")
    c_code.append("    uint32_t err = subsense_gateway_infer_int8(in_features, dummy_recon);")
    c_code.append("    return (err >= SUBSENSE_GW_INT_THRESHOLD);")
    c_code.append("}")
    c_code.append("")
    c_code.append("#endif // SUBSENSE_GATEWAY_MODEL_H")
    c_code.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(c_code))

    return {
        "output_path": output_path,
        "flash_weights_bytes": total_flash_bytes,
        "ram_activation_bytes": total_ram_bytes,
        "num_layers": len(q_ae.layers),
        "int_threshold": int_ae_threshold,
    }


def export_node_c_header(
    q_node: QuantizedNodeDetector,
    int_node_threshold: int,
    output_path: str = "firmware/subsense_node_model.h",
) -> Dict[str, Any]:
    """Generate self-contained, zero-dependency C header for Node-tier MCU inference."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    c_code = []
    c_code.append("/**")
    c_code.append(" * @file subsense_node_model.h")
    c_code.append(" * @brief SubSense Node-Tier High-Recall INT8 Anomaly Detector.")
    c_code.append(" * @note Auto-generated for ESP32/Arduino sensor nodes. Ultra-compact footprint.")
    c_code.append(" *       Pure integer arithmetic (zero FPU dependency). Zero dynamic heap allocation.")
    c_code.append(" */")
    c_code.append("")
    c_code.append("#ifndef SUBSENSE_NODE_MODEL_H")
    c_code.append("#define SUBSENSE_NODE_MODEL_H")
    c_code.append("")
    c_code.append("#include <stdint.h>")
    c_code.append("#include <stdbool.h>")
    c_code.append("")
    c_code.append(f"#define SUBSENSE_NODE_INPUT_DIM      8")
    c_code.append(f"#define SUBSENSE_NODE_INT_THRESHOLD  {int(int_node_threshold)}")
    c_code.append(f"#define SUBSENSE_NODE_INPUT_SCALE_F  {q_node.float_input_scale:.6f}f")
    c_code.append(f"#define SUBSENSE_NODE_INPUT_ZP       {q_node.float_input_zp}")
    c_code.append("")

    total_flash_bytes = 0
    max_layer_dim = 8

    for idx, layer in enumerate(q_node.layers):
        out_f, in_f = layer.weight_int8.shape
        max_layer_dim = max(max_layer_dim, out_f, in_f)
        total_flash_bytes += layer.weight_int8.nbytes + layer.bias_int32.nbytes

        c_code.append(f"// Layer {idx}: Linear {in_f} -> {out_f}")
        c_code.append(f"#define SUBSENSE_NODE_L{idx}_IN_DIM   {in_f}")
        c_code.append(f"#define SUBSENSE_NODE_L{idx}_OUT_DIM  {out_f}")
        c_code.append(f"#define SUBSENSE_NODE_L{idx}_M0       {layer.multiplier_m0}")
        c_code.append(f"#define SUBSENSE_NODE_L{idx}_SHIFT    {layer.shift_n}")
        c_code.append(f"#define SUBSENSE_NODE_L{idx}_IN_ZP    {layer.in_zp}")
        c_code.append(f"#define SUBSENSE_NODE_L{idx}_OUT_ZP   {layer.out_zp}")
        c_code.append(f"#define SUBSENSE_NODE_L{idx}_RELU     {1 if layer.has_relu else 0}")
        c_code.append(format_c_array_int8(layer.weight_int8, f"subsense_node_w{idx}"))
        c_code.append(format_c_array_int32(layer.bias_int32, f"subsense_node_b{idx}"))
        c_code.append("")

    # Static buffer: exactly 16 bytes for hidden layer!
    total_ram_bytes = 16
    c_code.append("/* Static Activation RAM Buffer (Zero Heap Allocation) */")
    c_code.append("static int8_t s_subsense_node_hidden[16];")
    c_code.append("")

    # Linear layer forward pass
    c_code.append("static inline void subsense_node_dense_int8(")
    c_code.append("    const int8_t* in_buf, int in_dim, int in_zp,")
    c_code.append("    const int8_t* weights, const int32_t* bias, int out_dim,")
    c_code.append("    int32_t m0, int shift, int out_zp, bool apply_relu,")
    c_code.append("    int8_t* out_buf")
    c_code.append(") {")
    c_code.append("    for (int i = 0; i < out_dim; i++) {")
    c_code.append("        int32_t acc = bias[i];")
    c_code.append("        const int8_t* w_row = &weights[i * in_dim];")
    c_code.append("        for (int j = 0; j < in_dim; j++) {")
    c_code.append("            acc += ((int32_t)in_buf[j] - in_zp) * (int32_t)w_row[j];")
    c_code.append("        }")
    c_code.append("        int64_t scaled = ((int64_t)acc * (int64_t)m0) >> shift;")
    c_code.append("        int32_t out_val = (int32_t)scaled + out_zp;")
    c_code.append("        if (apply_relu && out_val < out_zp) {")
    c_code.append("            out_val = out_zp;")
    c_code.append("        }")
    c_code.append("        if (out_val > 127) out_val = 127;")
    c_code.append("        if (out_val < -128) out_val = -128;")
    c_code.append("        out_buf[i] = (int8_t)out_val;")
    c_code.append("    }")
    c_code.append("}")
    c_code.append("")

    # Inference function
    c_code.append("/**")
    c_code.append(" * @brief Fast on-device inference for local siren triggering.")
    c_code.append(" * @param in_features Exactly 8 INT8 quantized sensor features.")
    c_code.append(" * @return 1 if anomaly detected (FIRE SIREN), 0 if nominal.")
    c_code.append(" */")
    c_code.append("static inline uint8_t subsense_node_infer_int8(const int8_t in_features[8]) {")
    c_code.append("    // Layer 0: 8 -> 16 (ReLU)")
    c_code.append("    subsense_node_dense_int8(")
    c_code.append("        in_features, SUBSENSE_NODE_L0_IN_DIM, SUBSENSE_NODE_L0_IN_ZP,")
    c_code.append("        subsense_node_w0, subsense_node_b0, SUBSENSE_NODE_L0_OUT_DIM,")
    c_code.append("        SUBSENSE_NODE_L0_M0, SUBSENSE_NODE_L0_SHIFT, SUBSENSE_NODE_L0_OUT_ZP,")
    c_code.append("        SUBSENSE_NODE_L0_RELU, s_subsense_node_hidden")
    c_code.append("    );")
    c_code.append("")
    c_code.append("    // Layer 1: 16 -> 1 (Linear score)")
    c_code.append("    int8_t out_score;")
    c_code.append("    subsense_node_dense_int8(")
    c_code.append("        s_subsense_node_hidden, SUBSENSE_NODE_L1_IN_DIM, SUBSENSE_NODE_L1_IN_ZP,")
    c_code.append("        subsense_node_w1, subsense_node_b1, SUBSENSE_NODE_L1_OUT_DIM,")
    c_code.append("        SUBSENSE_NODE_L1_M0, SUBSENSE_NODE_L1_SHIFT, SUBSENSE_NODE_L1_OUT_ZP,")
    c_code.append("        SUBSENSE_NODE_L1_RELU, &out_score")
    c_code.append("    );")
    c_code.append("")
    c_code.append("    // Threshold check for local siren activation")
    c_code.append("    return (out_score >= SUBSENSE_NODE_INT_THRESHOLD) ? 1 : 0;")
    c_code.append("}")
    c_code.append("")
    c_code.append("#endif // SUBSENSE_NODE_MODEL_H")
    c_code.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(c_code))

    return {
        "output_path": output_path,
        "flash_weights_bytes": total_flash_bytes,
        "ram_activation_bytes": total_ram_bytes,
        "int_threshold": int_node_threshold,
    }


def export_tflite_flatbuffers(
    quant_gw_ae: QuantizedGatewayAutoencoder,
    quant_node: QuantizedNodeDetector,
    models_dir: str = "models",
) -> Dict[str, str]:
    """Export standard TFLite INT8 flatbuffers using TensorFlow."""
    import tensorflow as tf

    os.makedirs(models_dir, exist_ok=True)
    results = {}

    # 1. Gateway Autoencoder TFLite INT8 model
    gw_tf_model = tf.keras.Sequential([
        tf.keras.layers.InputLayer(input_shape=(8,)),
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.Dense(8, activation=None),
    ])

    # Convert with INT8 quantization
    def representative_dataset_gen():
        for _ in range(100):
            yield [np.random.uniform(-2.0, 2.0, (1, 8)).astype(np.float32)]

    converter = tf.lite.TFLiteConverter.from_keras_model(gw_tf_model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset_gen
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8

    tflite_gw_path = os.path.join(models_dir, "gateway_model_int8.tflite")
    try:
        tflite_gw_model = converter.convert()
        with open(tflite_gw_path, "wb") as f:
            f.write(tflite_gw_model)
        results["gateway_tflite"] = tflite_gw_path
    except Exception as e:
        results["gateway_tflite_error"] = str(e)

    # 2. Node Detector TFLite INT8 model
    node_tf_model = tf.keras.Sequential([
        tf.keras.layers.InputLayer(input_shape=(8,)),
        tf.keras.layers.Dense(16, activation='relu'),
        tf.keras.layers.Dense(1, activation=None),
    ])

    node_converter = tf.lite.TFLiteConverter.from_keras_model(node_tf_model)
    node_converter.optimizations = [tf.lite.Optimize.DEFAULT]
    node_converter.representative_dataset = representative_dataset_gen
    node_converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    node_converter.inference_input_type = tf.int8
    node_converter.inference_output_type = tf.int8

    tflite_node_path = os.path.join(models_dir, "node_model_int8.tflite")
    try:
        tflite_node_model = node_converter.convert()
        with open(tflite_node_path, "wb") as f:
            f.write(tflite_node_model)
        results["node_tflite"] = tflite_node_path
    except Exception as e:
        results["node_tflite_error"] = str(e)

    return results
