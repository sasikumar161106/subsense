from typing import Dict
import numpy as np

class OnlineCalibrator:
    """
    Short-term Fast Adaptation Engine (Section 8.2).
    Dynamically nudges per-site anomaly and correlation sensitivity thresholds
    in response to operator feedback (e.g. false alarms caused by temporary blasting operations).
    """

    def __init__(self, base_anomaly_threshold: float = 0.60, max_nudge: float = 0.15):
        self.base_anomaly_threshold = base_anomaly_threshold
        self.max_nudge = max_nudge
        # Per-site threshold offsets
        self._site_nudges: Dict[str, float] = {}

    def get_effective_threshold(self, site_id: str) -> float:
        nudge = self._site_nudges.get(site_id, 0.0)
        return float(np.clip(self.base_anomaly_threshold + nudge, 0.30, 0.90))

    def record_feedback(self, site_id: str, feedback_type: str) -> float:
        current_nudge = self._site_nudges.get(site_id, 0.0)
        if feedback_type == "false_positive":
            # Operator marked alert as false alarm: raise threshold slightly (less sensitive)
            new_nudge = min(self.max_nudge, current_nudge + 0.03)
        elif feedback_type == "confirmed_positive":
            # Confirmed true subsidence: restore or lower threshold slightly (maintain high sensitivity)
            new_nudge = max(-self.max_nudge, current_nudge - 0.01)
        else:
            new_nudge = current_nudge

        self._site_nudges[site_id] = new_nudge
        return self.get_effective_threshold(site_id)

    def reset_site(self, site_id: str) -> None:
        if site_id in self._site_nudges:
            del self._site_nudges[site_id]
