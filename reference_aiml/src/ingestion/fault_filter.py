from typing import List, Dict, Tuple, Set
import numpy as np
from src.schemas.sensor_contracts import SensorReading, NodeHealthMetadata

class SensorFaultFilter:
    """
    Data-Quality & Sensor-Fault Filtering Stage (Section 3.3).
    Prevents hardware failure modes (dead batteries, frozen ADCs, loose mounts)
    from misclassifying as genuine ground subsidence.
    """

    def __init__(
        self,
        min_battery_voltage: float = 2.4,
        min_rssi_dbm: float = -115.0,
        flatline_variance_threshold: float = 1e-6,
        spike_z_score_threshold: float = 4.5,
    ):
        self.min_battery_voltage = min_battery_voltage
        self.min_rssi_dbm = min_rssi_dbm
        self.flatline_variance_threshold = flatline_variance_threshold
        self.spike_z_score_threshold = spike_z_score_threshold

    def evaluate_node(
        self,
        readings: List[SensorReading],
        health: NodeHealthMetadata,
    ) -> Tuple[bool, str]:
        """
        Evaluates a node's readings and health status.
        Returns (is_valid, reason_if_invalid).
        """
        # 1. Health metadata checks
        if health.is_faulty:
            return False, "Node explicitly flagged as faulty in mesh health metadata."

        if health.battery_voltage < self.min_battery_voltage:
            return False, f"Degraded battery voltage ({health.battery_voltage:.2f}V < {self.min_battery_voltage}V); high risk of ADC brownout spikes."

        if health.rssi_dbm < self.min_rssi_dbm:
            return False, f"Degraded RF signal strength ({health.rssi_dbm:.1f} dBm < {self.min_rssi_dbm} dBm); telemetry packet corruption likely."

        if len(readings) < 5:
            return False, f"Insufficient samples ({len(readings)}) for windowed inference."

        # 2. Sensor reading statistical checks
        tilts = np.array([r.tilt_deg for r in readings])
        vibrations = np.array([r.vibration_g for r in readings])
        displacements = np.array([r.displacement_mm for r in readings])

        # Flat-lining detection (frozen sensor)
        if np.var(tilts) < self.flatline_variance_threshold and np.var(vibrations) < self.flatline_variance_threshold:
            return False, "Sensor reading variance near zero; hardware flatline / frozen ADC detected."

        # Physical limit bounds check
        if np.any(np.abs(tilts) > 85.0):
            return False, "Tilt reading exceeds physical underground limits (> 85 deg); sensor dislodged or inverted."

        if np.any(displacements < -50.0) or np.any(displacements > 5000.0):
            return False, "Displacement value outside plausible physical mine geomechanical range."

        return True, "Node telemetry validated for inference."

    def filter_mesh_batch(
        self,
        node_readings_map: Dict[str, List[SensorReading]],
        node_health_map: Dict[str, NodeHealthMetadata],
    ) -> Tuple[Dict[str, List[SensorReading]], Dict[str, str]]:
        """
        Filters an entire mesh batch.
        Returns (valid_nodes_map, quarantined_nodes_with_reasons).
        """
        valid_nodes: Dict[str, List[SensorReading]] = {}
        quarantined_nodes: Dict[str, str] = {}

        for node_id, readings in node_readings_map.items():
            health = node_health_map.get(
                node_id,
                NodeHealthMetadata(
                    node_id=node_id,
                    timestamp=readings[-1].timestamp if readings else None,
                    battery_voltage=3.3,
                    rssi_dbm=-75.0,
                )
            )
            is_valid, reason = self.evaluate_node(readings, health)
            if is_valid:
                valid_nodes[node_id] = readings
            else:
                quarantined_nodes[node_id] = reason

        return valid_nodes, quarantined_nodes
