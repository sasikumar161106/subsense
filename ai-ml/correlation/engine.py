"""
Cross-sensor and cross-node rule-based correlation engine.
Deterministic, auditable gatekeeper enforcing DGMS multi-channel consistency:
1. Within-node: concordant drift across >=2 modalities required before escalation.
2. Across-node: neighbors within R <= 120m within tau <= 45 min, else down-weighted by 0.25.
Outputs: C_corr in [0.0, 1.0], Sensor Fault vs True Ground Movement flag.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from features.geometry_loader import haversine_distance_m


@dataclass
class AnomalyEventRecord:
    node_id: str
    timestamp: datetime
    lat: float
    lon: float
    anomaly_score: float
    is_anomaly: bool


@dataclass
class SensorDeltas:
    delta_tilt_deg: float
    delta_displacement_mm: float
    delta_vibration_rms_mm_s: float
    delta_crack_index: float


@dataclass
class CorrelationResult:
    node_id: str
    raw_anomaly_score: float
    corroborated_score: float
    corroboration_coefficient: float    # C_corr in [0.0, 1.0]
    is_multi_channel_concordant: bool
    concordant_channel_count: int
    active_neighbor_count: int
    is_isolated_node: bool
    sensor_fault_flag: bool
    true_movement_flag: bool
    routing_destination: str            # "ALERT_ESCALATION_PATH" or "PREDICTIVE_MAINTENANCE_QUEUE"
    plain_language_summary: str


class CrossCorrelationEngine:
    """
    Rule-based safety gatekeeper. Auditable by mine inspectorates.
    Prevents false trips from rock drills, haul trucks, or single-sensor electrical fatigue.
    """

    def __init__(
        self,
        delta_tilt_min_deg: float = 0.15,
        delta_displacement_min_mm: float = 1.5,
        delta_vib_min_mm_s: float = 10.0,
        delta_crack_min: float = 0.05,
        neighbor_radius_m: float = 120.0,
        temporal_window_min: float = 45.0,
        isolated_penalty_factor: float = 0.25,
    ):
        self.delta_tilt_min_deg = delta_tilt_min_deg
        self.delta_displacement_min_mm = delta_displacement_min_mm
        self.delta_vib_min_mm_s = delta_vib_min_mm_s
        self.delta_crack_min = delta_crack_min
        self.neighbor_radius_m = neighbor_radius_m
        self.temporal_window_sec = temporal_window_min * 60.0
        self.isolated_penalty = isolated_penalty_factor

        # Recent anomaly event history across mesh nodes
        self.event_history: List[AnomalyEventRecord] = []

    def register_event(
        self,
        node_id: str,
        timestamp: datetime,
        lat: float,
        lon: float,
        anomaly_score: float,
        is_anomaly: bool,
    ) -> None:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        self.event_history.append(
            AnomalyEventRecord(node_id, timestamp, lat, lon, anomaly_score, is_anomaly)
        )
        # Prune records older than 2x temporal window
        cutoff = timestamp.timestamp() - (2.0 * self.temporal_window_sec)
        self.event_history = [
            e for e in self.event_history if e.timestamp.timestamp() >= cutoff
        ]

    def evaluate(
        self,
        node_id: str,
        timestamp: datetime,
        lat: float,
        lon: float,
        raw_anomaly_score: float,
        deltas: SensorDeltas,
    ) -> CorrelationResult:
        """
        Executes within-node and across-node corroboration rules.
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # 1. Within-node multi-channel concordance check
        concordant_channels = 0
        if abs(deltas.delta_tilt_deg) >= self.delta_tilt_min_deg:
            concordant_channels += 1
        if abs(deltas.delta_displacement_mm) >= self.delta_displacement_min_mm:
            concordant_channels += 1
        if abs(deltas.delta_vibration_rms_mm_s) >= self.delta_vib_min_mm_s:
            concordant_channels += 1
        if abs(deltas.delta_crack_index) >= self.delta_crack_min:
            concordant_channels += 1

        is_concordant = bool(concordant_channels >= 2)

        # 2. Across-node spatio-temporal coincidence check
        curr_t = timestamp.timestamp()
        corroborating_neighbors = []

        for evt in self.event_history:
            if evt.node_id == node_id:
                continue
            # Check spatial radius R <= 120m
            dist = haversine_distance_m(lat, lon, evt.lat, evt.lon)
            if dist <= self.neighbor_radius_m:
                # Check temporal window tau <= 45 min
                dt = abs(curr_t - evt.timestamp.timestamp())
                if dt <= self.temporal_window_sec and evt.is_anomaly:
                    corroborating_neighbors.append((evt.node_id, dist, dt))

        neighbor_count = len(corroborating_neighbors)
        is_isolated = bool(neighbor_count == 0)

        # 3. Decision Logic & Corroboration Coefficient C_corr
        if not is_concordant:
            # Single-channel spike: Sensor Malfunction / Hardware Fatigue
            # Divert to Predictive Maintenance Diagnostic Queue, NOT alert path
            sensor_fault = True
            true_movement = False
            c_corr = float(min(0.25, 0.10 * concordant_channels))
            corroborated_score = float(raw_anomaly_score * self.isolated_penalty)
            destination = "PREDICTIVE_MAINTENANCE_QUEUE"
            summary = (
                f"Isolated single-channel spike at {node_id} (concordant modalities: {concordant_channels}/2). "
                "Attributed to sensor hardware fatigue. Routed to Predictive Maintenance Queue."
            )
        else:
            # Multi-channel concordance confirmed
            sensor_fault = False
            true_movement = True
            if is_isolated:
                # Concordant within node, but no neighbors within 120m / 45min
                # Down-weight by isolated penalty factor (0.25)
                corroborated_score = float(raw_anomaly_score * self.isolated_penalty)
                c_corr = float(0.25 + 0.15 * min(concordant_channels - 2, 2))
                destination = "PREDICTIVE_MAINTENANCE_QUEUE" if corroborated_score < 0.65 else "ALERT_ESCALATION_PATH"
                summary = (
                    f"Multi-channel drift at {node_id} (concordant modalities: {concordant_channels}), "
                    f"but uncorroborated by neighbors within {self.neighbor_radius_m}m. "
                    f"Score down-weighted by {self.isolated_penalty}x to {corroborated_score:.2f}."
                )
            else:
                # Fully corroborated across space and time!
                corroborated_score = float(raw_anomaly_score)
                # C_corr scales with number of neighbors and channels
                neighbor_factor = min(1.0, neighbor_count / 3.0)
                channel_factor = min(1.0, concordant_channels / 4.0)
                c_corr = float(min(1.0, 0.40 * channel_factor + 0.60 * neighbor_factor))
                destination = "ALERT_ESCALATION_PATH"
                neighbor_names = ", ".join([n[0] for n in corroborating_neighbors[:3]])
                summary = (
                    f"CONFIRMED GROUND MOVEMENT at {node_id}: {concordant_channels} concordant modalities. "
                    f"Corroborated by {neighbor_count} neighbor(s) [{neighbor_names}] within {self.neighbor_radius_m}m."
                )

        # Register this node's event into history
        self.register_event(
            node_id=node_id,
            timestamp=timestamp,
            lat=lat,
            lon=lon,
            anomaly_score=corroborated_score,
            is_anomaly=bool(corroborated_score >= 0.65 and true_movement),
        )

        return CorrelationResult(
            node_id=node_id,
            raw_anomaly_score=round(raw_anomaly_score, 4),
            corroborated_score=round(corroborated_score, 4),
            corroboration_coefficient=round(c_corr, 4),
            is_multi_channel_concordant=is_concordant,
            concordant_channel_count=concordant_channels,
            active_neighbor_count=neighbor_count,
            is_isolated_node=is_isolated,
            sensor_fault_flag=sensor_fault,
            true_movement_flag=true_movement,
            routing_destination=destination,
            plain_language_summary=summary,
        )
