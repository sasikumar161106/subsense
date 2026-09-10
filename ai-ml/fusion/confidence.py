"""
Composite Confidence Scoring Engine.
Computes:
    Confidence = w1 * Agreement(IsoForest, LSTM, GNN) + w2 * C_corr + w3 * Q_mesh
Directly wires to Phase 1 QoS telemetry metrics and Phase 2 deep intelligence models.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import numpy as np


@dataclass
class ConfidenceComponents:
    confidence: float
    model_agreement: float
    c_corr: float
    q_mesh: float
    w1: float
    w2: float
    w3: float
    isoforest_risk: float
    lstm_risk: float
    gnn_risk: float


class ConfidenceScorer:
    """
    Evaluates multi-model consensus and empirical evidence quality.
    Ensures that single-point-of-failure anomalies (e.g. noisy sensor, lone spike)
    receive low confidence (< 0.60), whereas multi-source corroborated events
    reach high confidence (>= 0.75 - 0.95).
    """

    def __init__(
        self,
        w1_agreement: float = 0.50,
        w2_correlation: float = 0.30,
        w3_qos: float = 0.20,
    ):
        total_w = w1_agreement + w2_correlation + w3_qos
        assert total_w > 0, "Weights must sum to positive value"
        self.w1 = float(w1_agreement / total_w)
        self.w2 = float(w2_correlation / total_w)
        self.w3 = float(w3_qos / total_w)

    def compute_agreement(
        self,
        isoforest_score: float,
        lstm_regime: str,
        r_gnn: float,
        lstm_velocity_mm_h: float = 0.0,
        lstm_accel_mm_h2: float = 0.0,
    ) -> Tuple[float, float, float, float]:
        """
        Computes continuous and binary consensus between IsoForest, LSTM, and GNN.
        Returns (agreement, r_if, r_lstm, r_gnn) all in [0.0, 1.0].
        """
        # 1. Normalize IsoForest risk
        r_if = float(np.clip(isoforest_score, 0.0, 1.0))

        # 2. Normalize LSTM kinematic risk
        regime_upper = str(lstm_regime).strip().upper()
        if regime_upper == "ACCELERATING":
            base_lstm = 0.90
        elif regime_upper == "SUSTAINED":
            base_lstm = 0.70
        else:  # STABLE or unknown
            base_lstm = 0.15

        # Refine with numerical velocity/acceleration if provided
        dyn_boost = min(0.10, max(0.0, lstm_velocity_mm_h * 0.05 + lstm_accel_mm_h2 * 0.5))
        r_lstm = float(np.clip(base_lstm + dyn_boost, 0.0, 1.0))

        # 3. Normalize GNN spatial fracture risk
        r_gnn = float(np.clip(r_gnn, 0.0, 1.0))

        # 4. Measure consensus
        risks = np.array([r_if, r_lstm, r_gnn], dtype=float)
        
        # Standard deviation normalized by maximum possible standard deviation of 3 numbers in [0, 1] (sqrt(1/3) ≈ 0.577)
        std_dev = float(np.std(risks))
        continuous_consensus = float(np.clip(1.0 - (std_dev / 0.57735), 0.0, 1.0))

        # Binary concordance: do >=2 models agree on elevation (> 0.5)?
        elevated_count = int(np.sum(risks >= 0.50))
        if elevated_count == 3 or elevated_count == 0:
            binary_concordance = 1.0
        elif elevated_count == 2:
            binary_concordance = 0.75
        else:
            binary_concordance = 0.35

        agreement = float(np.clip(0.60 * continuous_consensus + 0.40 * binary_concordance, 0.0, 1.0))
        return agreement, r_if, r_lstm, r_gnn

    def score(
        self,
        isoforest_score: float,
        lstm_regime: str,
        r_gnn: float,
        c_corr: float,
        q_mesh: float,
        lstm_velocity_mm_h: float = 0.0,
        lstm_accel_mm_h2: float = 0.0,
    ) -> ConfidenceComponents:
        """
        Computes total calibrated confidence:
            Confidence = w1 * Agreement + w2 * C_corr + w3 * Q_mesh
        """
        c_corr_norm = float(np.clip(c_corr, 0.0, 1.0))
        q_mesh_norm = float(np.clip(q_mesh, 0.0, 1.0))

        agreement, r_if, r_lstm, r_gnn = self.compute_agreement(
            isoforest_score=isoforest_score,
            lstm_regime=lstm_regime,
            r_gnn=r_gnn,
            lstm_velocity_mm_h=lstm_velocity_mm_h,
            lstm_accel_mm_h2=lstm_accel_mm_h2,
        )

        composite_conf = self.w1 * agreement + self.w2 * c_corr_norm + self.w3 * q_mesh_norm
        calibrated_conf = float(np.clip(composite_conf, 0.0, 1.0))

        return ConfidenceComponents(
            confidence=calibrated_conf,
            model_agreement=agreement,
            c_corr=c_corr_norm,
            q_mesh=q_mesh_norm,
            w1=self.w1,
            w2=self.w2,
            w3=self.w3,
            isoforest_risk=r_if,
            lstm_risk=r_lstm,
            gnn_risk=r_gnn,
        )

    def update_weights(self, w1: float, w2: float, w3: float) -> None:
        """Dynamically reconfigures weighting vector."""
        total = w1 + w2 + w3
        assert total > 0, "Weights must sum to positive value"
        self.w1 = float(w1 / total)
        self.w2 = float(w2 / total)
        self.w3 = float(w3 / total)
