"""
Autoencoder Knowledge Distillation & int8 Quantization Engine.
Distills the cloud Conv1D-Autoencoder into a 3-layer MLP and evaluates
edge/cloud parity target (>= 94% decision agreement).
Generates C header definitions for zero-dependency ESP32-S3 TinyML deployment.
"""

import math
import sys
from pathlib import Path
from typing import Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from features.constants import FEATURE_VECTOR_DIM
from models.anomaly.autoencoder import MineAutoencoder
from models.anomaly.ensemble import AnomalyEnsemble


class EdgeMLPModel(nn.Module):
    """
    3-layer bottleneck MLP designed for sub-38KB SRAM and ~4.8ms ESP32-S3 execution.
    12 -> 16 -> 8 -> 12
    """

    def __init__(self, in_dim: int = FEATURE_VECTOR_DIM, h1: int = 16, h2: int = 8):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, h1)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Linear(h1, h2)
        self.relu2 = nn.ReLU()
        self.fc3 = nn.Linear(h2, in_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.relu1(self.fc1(x))
        out = self.relu2(self.fc2(out))
        out = self.fc3(out)
        return out


class TinyMLDistiller:
    """
    Handles distillation training, int8 quantization, and C header generation.
    """

    def __init__(self, cloud_ensemble: AnomalyEnsemble):
        self.cloud_ensemble = cloud_ensemble
        self.edge_model = EdgeMLPModel()
        self.quantized_weights: Dict[str, np.ndarray] = {}
        self.quantized_biases: Dict[str, np.ndarray] = {}
        self.scales: Dict[str, float] = {}

    def distill(
        self,
        X_train: np.ndarray,
        epochs: int = 50,
        lr: float = 0.005,
        batch_size: int = 32,
    ) -> float:
        """
        Trains Edge MLP to mimic the cloud autoencoder's reconstructions and outputs.
        """
        self.edge_model.train()
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.edge_model.parameters(), lr=lr)

        # Get teacher reconstructions
        self.cloud_ensemble.autoencoder.model.eval()
        with torch.no_grad():
            x_tensor = torch.from_numpy(X_train.astype(np.float32))
            teacher_targets = self.cloud_ensemble.autoencoder.model(x_tensor)

        dataset = torch.utils.data.TensorDataset(x_tensor, teacher_targets)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

        final_loss = 0.0
        for epoch in range(epochs):
            total_loss = 0.0
            for batch_x, batch_y in loader:
                optimizer.zero_grad()
                pred = self.edge_model(batch_x)
                loss = criterion(pred, batch_y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * batch_x.size(0)
            final_loss = total_loss / len(dataset)

        self.edge_model.eval()
        self._quantize_to_int8()

        # Calibrate edge baseline MSE on training set
        with torch.no_grad():
            train_tensor = torch.from_numpy(X_train.astype(np.float32))
            train_preds = self.edge_model(train_tensor).numpy()
            train_mse = np.mean((X_train - train_preds) ** 2, axis=1)
            self.baseline_edge_mse = float(np.percentile(train_mse, 75))

        # Calibrate edge threshold against cloud teacher decisions on balanced calibration split
        calib_normal = X_train[:160]
        # Create synthetic anomalous samples to calibrate decision boundary
        calib_anom = X_train[:40] + np.random.normal(loc=2.0, scale=0.5, size=(40, FEATURE_VECTOR_DIM)).astype(np.float32)
        calib_X = np.vstack([calib_normal, calib_anom])
        raw_scores, _ = self.predict_edge_simulated(calib_X)
        teacher_decisions = np.array([self.cloud_ensemble.predict(calib_X[i]).is_anomaly for i in range(len(calib_X))])
        
        best_th = 0.55
        best_acc = 0.0
        for th in np.linspace(0.35, 0.75, 41):
            acc = float(np.mean((raw_scores >= th) == teacher_decisions))
            if acc >= best_acc:
                best_acc = acc
                best_th = float(th)
        self.edge_threshold = best_th

        return float(final_loss)

    def _quantize_to_int8(self) -> None:
        """Quantizes float32 linear weights to signed int8 [-127, 127]."""
        state_dict = self.edge_model.state_dict()
        for name, param in state_dict.items():
            arr = param.cpu().numpy()
            if "weight" in name:
                max_abs = float(np.max(np.abs(arr))) + 1e-8
                scale = max_abs / 127.0
                q_arr = np.round(arr / scale).astype(np.int8)
                self.quantized_weights[name] = q_arr
                self.scales[name] = scale
            elif "bias" in name:
                self.quantized_biases[name] = arr.astype(np.float32)

    def predict_edge_simulated(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Simulates the int8 inference executing on ESP32-S3.
        Returns:
            scores: anomaly score in [0.0, 1.0]
            decisions: bool array of anomaly flags
        """
        is_1d = (X.ndim == 1)
        X_in = X.reshape(1, -1) if is_1d else X

        # Reconstructed output using quantized weights
        W1 = self.quantized_weights["fc1.weight"] * self.scales["fc1.weight"]
        b1 = self.quantized_biases["fc1.bias"]
        W2 = self.quantized_weights["fc2.weight"] * self.scales["fc2.weight"]
        b2 = self.quantized_biases["fc2.bias"]
        W3 = self.quantized_weights["fc3.weight"] * self.scales["fc3.weight"]
        b3 = self.quantized_biases["fc3.bias"]

        # Forward pass
        h1 = np.maximum(0.0, X_in @ W1.T + b1)
        h2 = np.maximum(0.0, h1 @ W2.T + b2)
        out = h2 @ W3.T + b3

        mse = np.mean((X_in - out) ** 2, axis=1)
        base_mse = getattr(self, "baseline_edge_mse", 0.05)
        excess_mse = np.maximum(0.0, mse - base_mse)
        scores = np.tanh(12.5 * excess_mse)
        
        threshold = getattr(self, "edge_threshold", 0.60)
        decisions = scores >= threshold

        if is_1d:
            return scores[0], decisions[0]
        return scores, decisions

    def evaluate_parity(self, X_val: np.ndarray) -> Dict[str, float]:
        """
        Evaluates Section 8 Edge vs. Cloud Parity (>94.0% agreement rate).
        """
        cloud_decisions = []
        for i in range(len(X_val)):
            res = self.cloud_ensemble.predict(X_val[i])
            cloud_decisions.append(res.is_anomaly)
        cloud_decisions = np.array(cloud_decisions, dtype=bool)

        _, edge_decisions = self.predict_edge_simulated(X_val)

        agreements = (cloud_decisions == edge_decisions)
        agreement_rate = float(np.mean(agreements)) * 100.0

        return {
            "agreement_rate_pct": round(agreement_rate, 2),
            "target_threshold_pct": 94.0,
            "meets_target": bool(agreement_rate >= 94.0),
            "sample_count": len(X_val),
        }

    def export_c_header(self, output_path: str) -> None:
        """Generates C/C++ header with int8 weight matrices and scale constants."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        W1 = self.quantized_weights["fc1.weight"]  # shape (16, 12)
        b1 = self.quantized_biases["fc1.bias"]     # shape (16,)
        W2 = self.quantized_weights["fc2.weight"]  # shape (8, 16)
        b2 = self.quantized_biases["fc2.bias"]     # shape (8,)
        W3 = self.quantized_weights["fc3.weight"]  # shape (12, 8)
        b3 = self.quantized_biases["fc3.bias"]     # shape (12,)

        lines = [
            "// Auto-generated TinyML int8 model parameters for ESP32-S3",
            "// SubSense Layer 4 - Zero-Connectivity Defense Layer",
            "#pragma once",
            "#include <stdint.h>",
            "",
            "#define TINYML_INPUT_DIM  12",
            "#define TINYML_HIDDEN1_DIM 16",
            "#define TINYML_HIDDEN2_DIM 8",
            "#define TINYML_OUTPUT_DIM 12",
            "",
            f"static const float SCALE_W1 = {self.scales['fc1.weight']:.8f}f;",
            f"static const float SCALE_W2 = {self.scales['fc2.weight']:.8f}f;",
            f"static const float SCALE_W3 = {self.scales['fc3.weight']:.8f}f;",
            "",
            "// Weight matrices (int8)",
            f"static const int8_t W1[16][12] = {{"
        ]
        for row in W1:
            lines.append("    {" + ", ".join(str(int(v)) for v in row) + "},")
        lines.append("};")

        lines.append(f"\nstatic const int8_t W2[8][16] = {{")
        for row in W2:
            lines.append("    {" + ", ".join(str(int(v)) for v in row) + "},")
        lines.append("};")

        lines.append(f"\nstatic const int8_t W3[12][8] = {{")
        for row in W3:
            lines.append("    {" + ", ".join(str(int(v)) for v in row) + "},")
        lines.append("};")

        # Biases
        lines.append("\n// Biases (float)")
        lines.append("static const float B1[16] = {" + ", ".join(f"{float(v):.6f}f" for v in b1) + "};")
        lines.append("static const float B2[8] = {" + ", ".join(f"{float(v):.6f}f" for v in b2) + "};")
        lines.append("static const float B3[12] = {" + ", ".join(f"{float(v):.6f}f" for v in b3) + "};")

        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
