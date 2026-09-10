"""
Per-node Quality of Service (QoS) and Telemetry Reliability Tracker.
Computes Packet Delivery Ratio (PDR) and Q_mesh completeness term.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import numpy as np

from .schema import RawSensorRecord


@dataclass
class NodeQoSMetrics:
    node_id: str
    total_received: int = 0
    total_expected: int = 0
    packet_delivery_ratio: float = 1.0
    first_seen_utc: Optional[datetime] = None
    last_seen_utc: Optional[datetime] = None
    last_battery_pct: float = 100.0
    last_rssi_dbm: float = -70.0
    last_hop_count: int = 1
    mean_interval_sec: float = 1.0
    jitter_sec: float = 0.0
    q_mesh: float = 1.0
    recent_intervals: List[float] = field(default_factory=list)


class QoSTracker:
    """
    Monitors packet telemetry stream per sensor node.
    Provides verified metric calculations for Section 8 (>96.5% PDR)
    and computes the Q_mesh confidence multiplier for Phase 3.
    """

    def __init__(self, nominal_interval_sec: float = 1.0, window_size: int = 300):
        self.nominal_interval_sec = nominal_interval_sec
        self.window_size = window_size
        self.nodes: Dict[str, NodeQoSMetrics] = {}

    def record_packet(self, record: RawSensorRecord) -> NodeQoSMetrics:
        node_id = record.node_id
        timestamp = record.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        if node_id not in self.nodes:
            self.nodes[node_id] = NodeQoSMetrics(
                node_id=node_id,
                total_received=1,
                total_expected=1,
                packet_delivery_ratio=1.0,
                first_seen_utc=timestamp,
                last_seen_utc=timestamp,
                last_battery_pct=record.node_health.battery_pct,
                last_rssi_dbm=record.node_health.rssi_dbm,
                last_hop_count=record.node_health.hop_count,
                mean_interval_sec=self.nominal_interval_sec,
                jitter_sec=0.0,
                q_mesh=1.0,
            )
            return self.nodes[node_id]

        m = self.nodes[node_id]
        prev_ts = m.last_seen_utc
        dt = (timestamp - prev_ts).total_seconds() if prev_ts else self.nominal_interval_sec

        # Update timings
        m.total_received += 1
        m.last_seen_utc = timestamp
        m.last_battery_pct = record.node_health.battery_pct
        m.last_rssi_dbm = record.node_health.rssi_dbm
        m.last_hop_count = record.node_health.hop_count

        if dt > 0:
            m.recent_intervals.append(dt)
            if len(m.recent_intervals) > self.window_size:
                m.recent_intervals.pop(0)

            m.mean_interval_sec = float(np.mean(m.recent_intervals))
            m.jitter_sec = float(np.std(m.recent_intervals)) if len(m.recent_intervals) > 1 else 0.0

        # Calculate expected packets based on elapsed duration
        if m.first_seen_utc and m.last_seen_utc:
            total_elapsed = max(0.0, (m.last_seen_utc - m.first_seen_utc).total_seconds())
            expected = int(np.round(total_elapsed / self.nominal_interval_sec)) + 1
            m.total_expected = max(m.total_received, expected)

        # Packet Delivery Ratio (PDR)
        m.packet_delivery_ratio = float(min(1.0, m.total_received / max(1, m.total_expected)))

        # Q_mesh = 0.60 * PDR + 0.25 * (battery / 100) + 0.15 * normalized_rssi
        # RSSI normalized from [-110 dBm (0.0) to -50 dBm (1.0)]
        norm_rssi = float(np.clip((record.node_health.rssi_dbm - (-110.0)) / ((-50.0) - (-110.0)), 0.0, 1.0))
        batt_norm = float(np.clip(record.node_health.battery_pct / 100.0, 0.0, 1.0))

        m.q_mesh = float(np.clip(0.60 * m.packet_delivery_ratio + 0.25 * batt_norm + 0.15 * norm_rssi, 0.0, 1.0))
        return m

    def get_metrics(self, node_id: str) -> Optional[NodeQoSMetrics]:
        return self.nodes.get(node_id)

    def get_mesh_summary(self) -> Dict[str, float]:
        """Calculates global mesh telemetry health statistics."""
        if not self.nodes:
            return {"mean_pdr": 1.0, "mean_q_mesh": 1.0, "active_nodes": 0}

        pdrs = [m.packet_delivery_ratio for m in self.nodes.values()]
        q_meshes = [m.q_mesh for m in self.nodes.values()]
        return {
            "mean_pdr": float(np.mean(pdrs)),
            "min_pdr": float(np.min(pdrs)),
            "mean_q_mesh": float(np.mean(q_meshes)),
            "active_nodes": len(self.nodes),
        }
