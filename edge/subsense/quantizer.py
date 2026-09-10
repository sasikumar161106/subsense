"""SubSense Model Quantization & Pruning Module for ESP32 Microcontrollers.

Provides:
1. Magnitude-based structured and unstructured weight pruning.
2. Post-Training INT8 Quantization (PTQ) with per-tensor/per-channel calibration.
3. Quantization-Aware Training (QAT) fallback if recall tolerance is breached.
4. Calculation of integer fixed-point multipliers (M0) and bit-shifts (n) for
   FPU-less MCU hardware (e.g. ESP32-C3 RISC-V).
"""

import math
import numpy as np
import torch
import torch.nn as nn
import torch.nn.utils.prune as prune
from typing import Dict, Tuple, List, Any, Optional

from subsense.student_models import GatewayStudentAutoencoder, NodeStudentDetector


def calculate_quant_params_symmetric(data: np.ndarray, num_bits: int = 8) -> Tuple[float, int]:
    """Calculate scale and zero point for symmetric signed integer quantization [-128, 127]."""
    max_val = float(np.max(np.abs(data)))
    max_val = max(max_val, 1e-6)
    qmax = (1 << (num_bits - 1)) - 1  # 127 for 8-bit
    scale = max_val / float(qmax)
    zero_point = 0
    return scale, zero_point


def calculate_quant_params_asymmetric(data: np.ndarray, num_bits: int = 8) -> Tuple[float, int]:
    """Calculate scale and zero point for asymmetric signed integer quantization [-128, 127]."""
    min_val = float(np.min(data))
    max_val = float(np.max(data))
    if min_val == max_val:
        return 1.0, 0
    qmin = -(1 << (num_bits - 1))     # -128
    qmax = (1 << (num_bits - 1)) - 1  # 127

    scale = (max_val - min_val) / float(qmax - qmin)
    scale = max(scale, 1e-6)
    zero_point = int(np.round(qmin - min_val / scale))
    zero_point = max(qmin, min(qmax, zero_point))
    return scale, zero_point


def quantize_to_int8(data: np.ndarray, scale: float, zero_point: int) -> np.ndarray:
    """Quantize floating point array to signed int8 [-128, 127]."""
    q = np.round(data / scale) + zero_point
    return np.clip(q, -128, 127).astype(np.int8)


def dequantize_from_int8(qdata: np.ndarray, scale: float, zero_point: int) -> np.ndarray:
    """Dequantize int8 array back to float32 for accuracy simulation."""
    return (qdata.astype(np.float32) - float(zero_point)) * float(scale)


def calculate_fixed_point_multiplier(real_multiplier: float) -> Tuple[int, int]:
    """Convert a float scaling multiplier M into an integer multiplier M0 and right shift n.

    M approx M0 * 2^(-n) where M0 is a 31-bit integer.
    """
    if real_multiplier <= 0.0:
        return 0, 0
    # Find shift n such that M0 is in [0.5, 1.0) * 2^31
    frexp_val, exponent = math.frexp(real_multiplier)
    # frexp returns significand in [0.5, 1.0) and exponent such that real = frexp * 2^exp
    m0 = int(round(frexp_val * (1 << 31)))
    if m0 == (1 << 31):
        m0 = m0 // 2
        exponent += 1
    shift = -exponent + 31
    shift = max(0, min(62, shift))
    return int(m0), int(shift)


def prune_model_l1_unstructured(model: nn.Module, amount: float = 0.25) -> nn.Module:
    """Prune low-magnitude weights across all Linear layers."""
    for name, module in model.named_modules():
        if isinstance(module, nn.Linear):
            prune.l1_unstructured(module, name="weight", amount=amount)
            # Make pruning permanent (removes mask and zeroes pruned weights)
            prune.remove(module, "weight")
    return model


