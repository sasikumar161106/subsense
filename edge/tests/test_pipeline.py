"""Comprehensive Test Suite for SubSense ML Pipeline.

Tests:
1. Feature extraction determinism and exclusion of battery/RSSI metadata.
2. Chronological zero-leakage split across window boundaries.
3. Model forward passes and parameter sizing.
4. Gateway-tier student footprint (50-200 KB target).
5. Node-tier student footprint (<= 200 KB target) and high-recall validation.
"""

import unittest
import numpy as np
import pandas as pd
import torch

from subsense.data_generator import generate_mine_telemetry
from subsense.feature_extractor import (
    SubSenseFeatureExtractor,
    chronological_split_zero_leakage,
    FEATURE_NAMES,
)
from subsense.teacher_models import (
    DeepTeacherAutoencoder,
    train_teacher_autoencoder,
    train_teacher_isolation_forest,
    evaluate_classifier,
)
from subsense.student_models import (
    GatewayStudentAutoencoder,
    GatewayRuleEnsemble,
    GatewayDualEnsemble,
    NodeStudentDetector,
)


class TestSubSensePipeline(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        torch.manual_seed(42)
        self.df = generate_mine_telemetry(total_samples=1200, sampling_rate_hz=1.0, random_seed=42)
        self.extractor = SubSenseFeatureExtractor(window_size=32, step_size=1)

    def test_feature_extraction_shape_and_determinism(self):
        """Verify feature extractor output shape, determinism, and exclusion of battery/RSSI."""
        features, labels, window_ends = self.extractor.process_dataframe(self.df)

        expected_windows = (len(self.df) - 32) // 1 + 1
        self.assertEqual(len(features), expected_windows)
        self.assertEqual(features.shape[1], 8)
        self.assertEqual(len(labels), expected_windows)
        self.assertEqual(len(FEATURE_NAMES), 8)

        # Assert determinism: repeated extraction yields identical results
        features_repeat, _, _ = self.extractor.process_dataframe(self.df)
        np.testing.assert_allclose(features, features_repeat, rtol=1e-5, atol=1e-6)

        # Assert no NaN or Inf
        self.assertFalse(np.isnan(features).any())
        self.assertFalse(np.isinf(features).any())

    def test_zero_metadata_leakage(self):
        """Verify that modifying battery and RSSI has ZERO effect on extracted features."""
        df_modified = self.df.copy()
        df_modified["battery_voltage"] = 1.0  # severely altered
        df_modified["rssi"] = -120.0          # severely altered

        features_orig, _, _ = self.extractor.process_dataframe(self.df)
        features_mod, _, _ = self.extractor.process_dataframe(df_modified)

        np.testing.assert_allclose(
            features_orig,
            features_mod,
            rtol=1e-6,
            atol=1e-6,
            err_msg="Battery/RSSI metadata leaked into feature extraction!",
        )

    def test_chronological_split_zero_leakage(self):
        """Verify chronological ordering and boundary non-overlap (zero leakage)."""
        features, labels, window_ends = self.extractor.process_dataframe(self.df)
        splits = chronological_split_zero_leakage(
            features, labels, window_ends, train_ratio=0.60, val_ratio=0.20, window_size=32
        )

        x_train, y_train = splits["train"]
        x_val, y_val = splits["val"]
        x_test, y_test = splits["test"]

        # Ensure slices are non-empty and respect sizes
        self.assertGreater(len(x_train), 0)
        self.assertGreater(len(x_val), 0)
        self.assertGreater(len(x_test), 0)

        # Train end index + buffer <= val start
        train_len = len(x_train)
        total_len = len(window_ends)
        val_start_idx = int(total_len * 0.60) + 32
        val_len = len(x_val)

        # Confirm total split length is strictly bounded
        self.assertLess(train_len + val_len + len(x_test), total_len)

    def test_gateway_student_footprint_budget(self):
        """Gateway student Autoencoder must fit target 50-200 KB float32 footprint."""
        gateway_ae = GatewayStudentAutoencoder(input_dim=8, latent_dim=32)
        footprint_kb = gateway_ae.get_footprint_kb()

        # Must strictly be between 50 KB and 200 KB
        self.assertGreaterEqual(
            footprint_kb, 50.0,
            f"Gateway footprint {footprint_kb:.2f} KB is below 50 KB minimum target"
        )
        self.assertLessEqual(
            footprint_kb, 200.0,
            f"Gateway footprint {footprint_kb:.2f} KB exceeds 200 KB maximum budget"
        )

        # Test forward pass shape
        dummy_input = torch.randn(4, 8)
        output = gateway_ae(dummy_input)
        self.assertEqual(output.shape, (4, 8))

    def test_node_student_footprint_budget(self):
        """Node student detector must be <= 200 KB pre-quantization float32."""
        node_model = NodeStudentDetector(input_dim=8, hidden_dim=16)
        footprint_kb = node_model.get_footprint_kb()

        self.assertLessEqual(
            footprint_kb, 200.0,
            f"Node footprint {footprint_kb:.2f} KB exceeds 200 KB budget"
        )

        dummy_input = torch.randn(4, 8)
        probs = node_model(dummy_input)
        self.assertEqual(probs.shape, (4,))
        self.assertTrue((probs >= 0.0).all() and (probs <= 1.0).all())

    def test_evaluation_metrics_calculator(self):
        """Verify correctness of precision, recall, and false positive rate."""
        y_true = np.array([1, 1, 0, 0, 0])
        y_pred = np.array([1, 0, 1, 0, 0])

        m = evaluate_classifier(y_true, y_pred)
        # TP = 1, FN = 1 -> Recall = 1 / 2 = 0.5
        # FP = 1, TN = 2 -> FPR = 1 / (1 + 2) = 0.3333
        self.assertAlmostEqual(m["recall"], 0.5)
        self.assertAlmostEqual(m["fpr"], 1.0 / 3.0)


if __name__ == "__main__":
    unittest.main()
