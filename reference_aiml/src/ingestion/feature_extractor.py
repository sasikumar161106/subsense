from typing import List, Dict, Optional
import numpy as np
from src.schemas.sensor_contracts import SensorReading, EngineeredFeatureVector

class FeatureExtractor:
    """
    Windowing & Feature Extraction Stage (Section 3.2).
    Extracts physically grounded time-series statistical features from sliding windows.
    Matches the feature specification shared with the TinyML Edge layer.
    """

    def __init__(self, short_var_window: int = 10):
        self.short_var_window = short_var_window

    def extract_features(
        self,
        node_id: str,
        readings: List[SensorReading],
        baseline_displacement: Optional[float] = None,
    ) -> EngineeredFeatureVector:
        if not readings:
            raise ValueError(f"Cannot extract features from empty readings list for node {node_id}")

        tilts = np.array([r.tilt_deg for r in readings], dtype=np.float64)
        vibrations = np.array([r.vibration_g for r in readings], dtype=np.float64)
        displacements = np.array([r.displacement_mm for r in readings], dtype=np.float64)
        cracks = np.array([1.0 if r.crack_sensor_active else 0.0 for r in readings], dtype=np.float64)

        n = len(readings)

        # 1. Tilt features
        tilt_mean = float(np.mean(tilts))
        # Rate of change: delta over window duration
        tilt_rate = float((tilts[-1] - tilts[0]) / max(1, n - 1))
        # Short-window vs long-window variance
        k_short = min(self.short_var_window, n)
        tilt_var_short = float(np.var(tilts[-k_short:]))
        tilt_var_long = float(np.var(tilts))

        # 2. Vibration features
        vibration_rms = float(np.sqrt(np.mean(vibrations ** 2)))
        vibration_peak = float(np.max(vibrations)) if len(vibrations) > 0 else 0.0
        vibration_peak_ratio = float(vibration_peak / (vibration_rms + 1e-6))

        # 3. Displacement features
        base_disp = baseline_displacement if baseline_displacement is not None else displacements[0]
        displacement_delta = float(displacements[-1] - base_disp)
        displacement_cum_drift = float(np.sum(np.abs(np.diff(displacements)))) if n > 1 else 0.0

        # 4. Crack features
        crack_active_ratio = float(np.mean(cracks))

        return EngineeredFeatureVector(
            node_id=node_id,
            timestamp=readings[-1].timestamp,
            tilt_mean=tilt_mean,
            tilt_rate=tilt_rate,
            tilt_var_short=tilt_var_short,
            tilt_var_long=tilt_var_long,
            vibration_rms=vibration_rms,
            vibration_peak_ratio=vibration_peak_ratio,
            displacement_delta=displacement_delta,
            displacement_cum_drift=displacement_cum_drift,
            crack_active_ratio=crack_active_ratio,
        )

    def extract_batch(
        self,
        node_readings_map: Dict[str, List[SensorReading]],
        baselines_map: Optional[Dict[str, float]] = None,
    ) -> Dict[str, EngineeredFeatureVector]:
        baselines = baselines_map or {}
        feature_map: Dict[str, EngineeredFeatureVector] = {}

        for node_id, readings in node_readings_map.items():
            if readings:
                feature_map[node_id] = self.extract_features(
                    node_id=node_id,
                    readings=readings,
                    baseline_displacement=baselines.get(node_id),
                )

        return feature_map