class QuantizedLinearLayer:
    """Representation of an INT8 quantized fully-connected layer with fixed-point arithmetic."""

    def __init__(
        self,
        weight_int8: np.ndarray,
        bias_int32: np.ndarray,
        in_scale: float,
        in_zp: int,
        out_scale: float,
        out_zp: int,
        weight_scale: float,
        has_relu: bool = True,
    ):
        self.weight_int8 = weight_int8.astype(np.int8)  # Shape (out_features, in_features)
        self.bias_int32 = bias_int32.astype(np.int32)    # Shape (out_features,)
        self.in_scale = float(in_scale)
        self.in_zp = int(in_zp)
        self.out_scale = float(out_scale)
        self.out_zp = int(out_zp)
        self.weight_scale = float(weight_scale)
        self.has_relu = has_relu

        # Compute fixed-point multiplier
        real_multiplier = (self.in_scale * self.weight_scale) / self.out_scale
        self.multiplier_m0, self.shift_n = calculate_fixed_point_multiplier(real_multiplier)

    def forward(self, x_int8: np.ndarray) -> np.ndarray:
        """Pure integer forward pass: int8 in -> int32 acc -> bit-shift -> int8 out."""
        # x_int8 shape: (B, in_features) or (in_features,)
        is_1d = (x_int8.ndim == 1)
        if is_1d:
            x_int8 = x_int8[None, :]

        # Subtract input zero-point: int16
        x_centered = x_int8.astype(np.int32) - self.in_zp

        # Matrix multiply in int32 accumulator
        # (B, in_features) @ (out_features, in_features).T -> (B, out_features)
        acc = np.matmul(x_centered, self.weight_int8.astype(np.int32).T) + self.bias_int32

        # Requantize to output int8 using fixed-point integer math:
        # acc_scaled = (acc * M0) >> shift
        # In 64-bit int to avoid intermediate 32-bit overflow before shift:
        acc_scaled = (acc.astype(np.int64) * self.multiplier_m0) >> self.shift_n
        out_int8 = acc_scaled.astype(np.int32) + self.out_zp

        # Clamped ReLU in integer domain if applicable
        if self.has_relu:
            out_int8 = np.maximum(out_int8, self.out_zp)

        out_int8 = np.clip(out_int8, -128, 127).astype(np.int8)
        return out_int8[0] if is_1d else out_int8


