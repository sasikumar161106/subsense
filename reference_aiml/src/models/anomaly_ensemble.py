from typing import Dict, List, Tuple, Optional
import numpy as np
from src.schemas.sensor_contracts import EngineeredFeatureVector
from .isolation_forest_detector import IsolationForestAnomalyDetector
from .autoencoder_detector import PyTorchAutoencoderDetector

class AnomalyDetectionEnsemble:
    """
    Unsupervised Anomaly Detection Ensemble (Section 4).
    Combines Isolation Forest and Deep Autoencoder into a unified, calibrated
    per-node anomaly_score in [0.0, 1.0].
    Also tracks agreement between models to feed the confidence scoring engine (Section 7).
    """

    def __init__(
        self,
        weight_if: float = 0.45,
        weight_ae: float = 0.55,
        anomaly_threshold: float = 0.60,
        version: str = "cloud-ensemble-v2.1.0",
    ):
        self.weight_if = weight_if
        self.weight_ae = weight_ae
        self.anomaly_threshold = anomaly_threshold
        self.version = version

        self.if_model = IsolationForestAnomalyDetector(version=f"{version}-if")
        self.ae_model = PyTorchAutoencoderDetector(version=f"{version}-ae")

    def fit(self, X_baseline: np.ndarray) -> "AnomalyDetectionEnsemble":
        """Fits both constituent models on baseline / normal historical feature arrays."""
        self.if_model.fit(X_baseline)
        self.ae_model.fit(X_baseline)
        return self

    def score_vector(self, features: EngineeredFeatureVector) -> Tuple[float, float, float, float]:
        """
        Scores a single node feature vector.
        Returns: (ensemble_score, if_score, ae_score, agreement)
        """
        arr = np.array(features.to_feature_list(), dtype=np.float32).reshape(1, -1)
        score_if = float(self.if_model.predict_anomaly_score(arr)[0])
        score_ae = float(self.ae_model.predict_anomaly_score(arr)[0])

        ensemble_score = float(np.clip(
            self.weight_if * score_if + self.weight_ae * score_ae,
            0.0, 1.0
        ))

        # Model agreement: 1.0 - absolute difference between model scores
        agreement = float(1.0 - np.abs(score_if - score_ae))

        return ensemble_score, score_if, score_ae, agreement

    def score_batch(
        self,
        feature_map: Dict[str, EngineeredFeatureVector],
    ) -> Dict[str, Dict[str, float]]:
        """
        Scores all validated nodes across the mesh.
        Returns: {node_id: {"anomaly_score": ..., "if_score": ..., "ae_score": ..., "agreement": ...}}
        """
        results: Dict[str, Dict[str, float]] = {}
        for nid, fvec in feature_map.items():
            ens, sif, sae, agr = self.score_vector(fvec)
            results[nid] = {
                "anomaly_score": ens,
                "if_score": sif,
                "ae_score": sae,
                "agreement": agr,
            }
        return results

    def adjust_sensitivity(self, delta_threshold: float) -> None:
        """Dynamic nudge from feedback loop (Section 8.2)."""
        self.anomaly_threshold = float(np.clip(self.anomaly_threshold + delta_threshold, 0.20, 0.90))
