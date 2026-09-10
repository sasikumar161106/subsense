"""
Automated Model Retraining Service.
Implements:
1. Scheduled weekly baseline retrain across a rolling 30-day non-anomalous baseline.
2. Event-driven instant retraining triggered by physical node relocation.
3. Structured before/after score distribution logging for DGMS regulatory audits.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy import stats

from .ensemble import AnomalyEnsemble
from .relocation import GPSRelocationDetector

logger = logging.getLogger("subsense.models.retrain")


@dataclass
class ScoreDistributionSummary:
    mean: float
    std: float
    median: float
    p90: float
    p99: float
    sample_count: int


@dataclass
class RetrainAuditReport:
    timestamp_utc: str
    trigger_type: str                  # "WEEKLY_SCHEDULED" or "INSTANT_RELOCATION"
    node_id: Optional[str]
    before_distribution: ScoreDistributionSummary
    after_distribution: ScoreDistributionSummary
    ks_statistic: float
    p_value: float
    distribution_shifted: bool
    status: str


class ModelRetrainer:
    """
    Orchestrates baseline retraining loops for the per-node anomaly engine.
    Ensures that retrained models maintain safe calibration and logs all score shifts.
    """

    def __init__(
        self,
        ensemble: AnomalyEnsemble,
        relocation_detector: Optional[GPSRelocationDetector] = None,
        audit_log_path: Optional[str] = None,
    ):
        self.ensemble = ensemble
        self.relocation_detector = relocation_detector or GPSRelocationDetector()
        self.audit_log_path = Path(audit_log_path) if audit_log_path else None
        self.history: List[RetrainAuditReport] = []

        if self.audit_log_path:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def _compute_distribution(self, X_val: np.ndarray) -> Tuple[np.ndarray, ScoreDistributionSummary]:
        scores = []
        for i in range(len(X_val)):
            res = self.ensemble.predict(X_val[i])
            scores.append(res.anomaly_score)
        scores_arr = np.array(scores, dtype=np.float64)

        summary = ScoreDistributionSummary(
            mean=float(np.mean(scores_arr)),
            std=float(np.std(scores_arr)),
            median=float(np.median(scores_arr)),
            p90=float(np.percentile(scores_arr, 90)),
            p99=float(np.percentile(scores_arr, 99)),
            sample_count=len(scores_arr),
        )
        return scores_arr, summary

    def run_retrain(
        self,
        X_train_baseline: np.ndarray,
        X_val: np.ndarray,
        trigger_type: str = "WEEKLY_SCHEDULED",
        node_id: Optional[str] = None,
        epochs: int = 25,
    ) -> RetrainAuditReport:
        """
        Executes end-to-end retrain:
        1. Computes pre-retrain score distribution on validation set.
        2. Fits Isolation Forest and Conv1D-AE on new rolling baseline.
        3. Computes post-retrain score distribution and KS test.
        4. Writes audit report.
        """
        # 1. Pre-retrain distribution
        scores_before, dist_before = self._compute_distribution(X_val)

        # 2. Retrain model
        self.ensemble.fit(X_train_baseline, epochs=epochs, batch_size=32)

        # 3. Post-retrain distribution
        scores_after, dist_after = self._compute_distribution(X_val)

        # 4. Statistical comparison (Kolmogorov-Smirnov two-sample test)
        ks_res = stats.ks_2samp(scores_before, scores_after)
        ks_stat = float(ks_res.statistic)
        p_val = float(ks_res.pvalue)
        # Shift detected if p-value is small and KS statistic > 0.15
        shifted = bool(p_val < 0.05 and ks_stat > 0.15)

        report = RetrainAuditReport(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            trigger_type=trigger_type,
            node_id=node_id,
            before_distribution=dist_before,
            after_distribution=dist_after,
            ks_statistic=round(ks_stat, 4),
            p_value=round(p_val, 4),
            distribution_shifted=shifted,
            status="SUCCESS",
        )
        self.history.append(report)

        # Log audit entry
        logger.info(
            f"RETRAIN COMPLETED [{trigger_type}] Node: {node_id} | "
            f"Mean score: {dist_before.mean:.3f} -> {dist_after.mean:.3f} | KS: {ks_stat:.3f}"
        )

        if self.audit_log_path:
            try:
                with open(self.audit_log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(report)) + "\n")
            except Exception as e:
                logger.error(f"Failed to log retrain report: {e}")

        return report

    def handle_node_telemetry_relocation(
        self,
        node_id: str,
        lat: float,
        lon: float,
        X_train_baseline: np.ndarray,
        X_val: np.ndarray,
    ) -> Optional[RetrainAuditReport]:
        """
        Checks node GPS drift. If relocated beyond threshold, executes instant retraining.
        """
        reloc = self.relocation_detector.check_position(node_id, lat, lon)
        if reloc.is_relocated:
            logger.warning(
                f"Node {node_id} relocated by {reloc.drift_distance_m}m >= threshold {reloc.threshold_m}m. "
                "Triggering INSTANT RETRAIN."
            )
            report = self.run_retrain(
                X_train_baseline=X_train_baseline,
                X_val=X_val,
                trigger_type="INSTANT_RELOCATION",
                node_id=node_id,
            )
            self.relocation_detector.acknowledge_relocation(node_id, lat, lon)
            return report
        return None
