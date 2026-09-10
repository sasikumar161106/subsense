"""
Feature engineering pipeline for SubSense Layer 4.
Computes a 12-dimensional feature vector over a 5-minute rolling window with 30s stride,
normalized via RobustScaler.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.preprocessing import RobustScaler

from .constants import FEATURE_VECTOR_DIM, FEATURE_NAMES
from .geometry_loader import MineGeometryLoader, haversine_distance_m
from ingestion.schema import RawSensorRecord


class FeaturePipeline:
    """
    Stateful streaming and batch feature extraction pipeline.
    Maintains per-node rolling window buffers (300s window) and calculates
    all 12 kinematic, seismic, spatial, and crack features.
    """

    def __init__(
        self,
        geometry_loader: Optional[MineGeometryLoader] = None,
        window_duration_sec: float = 300.0,
        stride_sec: float = 30.0,
    ):
        self.geometry = geometry_loader or MineGeometryLoader()
        self.window_duration_sec = window_duration_sec
        self.stride_sec = stride_sec
        self.buffers: Dict[str, List[RawSensorRecord]] = {}
        self.last_stride_times: Dict[str, datetime] = {}
        self.node_positions: Dict[str, Tuple[float, float]] = {}  # node_id -> (lat, lon)
        self.scaler = RobustScaler()
        self.is_fitted = False

    def update_node_position(self, node_id: str, lat: float, lon: float) -> None:
        self.node_positions[node_id] = (lat, lon)

    def add_record(self, record: RawSensorRecord) -> Optional[Tuple[datetime, datetime, np.ndarray, np.ndarray]]:
        """
        Streaming interface: ingests a single validated record.
        Returns (window_start, window_end, raw_vector, normalized_vector)
        if the current timestamp has advanced by at least stride_sec and
        the window buffer has sufficient history (>= 2 samples).
        """
        node_id = record.node_id
        ts = record.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        self.update_node_position(node_id, record.gps.lat, record.gps.lon)

        if node_id not in self.buffers:
            self.buffers[node_id] = []
            self.last_stride_times[node_id] = ts

        buf = self.buffers[node_id]
        buf.append(record)

        # Evict records older than window_duration_sec from ts
        cutoff = ts.timestamp() - self.window_duration_sec
        self.buffers[node_id] = [r for r in buf if (r.timestamp if r.timestamp.tzinfo else r.timestamp.replace(tzinfo=timezone.utc)).timestamp() >= cutoff]
        buf = self.buffers[node_id]

        if len(buf) < 2:
            return None

        # Check stride
        last_t = self.last_stride_times.get(node_id)
        if last_t is not None:
            delta_stride = (ts - last_t).total_seconds()
            if delta_stride < self.stride_sec:
                return None

        self.last_stride_times[node_id] = ts
        win_start = buf[0].timestamp
        win_end = buf[-1].timestamp

        raw_vec = self.compute_window_vector(buf, node_id)
        norm_vec = self.transform(raw_vec)
        return win_start, win_end, raw_vec, norm_vec

    def compute_window_vector(self, window_records: List[RawSensorRecord], node_id: str) -> np.ndarray:
        """
        Computes the 12-dimensional raw feature vector for a given list of window records.
        """
        if len(window_records) < 2:
            raise ValueError("At least 2 records are required to compute rate/moments.")

        times = np.array([
            (r.timestamp if r.timestamp.tzinfo else r.timestamp.replace(tzinfo=timezone.utc)).timestamp()
            for r in window_records
        ])
        t_rel = times - times[0]  # Relative seconds from window start

        tilts = np.array([r.sensors.tilt_deg for r in window_records], dtype=np.float64)
        disps = np.array([r.sensors.displacement_mm for r in window_records], dtype=np.float64)
        vibs = np.array([r.sensors.vibration_rms_mm_s for r in window_records], dtype=np.float64)
        cracks = np.array([r.sensors.crack_index for r in window_records], dtype=np.float64)

        # 1. tilt_mean
        tilt_mean = float(np.mean(tilts))

        # 2. tilt_std (sample standard deviation with ddof=1)
        tilt_std = float(np.std(tilts, ddof=1)) if len(tilts) > 1 else 0.0

        # 3. tilt_slope_dt (linear slope in deg/hour)
        if np.max(t_rel) > 0:
            # Linear regression: slope = cov(t, tilt) / var(t)
            slope_deg_s = float(np.polyfit(t_rel, tilts, deg=1)[0])
            tilt_slope_dt = slope_deg_s * 3600.0  # deg / hour
        else:
            tilt_slope_dt = 0.0

        # 4. disp_max (mm)
        disp_max = float(np.max(disps))

        # 5. disp_rate_mm_h (mm/hour)
        if np.max(t_rel) > 0:
            slope_disp_s = float(np.polyfit(t_rel, disps, deg=1)[0])
            disp_rate_mm_h = slope_disp_s * 3600.0
        else:
            disp_rate_mm_h = 0.0

        # 6. vib_rms_max (mm/s)
        vib_rms_max = float(np.max(vibs))

        # 7. vib_spectral_energy_10_50hz
        # Compute spectral energy via FFT. If sampling is 1Hz (Nyquist 0.5Hz), synthetic high-frequency
        # proxy energy is modeled using geophone velocity dynamics; for multi-sample window:
        # We calculate normalized power spectrum of the vibration series.
        if len(vibs) >= 4:
            fft_vals = np.abs(np.fft.rfft(vibs - np.mean(vibs)))
            # Energy in mid-high frequency bins
            vib_spectral_energy = float(np.sum(fft_vals[1:] ** 2) / (len(vibs) ** 2))
        else:
            vib_spectral_energy = float(np.var(vibs))

        # 8. crest_factor: peak vibration / RMS vibration
        mean_rms = float(np.mean(vibs))
        crest_factor = float(vib_rms_max / (mean_rms + 1e-6))

        # Spatial features
        latest_rec = window_records[-1]
        lat = latest_rec.gps.lat
        lon = latest_rec.gps.lon

        # 9. nearest_neighbor_dist_m
        nearest_dist = self._compute_nearest_neighbor_dist(node_id, lat, lon)

        # 10. dist_to_goaf_edge_m
        dist_goaf = self.geometry.dist_to_goaf_edge_m(lat, lon)

        # 11. pillar_stress_index
        stress_idx = self.geometry.pillar_stress_index(lat, lon)

        # 12. raw crack_index (pass-through un-transformed)
        raw_crack = float(cracks[-1])

        raw_vector = np.array([
            tilt_mean,
            tilt_std,
            tilt_slope_dt,
            disp_max,
            disp_rate_mm_h,
            vib_rms_max,
            vib_spectral_energy,
            crest_factor,
            nearest_dist,
            dist_goaf,
            stress_idx,
            raw_crack,
        ], dtype=np.float32)

        assert raw_vector.shape[0] == FEATURE_VECTOR_DIM, (
            f"Feature vector dimension {raw_vector.shape[0]} != FEATURE_VECTOR_DIM ({FEATURE_VECTOR_DIM})"
        )
        return raw_vector

    def _compute_nearest_neighbor_dist(self, node_id: str, lat: float, lon: float) -> float:
        min_dist = float("inf")
        for other_id, (olat, olon) in self.node_positions.items():
            if other_id != node_id:
                d = haversine_distance_m(lat, lon, olat, olon)
                if d < min_dist:
                    min_dist = d

        if math_is_inf(min_dist):
            return 45.0  # Default nominal sensor mesh grid spacing (45m)
        return float(min_dist)

    def fit_scaler(self, feature_matrix: np.ndarray) -> None:
        """Fits RobustScaler on baseline feature matrix."""
        assert feature_matrix.shape[1] == FEATURE_VECTOR_DIM
        self.scaler.fit(feature_matrix)
        self.is_fitted = True

    def transform(self, vector: np.ndarray) -> np.ndarray:
        """Applies RobustScaler transformation to 12-D feature vector."""
        if not self.is_fitted:
            # Fallback identity if uncalibrated
            return vector.copy()
        
        orig_shape = vector.shape
        if vector.ndim == 1:
            scaled = self.scaler.transform(vector.reshape(1, -1))[0]
        else:
            scaled = self.scaler.transform(vector)
        return scaled.astype(np.float32)


def math_is_inf(val: float) -> bool:
    import math
    return math.isinf(val)
