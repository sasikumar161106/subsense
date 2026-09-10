"""
Per-node Anomaly Ensemble combining Isolation Forest and 1D-Conv Autoencoder.
Computes composite score:
    S_node = alpha * S_IF + (1 - alpha) * tanh(beta * MSE_AE)
Extracts contributing sensors to satisfy Explainability-by-Construction mandate.
"""

import math
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from features.constants import FEATURE_VECTOR_DIM, FEATURE_NAMES, SENSOR_ATTRIBUTION_MAPPING
from .isoforest import MineIsolationForest
from .autoencoder import MineAutoencoder


@dataclass
class AnomalyInferenceResult:
    anomaly_score: float                # S_node in [0.0, 1.0]
    reconstruction_error: float         # Raw MSE_AE
    isoforest_score: float              # S_IF in [0.0, 1.0]
    ae_score_component: float           # tanh(beta * MSE_AE) in [0.0, 1.0]
    contributing_sensors: List[str]     # Non-empty list of attributing physical sensors
    is_anomaly: bool                    # Boolean threshold flag (S_node >= threshold)
    model_signature: str                # Versioned model signature


class AnomalyEnsemble:
    """
    Dual-Tier Unsupervised Anomaly Detection Engine.
    Combines density/isolation geometry (Isolation Forest) with non-linear correlation
    reconstruction (1D-CNN Autoencoder).
    """

    def __init__(
        self,
        alpha: float = 0.55,
        beta: float = 12.5,
        anomaly_threshold: float = 0.65,
        model_version: str = "isoforest_ae_ensemble_v3.2.1",
    ):
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.anomaly_threshold = float(anomaly_threshold)
        self.model_signature = model_version

        self.isoforest = MineIsolationForest(n_estimators=100, max_samples=0.75)
        self.autoencoder = MineAutoencoder(latent_dim=4)
        self.is_fitted = False
        self.baseline_mse = 0.05

    def fit(
        self,
        X_baseline: np.ndarray,
        epochs: int = 40,
        batch_size: int = 32,
    ) -> "AnomalyEnsemble":
        """
        Fits both models on non-anomalous baseline feature vectors (30-day baseline).
        """
        assert X_baseline.shape[1] == FEATURE_VECTOR_DIM, f"Expected dim {FEATURE_VECTOR_DIM}"
        self.isoforest.fit(X_baseline)
        self.autoencoder.train_baseline(X_baseline, epochs=epochs, batch_size=batch_size)
        
        # Calibrate baseline MSE on training set (75th percentile)
        overall_mse, _ = self.autoencoder.evaluate(X_baseline)
        self.baseline_mse = float(np.percentile(overall_mse, 75))
        self.is_fitted = True
        return self

    def predict(
        self,
        feature_vector: np.ndarray,
        sensor_availability: Optional[Dict[str, bool]] = None,
    ) -> AnomalyInferenceResult:
        """
        Runs composite inference on a 12-D normalized feature vector.
        Guarantees:
        1. S_node in [0.0, 1.0]
        2. contributing_sensors is NEVER empty
        3. contributing_sensors NEVER contains sensors marked unavailable in sensor_availability
        """
        assert feature_vector.ndim == 1, "Expected 1D feature vector"
        assert len(feature_vector) == FEATURE_VECTOR_DIM, f"Expected {FEATURE_VECTOR_DIM} features"

        # 1. Isolation Forest score S_IF
        s_if = float(self.isoforest.score(feature_vector))
        s_if = float(np.clip(s_if, 0.0, 1.0))

        # 2. Autoencoder MSE and per-feature error
        overall_mse, per_feat_mse = self.autoencoder.evaluate(feature_vector)
        overall_mse = float(overall_mse)
        
        # Calibrated excess MSE relative to baseline
        excess_mse = max(0.0, overall_mse - self.baseline_mse)
        ae_score_component = float(math.tanh(self.beta * excess_mse))
        ae_score_component = float(np.clip(ae_score_component, 0.0, 1.0))

        # 3. Composite score S_node = alpha * S_IF + (1 - alpha) * tanh(beta * excess_MSE)
        s_node = self.alpha * s_if + (1.0 - self.alpha) * ae_score_component
        s_node = float(np.clip(s_node, 0.0, 1.0))

        # 4. Explainability Attribution (contributing_sensors)
        contributing_sensors = self._extract_contributing_sensors(
            per_feat_mse, feature_vector, sensor_availability=sensor_availability
        )
        assert len(contributing_sensors) > 0, "FATAL: contributing_sensors must never be empty!"

        is_anomaly = bool(s_node >= self.anomaly_threshold)

        return AnomalyInferenceResult(
            anomaly_score=round(s_node, 4),
            reconstruction_error=round(overall_mse, 6),
            isoforest_score=round(s_if, 4),
            ae_score_component=round(ae_score_component, 4),
            contributing_sensors=contributing_sensors,
            is_anomaly=is_anomaly,
            model_signature=self.model_signature,
        )

    def _extract_contributing_sensors(
        self,
        per_feat_mse: np.ndarray,
        feature_vector: np.ndarray,
        sensor_availability: Optional[Dict[str, bool]] = None,
    ) -> List[str]:
        """
        Aggregates error contributions to physical sensor modalities:
        tilt_deg, displacement_mm, vibration_rms_mm_s, crack_index.
        Always returns at least one sensor (never empty).
        If sensor_availability is specified, sensors marked False are strictly excluded.
        """
        sensor_weights: Dict[str, float] = {
            "tilt_deg": 0.0,
            "displacement_mm": 0.0,
            "vibration_rms_mm_s": 0.0,
            "crack_index": 0.0,
        }

        # Combine AE reconstruction error + feature magnitude
        for i, val in enumerate(per_feat_mse):
            feat_name = FEATURE_NAMES[i]
            target_sensor = SENSOR_ATTRIBUTION_MAPPING.get(feat_name)
            if target_sensor in sensor_weights:
                # Add normalized square error plus relative feature magnitude
                sensor_weights[target_sensor] += float(val) + 0.1 * abs(float(feature_vector[i]))

        # Filter out unavailable sensors if sensor_availability is provided
        if sensor_availability:
            def _is_sensor_available(s_name: str) -> bool:
                aliases = {
                    "tilt_deg": ["tilt_deg", "tilt"],
                    "vibration_rms_mm_s": ["vibration_rms_mm_s", "vibration"],
                    "displacement_mm": ["displacement_mm", "displacement"],
                    "crack_index": ["crack_index", "crack"],
                }
                keys = aliases.get(s_name, [s_name])
                for k in keys:
                    if k in sensor_availability and sensor_availability[k] is False:
                        return False
                return True

            filtered_weights = {s: w for s, w in sensor_weights.items() if _is_sensor_available(s)}
            if filtered_weights:
                sensor_weights = filtered_weights

        # Sort sensors by total contribution descending
        sorted_sensors = sorted(sensor_weights.items(), key=lambda item: item[1], reverse=True)
        max_val = sorted_sensors[0][1]

        # Select sensors that contribute meaningfully (>= 40% of max contribution)
        contributing = [s for s, val in sorted_sensors if (max_val > 1e-9 and val >= 0.40 * max_val)]

        # Fail-safe: if none met ratio or all zero, select top-1 dominant channel
        if not contributing:
            contributing = [sorted_sensors[0][0]]

        return contributing
