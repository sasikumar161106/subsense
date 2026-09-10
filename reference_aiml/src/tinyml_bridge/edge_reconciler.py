from typing import Dict, List, Tuple
from datetime import datetime
from collections import deque
import numpy as np

class EdgeCloudReconciler:
    """
    Edge-Cloud Detection Reconciliation & Drift Monitoring Engine (Section 9 & 10).
    Reconciles buffered edge alerts backfilled after connectivity recovery against
    the cloud inference layer. Alerts when persistent disagreement signals model drift.
    """

    def __init__(self, drift_threshold_disagreements: int = 5):
        self.drift_threshold = drift_threshold_disagreements
        # {node_id: deque of recent comparisons (edge_flag, cloud_flag)}
        self._history: Dict[str, deque[Tuple[bool, bool, datetime]]] = {}

    def record_comparison(
        self,
        node_id: str,
        edge_detected_anomaly: bool,
        cloud_detected_anomaly: bool,
        timestamp: datetime,
    ) -> Dict[str, any]:
        if node_id not in self._history:
            self._history[node_id] = deque(maxlen=50)

        self._history[node_id].append((edge_detected_anomaly, cloud_detected_anomaly, timestamp))

        # Check for disagreement
        is_agreement = (edge_detected_anomaly == cloud_detected_anomaly)

        # Count consecutive disagreements
        consecutive_disagreements = 0
        for e_flag, c_flag, _ in reversed(self._history[node_id]):
            if e_flag != c_flag:
                consecutive_disagreements += 1
            else:
                break

        drift_detected = consecutive_disagreements >= self.drift_threshold

        return {
            "node_id": node_id,
            "is_agreement": is_agreement,
            "consecutive_disagreements": consecutive_disagreements,
            "drift_detected": drift_detected,
            "recommended_action": "Redistill and re-flash edge firmware model" if drift_detected else "Nominal",
        }

    def get_node_agreement_rate(self, node_id: str) -> float:
        hist = self._history.get(node_id)
        if not hist:
            return 1.0
        agreements = sum(1 for e, c, _ in hist if e == c)
        return float(agreements / len(hist))
