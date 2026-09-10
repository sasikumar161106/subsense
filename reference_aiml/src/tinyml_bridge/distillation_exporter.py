from typing import Dict, Any, List
import numpy as np
import torch
import torch.nn as nn
from src.models.autoencoder_detector import PyTorchAutoencoderDetector

class TinyMLDistillationExporter:
    """
    Teacher-to-Student Distillation & Model Quantization Bridge (Section 9).
    Distills cloud-trained neural models into micro-quantized representations
    for ARM Cortex-M4/ESP32 edge nodes and Raspberry Pi gateways.
    """

    def __init__(self, teacher_ae: PyTorchAutoencoderDetector):
        self.teacher_ae = teacher_ae

    def export_quantized_edge_model(
        self,
        target_device: str = "ARM_Cortex_M4",
        bits: int = 8,
    ) -> Dict[str, Any]:
        """
        Extracts weights from PyTorch teacher Autoencoder, performs INT8 symmetric
        quantization, and returns deployment artifact bundle.
        """
        weights_bundle: Dict[str, Any] = {}
        total_param_bytes = 0

        for name, param in self.teacher_ae.model.named_parameters():
            if "weight" in name:
                w_float = param.detach().cpu().numpy()
                max_val = np.max(np.abs(w_float)) + 1e-8
                scale = max_val / (2 ** (bits - 1) - 1)
                w_int8 = np.round(w_float / scale).astype(np.int8)

                weights_bundle[name] = {
                    "shape": list(w_float.shape),
                    "scale": float(scale),
                    "zero_point": 0,
                    "quantized_weights": w_int8.tolist(),
                }
                total_param_bytes += w_int8.nbytes

            elif "bias" in name:
                b_float = param.detach().cpu().numpy()
                weights_bundle[name] = {
                    "shape": list(b_float.shape),
                    "values": b_float.tolist(),
                }
                total_param_bytes += b_float.nbytes

        manifest = {
            "teacher_version": self.teacher_ae.version,
            "target_architecture": target_device,
            "quantization": f"INT{bits}_symmetric",
            "input_dimension": self.teacher_ae.input_dim,
            "latent_dimension": self.teacher_ae.latent_dim,
            "model_footprint_bytes": total_param_bytes,
            "is_edge_deployable": total_param_bytes < 32768,  # Under 32KB RAM limit for TinyML
            "weights": weights_bundle,
        }
        return manifest
