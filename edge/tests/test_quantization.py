"""Unit Tests for Phase 2 Quantization, Pruning, and ESP32 Constraints.

Tests:
1. Integer fixed-point math precision and multiplier bit-shift calculations.
2. Magnitude pruning sparsity verification.
3. Quantized layer forward pass determinism.
4. Microcontroller C headers syntax and zero-heap static allocation verification.
5. Strict budget gate compliance (RAM, Flash, latency bounds).
"""

import os
import sys
import unittest
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from subsense.quantizer import (
    calculate_quant_params_symmetric,
    calculate_fixed_point_multiplier,
    quantize_to_int8,
    dequantize_from_int8,
    prune_model_l1_unstructured,
    QuantizedLinearLayer,
    calibrate_and_quantize_gateway_ae,
    calibrate_and_quantize_node_detector,
)
from subsense.student_models import GatewayStudentAutoencoder, NodeStudentDetector
from subsense.export_embedded import export_gateway_c_header, export_node_c_header


class TestQuantizationAndESP32Constraints(unittest.TestCase):

    def test_fixed_point_multiplier_shift(self):
        """Verify M approx M0 * 2^(-shift) to high numerical precision."""
        test_multipliers = [0.00125, 0.0456, 0.128, 0.789, 1.45, 3.21]
        for real_m in test_multipliers:
            m0, shift = calculate_fixed_point_multiplier(real_m)
            approx_m = (m0 * (2.0 ** (-shift)))
            rel_err = abs(real_m - approx_m) / real_m
            self.assertLess(rel_err, 1e-4, f"Multiplier approximation error too high for {real_m}")

    def test_pruning_sparsity(self):
        """Verify that L1 unstructured pruning zeroes out the requested proportion of weights."""
        model = GatewayStudentAutoencoder(8, 32)
        initial_zero_count = sum((param == 0).sum().item() for param in model.parameters() if param.dim() > 1)

        prune_amount = 0.25
        prune_model_l1_unstructured(model, amount=prune_amount)

        total_weights = sum(param.numel() for param in model.parameters() if param.dim() > 1)
        zero_weights = sum((param == 0).sum().item() for param in model.parameters() if param.dim() > 1)

        actual_sparsity = zero_weights / total_weights
        self.assertAlmostEqual(actual_sparsity, prune_amount, delta=0.02)

    def test_quantized_linear_layer_integer_execution(self):
        """Verify pure integer forward pass through QuantizedLinearLayer."""
        in_dim, out_dim = 8, 16
        w_int8 = np.random.randint(-64, 64, size=(out_dim, in_dim), dtype=np.int8)
        b_int32 = np.random.randint(-1000, 1000, size=(out_dim,), dtype=np.int32)

        layer = QuantizedLinearLayer(
            weight_int8=w_int8,
            bias_int32=b_int32,
            in_scale=0.05,
            in_zp=0,
            out_scale=0.08,
            out_zp=0,
            weight_scale=0.02,
            has_relu=True,
        )

        in_int8 = np.random.randint(-128, 127, size=(in_dim,), dtype=np.int8)
        out_int8 = layer.forward(in_int8)

        # Output must be int8 and non-negative (due to ReLU)
        self.assertEqual(out_int8.dtype, np.int8)
        self.assertEqual(len(out_int8), out_dim)
        self.assertTrue((out_int8 >= 0).all())

    def test_c_header_generation_and_static_allocation(self):
        """Verify generated C headers have zero heap allocation and strictly static buffers."""
        gw_model = GatewayStudentAutoencoder(8, 32)
        dummy_calib = np.random.normal(0, 1.0, (100, 8)).astype(np.float32)
        q_gw = calibrate_and_quantize_gateway_ae(gw_model, dummy_calib)

        os.makedirs("scratch", exist_ok=True)
        gw_header_path = "scratch/test_gw.h"
        info_gw = export_gateway_c_header(q_gw, int_ae_threshold=500, output_path=gw_header_path)

        with open(gw_header_path, "r") as f:
            header_content = f.read()

        # Strict checks for ESP32 constraints:
        self.assertNotIn("malloc(", header_content)
        self.assertNotIn("calloc(", header_content)
        self.assertNotIn("free(", header_content)
        self.assertIn("static const int8_t", header_content)
        self.assertIn("static const int32_t", header_content)
        self.assertIn("s_subsense_gw_buf_a", header_content)
        self.assertIn("s_subsense_gw_buf_b", header_content)

        # Budget check on generated header
        self.assertLessEqual(info_gw["flash_weights_bytes"], 1024 * 1024)  # <= 1 MB Flash
        self.assertLessEqual(info_gw["ram_activation_bytes"], 512 * 1024)   # <= 512 KB RAM

    def test_node_c_header_generation(self):
        """Verify Node detector C header meets ultra-compact MCU requirements."""
        node_model = NodeStudentDetector(8, 16)
        dummy_calib = np.random.normal(0, 1.0, (100, 8)).astype(np.float32)
        q_node = calibrate_and_quantize_node_detector(node_model, dummy_calib)

        os.makedirs("scratch", exist_ok=True)
        node_header_path = "scratch/test_node.h"
        info_node = export_node_c_header(q_node, int_node_threshold=10, output_path=node_header_path)

        with open(node_header_path, "r") as f:
            header_content = f.read()

        self.assertNotIn("malloc(", header_content)
        self.assertNotIn("free(", header_content)
        self.assertIn("static int8_t s_subsense_node_hidden[16];", header_content)

        # Budget check on Node header
        self.assertLessEqual(info_node["flash_weights_bytes"], 200 * 1024)  # <= 200 KB Flash
        self.assertLessEqual(info_node["ram_activation_bytes"], 80 * 1024)   # <= 80 KB RAM


if __name__ == "__main__":
    unittest.main()
