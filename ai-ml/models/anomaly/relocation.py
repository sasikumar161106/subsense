"""
Physical relocation detection based on GPS drift tracking.
Triggers immediate model retraining when a node is physically relocated.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from features.geometry_loader import haversine_distance_m


@dataclass
class RelocationStatus:
    is_relocated: bool
    drift_distance_m: float
    threshold_m: float
    baseline_coord: Tuple[float, float]
    current_coord: Tuple[float, float]
    node_id: str


class GPSRelocationDetector:
    """
    Monitors spatial centroid coordinates of each wireless mesh node.
    Flags physical relocation if distance from baseline exceeds threshold_m.
    """

    def __init__(self, threshold_m: float = 15.0):
        self.threshold_m = threshold_m
        self.baseline_coords: Dict[str, Tuple[float, float]] = {}
        self.current_coords: Dict[str, Tuple[float, float]] = {}

    def set_baseline(self, node_id: str, lat: float, lon: float) -> None:
        self.baseline_coords[node_id] = (lat, lon)
        self.current_coords[node_id] = (lat, lon)

    def check_position(self, node_id: str, lat: float, lon: float) -> RelocationStatus:
        """
        Evaluates current coordinates against baseline coordinates.
        Returns RelocationStatus detailing drift.
        """
        self.current_coords[node_id] = (lat, lon)

        if node_id not in self.baseline_coords:
            # Initialize baseline upon first observation
            self.baseline_coords[node_id] = (lat, lon)
            return RelocationStatus(
                is_relocated=False,
                drift_distance_m=0.0,
                threshold_m=self.threshold_m,
                baseline_coord=(lat, lon),
                current_coord=(lat, lon),
                node_id=node_id,
            )

        base_lat, base_lon = self.baseline_coords[node_id]
        drift_m = haversine_distance_m(base_lat, base_lon, lat, lon)
        is_relocated = bool(drift_m >= self.threshold_m)

        return RelocationStatus(
            is_relocated=is_relocated,
            drift_distance_m=round(drift_m, 2),
            threshold_m=self.threshold_m,
            baseline_coord=(base_lat, base_lon),
            current_coord=(lat, lon),
            node_id=node_id,
        )

    def acknowledge_relocation(self, node_id: str, new_lat: float, new_lon: float) -> None:
        """Resets the baseline coordinates to the new relocated position."""
        self.baseline_coords[node_id] = (new_lat, new_lon)
        self.current_coords[node_id] = (new_lat, new_lon)
