"""
Feature Engineering Pipeline Test Suite.
Includes hand-computed mathematical reference window verification asserting exact numerical precision.
Validates ADR-001 (FEATURE_VECTOR_DIM = 12).
"""

import math
from datetime import datetime, timezone, timedelta
import numpy as np
import pytest

from features.constants import FEATURE_VECTOR_DIM, FEATURE_NAMES
from features.geometry_loader import MineGeometryLoader, haversine_distance_m
from features.pipeline import FeaturePipeline
from ingestion.schema import RawSensorRecord, GPSData, SensorData, NodeHealthData


def create_record(ts: datetime, tilt: float, disp: float, vib: float, crack: float, lat: float = 23.791204, lon: float = 86.433129) -> RawSensorRecord:
    return RawSensorRecord(
        node_id="SS-PANEL7-N042",
        timestamp=ts,
        gps=GPSData(lat=lat, lon=lon, elevation_m=242.6),
        sensors=SensorData(
            tilt_deg=tilt,
            vibration_rms_mm_s=vib,
            displacement_mm=disp,
            crack_index=crack,
        ),
        node_health=NodeHealthData(battery_pct=85.0, rssi_dbm=-68.0, hop_count=2),
    )


def test_feature_vector_dimension_constant():
    """Asserts ADR-001: FEATURE_VECTOR_DIM is 12 and matches FEATURE_NAMES length."""
    assert FEATURE_VECTOR_DIM == 12
    assert len(FEATURE_NAMES) == 12
    assert FEATURE_NAMES[11] == "crack_index"


def test_hand_computed_reference_window_assertion():
    """
    HAND-COMPUTED REFERENCE CALCULATION:
    6 samples over 5-minute (300-second) window with 60-second increments:
    t = [0, 60, 120, 180, 240, 300] seconds

    1. Tilt values: [0.10, 0.12, 0.14, 0.16, 0.18, 0.20]
       - tilt_mean: (0.10 + 0.12 + 0.14 + 0.16 + 0.18 + 0.20) / 6 = 0.150000 deg
       - tilt_std: sqrt(sum((x - 0.15)^2) / 5) = sqrt(0.0070 / 5) = sqrt(0.0014) = 0.03741657 deg
       - tilt_slope_dt: (0.20 - 0.10) / 300 s = 0.00033333 deg/s * 3600 s/hr = 1.200000 deg/hr

    2. Displacement values: [2.00, 2.50, 3.00, 3.50, 4.00, 4.50]
       - disp_max: 4.500000 mm
       - disp_rate_mm_h: (4.50 - 2.00) / 300 s = 2.50 / 300 * 3600 = 30.000000 mm/hr

    3. Vibration values: [1.00, 1.00, 1.00, 1.00, 1.00, 3.00]
       - vib_rms_max: 3.000000 mm/s
       - crest_factor: 3.00 / mean([1, 1, 1, 1, 1, 3]) = 3.00 / (8/6) = 3.00 / 1.333333 = 2.250000

    4. Crack Index: [0.01, 0.015, 0.02, 0.025, 0.03, 0.035]
       - raw crack_index at window end: 0.035000 (pass-through 12th feature)
    """
    t0 = datetime(2026, 9, 9, 4, 10, 0, tzinfo=timezone.utc)
    records = [
        create_record(t0 + timedelta(seconds=0), tilt=0.10, disp=2.00, vib=1.00, crack=0.010),
        create_record(t0 + timedelta(seconds=60), tilt=0.12, disp=2.50, vib=1.00, crack=0.015),
        create_record(t0 + timedelta(seconds=120), tilt=0.14, disp=3.00, vib=1.00, crack=0.020),
        create_record(t0 + timedelta(seconds=180), tilt=0.16, disp=3.50, vib=1.00, crack=0.025),
        create_record(t0 + timedelta(seconds=240), tilt=0.18, disp=4.00, vib=1.00, crack=0.030),
        create_record(t0 + timedelta(seconds=300), tilt=0.20, disp=4.50, vib=3.00, crack=0.035),
    ]

    pipeline = FeaturePipeline(stride_sec=30.0)
    pipeline.update_node_position("SS-PANEL7-N041", 23.791500, 86.433500) # Neighbor for distance calculation

    # Compute raw vector
    raw_vec = pipeline.compute_window_vector(records, "SS-PANEL7-N042")

    # Explicit Assertions against hand-computed reference values
    # Feature 0: tilt_mean
    assert np.isclose(raw_vec[0], 0.150, atol=1e-4), f"tilt_mean {raw_vec[0]} != 0.150"

    # Feature 1: tilt_std
    expected_std = math.sqrt(0.0014)
    assert np.isclose(raw_vec[1], expected_std, atol=1e-4), f"tilt_std {raw_vec[1]} != {expected_std}"

    # Feature 2: tilt_slope_dt
    assert np.isclose(raw_vec[2], 1.200, atol=1e-4), f"tilt_slope_dt {raw_vec[2]} != 1.200 deg/h"

    # Feature 3: disp_max
    assert np.isclose(raw_vec[3], 4.500, atol=1e-4), f"disp_max {raw_vec[3]} != 4.500 mm"

    # Feature 4: disp_rate_mm_h
    assert np.isclose(raw_vec[4], 30.000, atol=1e-4), f"disp_rate_mm_h {raw_vec[4]} != 30.000 mm/h"

    # Feature 5: vib_rms_max
    assert np.isclose(raw_vec[5], 3.000, atol=1e-4), f"vib_rms_max {raw_vec[5]} != 3.000 mm/s"

    # Feature 7: crest_factor
    assert np.isclose(raw_vec[7], 2.250, atol=1e-3), f"crest_factor {raw_vec[7]} != 2.250"

    # Feature 11: crack_index (pass-through raw value at window end)
    assert np.isclose(raw_vec[11], 0.035, atol=1e-4), f"crack_index {raw_vec[11]} != 0.035"

    assert len(raw_vec) == FEATURE_VECTOR_DIM


def test_spatial_topology_features():
    """Verifies goaf distance and pillar stress index calculations."""
    geom = MineGeometryLoader()
    # Coordinates inside/near Panel 7
    lat, lon = 23.791204, 86.433129
    dist_goaf = geom.dist_to_goaf_edge_m(lat, lon)
    assert dist_goaf >= 0.0
    assert dist_goaf < 1000.0

    stress_idx = geom.pillar_stress_index(lat, lon)
    assert 0.0 <= stress_idx <= 1.0


def test_robust_scaler_normalization():
    """Verifies that RobustScaler scales inputs based on median and IQR."""
    pipeline = FeaturePipeline()
    np.random.seed(42)
    sample_data = np.random.normal(loc=5.0, scale=2.0, size=(100, FEATURE_VECTOR_DIM)).astype(np.float32)
    pipeline.fit_scaler(sample_data)

    test_vec = np.full((FEATURE_VECTOR_DIM,), 5.0, dtype=np.float32)
    norm_vec = pipeline.transform(test_vec)
    # Since test_vec equals the mean/median, normalized vector should be close to 0
    assert np.all(np.abs(norm_vec) < 0.5)
