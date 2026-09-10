import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple
from src.schemas.sensor_contracts import SensorReading, NodeHealthMetadata

class SyntheticSubsidenceDataGenerator:
    """
    Generates high-fidelity synthetic multi-sensor time-series representing:
    1. Normal stable ground conditions.
    2. Subsidence precursors (progressive tilt, micro-seismic vibrations, strain drift, crack opening).
    3. Hardware fault signatures (flatline, battery brownout spikes, RSSI loss).
    4. Satellite InSAR Line-of-Sight deformation grids.
    """

    def __init__(self, seed: int = 42):
        np.random.seed(seed)

    def generate_node_series(
        self,
        node_id: str,
        n_samples: int = 120,
        start_time: datetime = None,
        interval_seconds: float = 1.0,
        scenario: str = "normal",  # "normal" | "subsidence_precursor" | "hardware_fault"
        precursor_onset_idx: int = 60,
    ) -> Tuple[List[SensorReading], NodeHealthMetadata]:
        if start_time is None:
            start_time = datetime.now(timezone.utc) - timedelta(seconds=n_samples * interval_seconds)

        readings: List[SensorReading] = []
        t = np.arange(n_samples)

        # Baseline noise levels
        tilt_base = 0.5 + 0.05 * np.random.randn(n_samples)
        vibration_base = 0.02 + 0.005 * np.abs(np.random.randn(n_samples))
        displacement_base = 1.2 + 0.02 * np.random.randn(n_samples)
        crack_base = np.zeros(n_samples, dtype=bool)

        battery_voltage = 3.3
        rssi_dbm = -75.0
        is_faulty = False

        if scenario == "subsidence_precursor":
            # Post-onset progressive exponential acceleration
            for i in range(precursor_onset_idx, n_samples):
                step = i - precursor_onset_idx
                # Tilt ramps up non-linearly
                tilt_base[i] += 0.08 * (step ** 1.3)
                # Vibration shows energetic bursts
                vibration_base[i] += 0.04 * (1.0 + 0.5 * np.sin(step)) * (step / 20.0)
                # Displacement exhibits continuous creeping strain
                displacement_base[i] += 0.25 * (step ** 1.2)
                # Crack sensor trips when strain exceeds threshold
                if displacement_base[i] > 8.0:
                    crack_base[i] = True

        elif scenario == "hardware_fault":
            fault_type = np.random.choice(["flatline", "low_battery_spike"])
            if fault_type == "flatline":
                # Sensor ADC freezes
                frozen_val = 1.500000
                tilt_base[precursor_onset_idx:] = frozen_val
                vibration_base[precursor_onset_idx:] = 0.0
                displacement_base[precursor_onset_idx:] = 5.0
                is_faulty = True
            elif fault_type == "low_battery_spike":
                battery_voltage = 2.1  # Degraded battery
                rssi_dbm = -118.0
                # Erratic ADC power rail collapse spikes
                for i in range(precursor_onset_idx, n_samples):
                    if np.random.rand() > 0.6:
                        tilt_base[i] += 25.0 * np.random.randn()
                        vibration_base[i] += 5.0 * np.random.rand()
                is_faulty = True

        for i in range(n_samples):
            curr_time = start_time + timedelta(seconds=i * interval_seconds)
            readings.append(
                SensorReading(
                    node_id=node_id,
                    timestamp=curr_time,
                    tilt_deg=float(np.clip(tilt_base[i], -90.0, 90.0)),
                    vibration_g=float(max(0.0, vibration_base[i])),
                    displacement_mm=float(displacement_base[i]),
                    crack_sensor_active=bool(crack_base[i]),
                )
            )

        health = NodeHealthMetadata(
            node_id=node_id,
            timestamp=start_time + timedelta(seconds=n_samples * interval_seconds),
            battery_voltage=float(battery_voltage),
            rssi_dbm=float(rssi_dbm),
            packet_loss_pct=0.0 if not is_faulty else 18.5,
            is_faulty=is_faulty,
        )

        return readings, health

    def generate_mesh_telemetry_batch(
        self,
        node_ids: List[str],
        active_zone_nodes: List[str],
        n_samples: int = 60,
        start_time: datetime = None,
    ) -> Dict[str, Tuple[List[SensorReading], NodeHealthMetadata]]:
        results = {}
        for nid in node_ids:
            if nid in active_zone_nodes:
                scenario = "subsidence_precursor"
            elif nid == "N-FAULTY":
                scenario = "hardware_fault"
            else:
                scenario = "normal"
            readings, health = self.generate_node_series(
                node_id=nid,
                n_samples=n_samples,
                start_time=start_time,
                scenario=scenario,
                precursor_onset_idx=15,
            )
            results[nid] = (readings, health)
        return results

    def generate_synthetic_insar_grid(
        self,
        bounds_utm: Tuple[float, float, float, float],
        grid_shape: Tuple[int, int] = (20, 20),
        basin_center_utm: Tuple[float, float] = (442450.0, 2631700.0),
        max_los_velocity: float = -28.5,  # mm/yr line-of-sight subsidence
    ) -> np.ndarray:
        """Generates a Sentinel-1 InSAR Line-of-Sight velocity raster in mm/year."""
        min_x, min_y, max_x, max_y = bounds_utm
        xs = np.linspace(min_x, max_x, grid_shape[1])
        ys = np.linspace(min_y, max_y, grid_shape[0])
        xx, yy = np.meshgrid(xs, ys)

        cx, cy = basin_center_utm
        dist_sq = (xx - cx) ** 2 + (yy - cy) ** 2
        sigma = 180.0  # Basin width in meters

        # Gaussian subsidence bowl
        velocity = max_los_velocity * np.exp(-dist_sq / (2 * sigma ** 2))
        # Atmospheric & speckle noise
        velocity += np.random.normal(0.0, 1.5, size=grid_shape)
        return velocity