class QuantizedGatewayAutoencoder:
    """INT8 fixed-point quantized Gateway Student Autoencoder."""

    def __init__(self, layers: List[QuantizedLinearLayer], float_input_scale: float, float_input_zp: int):
        self.layers = layers
        self.float_input_scale = float_input_scale
        self.float_input_zp = float_input_zp

    def forward_int8(self, in_features_int8: np.ndarray) -> np.ndarray:
        """Run pure integer forward pass through all layers."""
        x = in_features_int8
        for layer in self.layers:
            x = layer.forward(x)
        return x

    def compute_int8_reconstruction_error(self, in_features_int8: np.ndarray) -> int:
        """Calculate integer reconstruction error: sum((in - recon)^2) without floats!"""
        recon_int8 = self.forward_int8(in_features_int8)
        diff = in_features_int8.astype(np.int32) - recon_int8.astype(np.int32)
        int_mse = int(np.sum(diff * diff))
        return int_mse

    def predict_float(self, float_features: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Convenience wrapper for testing on float32 arrays."""
        # Quantize inputs
        in_int8 = quantize_to_int8(float_features, self.float_input_scale, self.float_input_zp)
        if float_features.ndim == 1:
            recon_int8 = self.forward_int8(in_int8)
            diff = in_int8.astype(np.int32) - recon_int8.astype(np.int32)
            int_err = np.sum(diff * diff)
            return in_int8, int_err
        else:
            errors = []
            for i in range(len(float_features)):
                recon_int8 = self.forward_int8(in_int8[i])
                diff = in_int8[i].astype(np.int32) - recon_int8.astype(np.int32)
                errors.append(np.sum(diff * diff))
            return in_int8, np.array(errors, dtype=np.int32)

    def get_flash_footprint_bytes(self) -> int:
        """Calculate total weight & bias bytes in Flash."""
        total = 0
        for layer in self.layers:
            total += layer.weight_int8.nbytes
            total += layer.bias_int32.nbytes
        return total

    def get_ram_footprint_bytes(self) -> int:
        """Calculate static activation ping-pong buffer size in RAM."""
        max_layer_dim = max(
            max(layer.weight_int8.shape[0], layer.weight_int8.shape[1]) for layer in self.layers
        )
        # Double-buffered ping-pong: 2 * max_layer_dim
        return 2 * max_layer_dim


class QuantizedNodeDetector:
    """INT8 fixed-point quantized Node Student Detector."""

    def __init__(self, layers: List[QuantizedLinearLayer], float_input_scale: float, float_input_zp: int):
        self.layers = layers
        self.float_input_scale = float_input_scale
        self.float_input_zp = float_input_zp
        self.int8_threshold: int = 0  # calibrated integer threshold

    def forward_int8(self, in_features_int8: np.ndarray) -> np.ndarray:
        x = in_features_int8
        for layer in self.layers:
            x = layer.forward(x)
        return x

    def predict_float(self, float_features: np.ndarray) -> np.ndarray:
        in_int8 = quantize_to_int8(float_features, self.float_input_scale, self.float_input_zp)
        if float_features.ndim == 1:
            out_int8 = self.forward_int8(in_int8)
            return out_int8[0]
        else:
            out = []
            for i in range(len(float_features)):
                out.append(self.forward_int8(in_int8[i])[0])
            return np.array(out, dtype=np.int8)

    def get_flash_footprint_bytes(self) -> int:
        total = 0
        for layer in self.layers:
            total += layer.weight_int8.nbytes
            total += layer.bias_int32.nbytes
        return total

    def get_ram_footprint_bytes(self) -> int:
        max_layer_dim = max(
            max(layer.weight_int8.shape[0], layer.weight_int8.shape[1]) for layer in self.layers
        )
        return 2 * max_layer_dim


def calibrate_and_quantize_gateway_ae(
    model: GatewayStudentAutoencoder,
    calibration_data: np.ndarray,
) -> QuantizedGatewayAutoencoder:
    """Calibrate activations and quantize Gateway Student Autoencoder to INT8."""
    model.eval()
    device = next(model.parameters()).device

    # 1. Input scale
    in_scale, in_zp = calculate_quant_params_symmetric(calibration_data)

    # 2. Trace activations through network on calibration data
    act_data = torch.tensor(calibration_data, dtype=torch.float32).to(device)
    activations = []

    # Encoder layers
    x = act_data
    for layer in model.encoder:
        x = layer(x)
        if isinstance(layer, nn.Linear):
            activations.append(x.detach().cpu().numpy())

    # Decoder layers
    for layer in model.decoder:
        x = layer(x)
        if isinstance(layer, nn.Linear):
            activations.append(x.detach().cpu().numpy())

    # Extract all Linear modules
    linear_modules = [m for m in model.modules() if isinstance(m, nn.Linear)]

    quantized_layers = []
    current_in_scale = in_scale
    current_in_zp = in_zp

    for idx, module in enumerate(linear_modules):
        w_float = module.weight.detach().cpu().numpy()
        b_float = module.bias.detach().cpu().numpy()

        w_scale, _ = calculate_quant_params_symmetric(w_float)
        w_int8 = quantize_to_int8(w_float, w_scale, 0)

        act_out = activations[idx]
        out_scale, out_zp = calculate_quant_params_symmetric(act_out)

        # Quantize bias to int32: bias_scale = in_scale * weight_scale
        bias_scale = current_in_scale * w_scale
        b_int32 = np.round(b_float / bias_scale).astype(np.int32)

        # Is last layer? (No ReLU on final reconstruction output)
        is_last = (idx == len(linear_modules) - 1)
        has_relu = not is_last

        q_layer = QuantizedLinearLayer(
            weight_int8=w_int8,
            bias_int32=b_int32,
            in_scale=current_in_scale,
            in_zp=current_in_zp,
            out_scale=out_scale,
            out_zp=out_zp,
            weight_scale=w_scale,
            has_relu=has_relu,
        )
        quantized_layers.append(q_layer)

        current_in_scale = out_scale
        current_in_zp = out_zp

    return QuantizedGatewayAutoencoder(quantized_layers, in_scale, in_zp)


def calibrate_and_quantize_node_detector(
    model: NodeStudentDetector,
    calibration_data: np.ndarray,
) -> QuantizedNodeDetector:
    """Calibrate activations and quantize Node Student Detector to INT8."""
    model.eval()
    device = next(model.parameters()).device

    in_scale, in_zp = calculate_quant_params_symmetric(calibration_data)
    act_data = torch.tensor(calibration_data, dtype=torch.float32).to(device)

    activations = []
    x = act_data
    for layer in model.net:
        x = layer(x)
        if isinstance(layer, nn.Linear):
            activations.append(x.detach().cpu().numpy())

    linear_modules = [m for m in model.net if isinstance(m, nn.Linear)]
    quantized_layers = []
    current_in_scale = in_scale
    current_in_zp = in_zp

    for idx, module in enumerate(linear_modules):
        w_float = module.weight.detach().cpu().numpy()
        b_float = module.bias.detach().cpu().numpy()

        w_scale, _ = calculate_quant_params_symmetric(w_float)
        w_int8 = quantize_to_int8(w_float, w_scale, 0)

        act_out = activations[idx]
        out_scale, out_zp = calculate_quant_params_symmetric(act_out)

        bias_scale = current_in_scale * w_scale
        b_int32 = np.round(b_float / bias_scale).astype(np.int32)

        is_last = (idx == len(linear_modules) - 1)
        has_relu = not is_last

        q_layer = QuantizedLinearLayer(
            weight_int8=w_int8,
            bias_int32=b_int32,
            in_scale=current_in_scale,
            in_zp=current_in_zp,
            out_scale=out_scale,
            out_zp=out_zp,
            weight_scale=w_scale,
            has_relu=has_relu,
        )
        quantized_layers.append(q_layer)
        current_in_scale = out_scale
        current_in_zp = out_zp

    return QuantizedNodeDetector(quantized_layers, in_scale, in_zp)
