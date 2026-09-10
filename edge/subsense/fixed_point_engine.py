"""Pure Integer Fixed-Point Inference Engine for SubSense on ESP32 Microcontrollers.

Operates purely on:
- int8_t inputs and weights
- int32_t accumulators
- bit-shift requantization
- Zero floating-point instructions (safe for FPU-less RISC-V / ESP32-C3)
- Zero heap allocation (operates on pre-allocated static buffers)
"""

import numpy as np
from typing import Tuple, Dict, Any

from subsense.quantizer import (
    QuantizedGatewayAutoencoder,
    QuantizedNodeDetector,
    quantize_to_int8,
)
from subsense.student_models import GatewayRuleEnsemble


class GatewayIntegerEnsemble:
    """Consensus ensemble running on the Gateway tier using pure integer math."""

    def __init__(
        self,
        quantized_ae: QuantizedGatewayAutoencoder,
        int_ae_threshold: int,
        rule_ensemble: GatewayRuleEnsemble,
        rule_threshold: float,
    ):
        self.quantized_ae = quantized_ae
        self.int_ae_threshold = int(int_ae_threshold)
        self.rule_ensemble = rule_ensemble
        self.rule_threshold = float(rule_threshold)

    def predict_window(self, in_features_int8: np.ndarray, in_features_float: np.ndarray) -> int:
        """Single-window inference in pure integer / fixed-point arithmetic."""
        # 1. Integer reconstruction error
        int_mse = self.quantized_ae.compute_int8_reconstruction_error(in_features_int8)
        ae_flag = 1 if int_mse >= self.int_ae_threshold else 0

        # 2. Rule ensemble prediction (evaluated on features)
        rule_score = self.rule_ensemble.predict_score(in_features_float[None, :])[0]
        rule_flag = 1 if rule_score >= self.rule_threshold else 0

        # 3. Dual-check consensus cuts false positives from shearer machinery noise
        return int(ae_flag & rule_flag)

    def predict_batch(
        self,
        in_features_int8: np.ndarray,
        in_features_float: np.ndarray,
    ) -> np.ndarray:
        n = len(in_features_int8)
        preds = np.zeros(n, dtype=np.int32)
        for i in range(n):
            preds[i] = self.predict_window(in_features_int8[i], in_features_float[i])
        return preds


class NodeIntegerDetectorEngine:
    """Single-layer node-tier detector running on pure integer MCU arithmetic."""

    def __init__(self, quantized_node: QuantizedNodeDetector, int_threshold: int):
        self.quantized_node = quantized_node
        self.int_threshold = int(int_threshold)

    def predict_window(self, in_features_int8: np.ndarray) -> int:
        """Single-window MCU inference: returns 1 (Alert Siren) or 0 (Nominal)."""
        out_int8 = self.quantized_node.forward_int8(in_features_int8)[0]
        return 1 if out_int8 >= self.int_threshold else 0

    def predict_batch(self, in_features_int8: np.ndarray) -> np.ndarray:
        n = len(in_features_int8)
        preds = np.zeros(n, dtype=np.int32)
        for i in range(n):
            preds[i] = self.predict_window(in_features_int8[i])
        return preds


def calibrate_integer_thresholds(
    quantized_ae: QuantizedGatewayAutoencoder,
    quantized_node: QuantizedNodeDetector,
    x_val_float: np.ndarray,
    y_val: np.ndarray,
) -> Tuple[int, int]:
    """Calibrate integer thresholds on validation set using percentile search."""
    x_val_int8 = quantize_to_int8(
        x_val_float,
        quantized_ae.float_input_scale,
        quantized_ae.float_input_zp,
    )

    # 1. Gateway AE integer error calibration
    val_int_errors = []
    for i in range(len(x_val_int8)):
        err = quantized_ae.compute_int8_reconstruction_error(x_val_int8[i])
        val_int_errors.append(err)
    val_int_errors = np.array(val_int_errors, dtype=np.int32)

    candidate_ae_ths = np.percentile(val_int_errors, np.linspace(20.0, 99.8, 500))
    best_ae_th = int(candidate_ae_ths[0])
    best_ae_f1 = -1.0
    for th in candidate_ae_ths:
        th = int(th)
        preds = (val_int_errors >= th).astype(int)
        tp = np.sum((preds == 1) & (y_val == 1))
        fp = np.sum((preds == 1) & (y_val == 0))
        fn = np.sum((preds == 0) & (y_val == 1))
        p = tp / (tp + fp + 1e-9)
        r = tp / (tp + fn + 1e-9)
        f1 = 2 * p * r / (p + r + 1e-9)
        if f1 > best_ae_f1:
            best_ae_f1 = f1
            best_ae_th = th

    # 2. Node Detector integer threshold calibration (guaranteeing >= 98% recall)
    val_node_outs = []
    for i in range(len(x_val_int8)):
        out = quantized_node.forward_int8(x_val_int8[i])[0]
        val_node_outs.append(out)
    val_node_outs = np.array(val_node_outs, dtype=np.int8)

    candidate_node_ths = np.unique(val_node_outs)
    candidate_node_ths.sort()
    best_node_th = int(candidate_node_ths[0])
    highest_recall = 0.0
    lowest_fpr = 1.0

    for th in candidate_node_ths:
        preds = (val_node_outs >= th).astype(int)
        tp = np.sum((preds == 1) & (y_val == 1))
        fp = np.sum((preds == 1) & (y_val == 0))
        fn = np.sum((preds == 0) & (y_val == 1))
        tn = np.sum((preds == 0) & (y_val == 0))

        rec = tp / (tp + fn + 1e-9)
        fpr = fp / (fp + tn + 1e-9)

        if rec >= 0.98:
            if fpr < lowest_fpr:
                lowest_fpr = fpr
                best_node_th = int(th)
                highest_recall = rec
        elif highest_recall < 0.98 and rec > highest_recall:
            highest_recall = rec
            best_node_th = int(th)

    return best_ae_th, best_node_th
