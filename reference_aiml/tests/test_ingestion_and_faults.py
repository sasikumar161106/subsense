import pytest
from datetime import datetime, timezone, timedelta
from src.schemas.sensor_contracts import SensorReading, NodeHealthMetadata
from src.ingestion.fault_filter import SensorFaultFilter
from src.ingestion.feature_extractor import FeatureExtractor
from src.ingestion.window_buffer import SlidingWindowBuffer
from data.synthetic_generator import SyntheticSubsidenceDataGenerator

def test_sliding_window_buffer():
    buf = SlidingWindowBuffer(window_size=10, min_samples_for_inference=5)
    now = datetime.now(timezone.utc)

    # Append 4 samples (below min threshold)
    for i in range(4):
        buf.append_reading(SensorReading(
            node_id="N-01",
            timestamp=now + timedelta(seconds=i),
            tilt_deg=0.5,
            vibration_g=0.02,
            displacement_mm=1.0,
            crack_sensor_active=False
        ))
    assert buf.get_window("N-01") is None

    # Append 5th sample
    buf.append_reading(SensorReading(
        node_id="N-01",
        timestamp=now + timedelta(seconds=4),
        tilt_deg=0.6,
        vibration_g=0.02,
        displacement_mm=1.1,
        crack_sensor_active=False
    ))
    window = buf.get_window("N-01")
    assert window is not None
    assert len(window) == 5

    # Test overflow capacity (window_size=10)
    for i in range(5, 15):
        buf.append_reading(SensorReading(
            node_id="N-01",
            timestamp=now + timedelta(seconds=i),
            tilt_deg=0.5,
            vibration_g=0.02,
            displacement_mm=1.0,
            crack_sensor_active=False
        ))
    assert len(buf.get_window("N-01")) == 10

def test_sensor_fault_filter_rejects_degraded_battery():
    gen = SyntheticSubsidenceDataGenerator()
    readings, health = gen.generate_node_series("N-BATTERY-LOW", n_samples=30, scenario="normal")
    health.battery_voltage = 2.1  # Degraded voltage < 2.4V
    health.is_faulty = False

    ff = SensorFaultFilter()
    is_valid, reason = ff.evaluate_node(readings, health)
    assert not is_valid
    assert "battery" in reason.lower()

def test_sensor_fault_filter_rejects_flatline():
    now = datetime.now(timezone.utc)
    readings = [
        SensorReading(
            node_id="N-FLAT",
            timestamp=now + timedelta(seconds=i),
            tilt_deg=1.2345,
            vibration_g=0.0,
            displacement_mm=2.0,
            crack_sensor_active=False
        ) for i in range(30)
    ]
    health = NodeHealthMetadata(
        node_id="N-FLAT",
        timestamp=now,
        battery_voltage=3.3,
        rssi_dbm=-70.0
    )
    ff = SensorFaultFilter()
    is_valid, reason = ff.evaluate_node(readings, health)
    assert not is_valid
    assert "flatline" in reason.lower()

def test_feature_extractor():
    gen = SyntheticSubsidenceDataGenerator()
    readings, _ = gen.generate_node_series(
        "N-TEST",
        n_samples=40,
        scenario="subsidence_precursor",
        precursor_onset_idx=10,
    )

    fe = FeatureExtractor()
    fvec = fe.extract_features("N-TEST", readings)

    assert fvec.node_id == "N-TEST"
    assert fvec.tilt_mean > 0.0
    assert fvec.tilt_rate > 0.0  # Ramping tilt
    assert fvec.vibration_rms > 0.0
    assert fvec.displacement_delta > 0.0
    feature_list = fvec.to_feature_list()
    assert len(feature_list) == 8
