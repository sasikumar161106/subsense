"""
Negative Mining Sample Repository.
Automatically aggregates confirmed false alarm incidents for model retraining.
Prevents recurrence of blasts, haulage vibration, or sensor drift false alarms.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid
import numpy as np


@dataclass
class NegativeSampleRecord:
    sample_id: str
    alert_id: str
    node_id: str
    timestamp: datetime
    label: str
    feature_vector: np.ndarray
    sensor_deltas: Dict[str, float]
    operator_notes: Optional[str] = None


class NegativeSampleMiningRepository:
    """
    In-memory and persisted storage for hard negative samples mined from operational feedback.
    """

    def __init__(self):
        self.samples: List[NegativeSampleRecord] = []

    def add_sample(
        self,
        alert_id: str,
        node_id: str,
        timestamp: datetime,
        label: str,
        feature_vector: List[float],
        sensor_deltas: Dict[str, float],
        operator_notes: Optional[str] = None,
    ) -> NegativeSampleRecord:
        """Appends verified false-alarm sample to repository."""
        vec = np.array(feature_vector, dtype=np.float32)
        sample_id = f"MINED-{uuid.uuid4().hex[:8].upper()}"
        record = NegativeSampleRecord(
            sample_id=sample_id,
            alert_id=alert_id,
            node_id=node_id,
            timestamp=timestamp,
            label=label,
            feature_vector=vec,
            sensor_deltas=sensor_deltas,
            operator_notes=operator_notes,
        )
        self.samples.append(record)
        return record

    def get_negative_feature_matrix(self) -> np.ndarray:
        """Returns stacked 2D numpy matrix (N, 12) of mined negative feature vectors."""
        if not self.samples:
            return np.empty((0, 12), dtype=np.float32)
        return np.vstack([s.feature_vector for s in self.samples])

    def get_counts_by_label(self) -> Dict[str, int]:
        """Returns distribution of mined false alarm classes."""
        counts: Dict[str, int] = {}
        for s in self.samples:
            counts[s.label] = counts.get(s.label, 0) + 1
        return counts

    def get_sample_count(self) -> int:
        return len(self.samples)

    def clear(self) -> None:
        self.samples.clear()
