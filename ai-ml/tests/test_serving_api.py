"""
FastAPI Serving API, Streaming Ingestion Sinks, and QoS Tracker Test Suite.
Verifies /v1/health, /v1/score, /v1/correlate, /v1/sync,
streaming window buffer eviction, Kafka publishers, and TimescaleDB sinks.
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from models.serving.app import app
from features.pipeline import FeaturePipeline
from ingestion.schema import RawSensorRecord, GPSData, SensorData, NodeHealthData
from ingestion.pipeline import IngestionPipeline
from ingestion.qos_tracker import QoSTracker


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    """Verifies GET /v1/health status and metadata."""
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert data["feature_dim"] == 12
    assert "isoforest_ae_ensemble" in data["model_signature"]


def test_score_endpoint_valid_and_invalid(client):
    """Verifies POST /v1/score with valid and invalid dimensions."""
    now = datetime.now(timezone.utc)
    t0 = now - timedelta(minutes=5)

    # 1. Valid 12-D vector
    valid_body = {
        "node_id": "SS-PANEL7-N042",
        "window_start": t0.isoformat(),
        "window_end": now.isoformat(),
        "feature_vector_12d": [0.15, 0.02, 1.2, 4.5, 30.0, 3.0, 0.05, 2.25, 45.0, 50.0, 0.25, 0.035],
    }
    resp = client.post("/v1/score", json=valid_body)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["node_id"] == "SS-PANEL7-N042"
    assert 0.0 <= res_data["anomaly_score"] <= 1.0
    assert len(res_data["contributing_sensors"]) > 0

    # 2. Invalid dimension (11 instead of 12)
    invalid_body = {
        "node_id": "SS-PANEL7-N042",
        "window_start": t0.isoformat(),
        "window_end": now.isoformat(),
        "feature_vector_12d": [0.15] * 11,
    }
    resp_bad = client.post("/v1/score", json=invalid_body)
    assert resp_bad.status_code in [400, 422]


def test_correlate_endpoint(client):
    """Verifies POST /v1/correlate endpoint."""
    now = datetime.now(timezone.utc)
    body = {
        "node_id": "SS-PANEL7-N042",
        "timestamp": now.isoformat(),
        "lat": 23.791204,
        "lon": 86.433129,
        "raw_anomaly_score": 0.85,
        "delta_tilt_deg": 0.25,
        "delta_displacement_mm": 2.50,
        "delta_vibration_rms_mm_s": 5.0,
        "delta_crack_index": 0.02,
    }
    resp = client.post("/v1/correlate", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_id"] == "SS-PANEL7-N042"
    assert data["is_multi_channel_concordant"] is True
    assert 0.0 <= data["corroboration_coefficient"] <= 1.0


def test_edge_sync_endpoint(client):
    """Verifies POST /v1/sync backfill endpoint."""
    now = datetime.now(timezone.utc)
    body = {
        "node_id": "SS-PANEL7-N042",
        "gateway_id": "GW-PANEL7-01",
        "sync_timestamp": now.isoformat(),
        "events": [
            {"record_id": 1, "anomaly_score": 0.78, "timestamp": now.isoformat()},
            {"record_id": 2, "anomaly_score": 0.81, "timestamp": now.isoformat()},
        ],
    }
    resp = client.post("/v1/sync", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SYNCED"
    assert data["synced_events_count"] == 2


def test_feature_pipeline_streaming_buffer():
    """Verifies streaming add_record with stride and window eviction."""
    pipe = FeaturePipeline(window_duration_sec=300.0, stride_sec=30.0)
    t0 = datetime(2026, 9, 9, 4, 0, 0, tzinfo=timezone.utc)

    def make_rec(sec):
        return RawSensorRecord(
            node_id="SS-PANEL7-N042",
            timestamp=t0 + timedelta(seconds=sec),
            gps=GPSData(lat=23.791204, lon=86.433129, elevation_m=242.6),
            sensors=SensorData(tilt_deg=0.10, vibration_rms_mm_s=1.0, displacement_mm=2.0, crack_index=0.01),
            node_health=NodeHealthData(battery_pct=90.0, rssi_dbm=-70.0, hop_count=2),
        )

    # Add sample 0
    res0 = pipe.add_record(make_rec(0))
    assert res0 is None  # Needs at least 2 samples

    # Add sample at +10s (less than stride 30s)
    res10 = pipe.add_record(make_rec(10))
    assert res10 is None

    # Add sample at +35s (stride >= 30s satisfied!)
    res35 = pipe.add_record(make_rec(35))
    assert res35 is not None
    win_start, win_end, raw_vec, norm_vec = res35
    assert len(raw_vec) == 12
    assert len(norm_vec) == 12

    # Add sample at +400s (older samples 0, 10, 35 evicted because 400 - 300 = 100 > 35)
    res400 = pipe.add_record(make_rec(400))
    assert res400 is None  # Only 1 sample in window after eviction

    # Add sample at +435s (stride 35s >= 30s and len(buf) == 2 >= 2)
    res435 = pipe.add_record(make_rec(435))
    assert res435 is not None
    _, _, raw_vec435, _ = res435
    assert len(raw_vec435) == 12


def test_ingestion_kafka_and_timescale_sinks(tmp_path):
    """Verifies Kafka publisher and Timescale sink invocations."""
    kafka_messages = []
    timescale_rows = []

    def mock_kafka(topic, msg):
        kafka_messages.append((topic, msg))

    def mock_timescale(record):
        timescale_rows.append(record)

    pipe = IngestionPipeline(
        audit_log_path=str(tmp_path / "sink_audit.log"),
        kafka_publisher=mock_kafka,
        timeseries_sink=mock_timescale,
    )

    rec_payload = {
        "node_id": "SS-PANEL7-N042",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gps": {"lat": 23.791204, "lon": 86.433129, "elevation_m": 242.6},
        "sensors": {"tilt_deg": 0.183, "vibration_rms_mm_s": 1.42, "displacement_mm": 3.70, "crack_index": 0.02},
        "node_health": {"battery_pct": 78.0, "rssi_dbm": -71.0, "hop_count": 3},
    }

    res = pipe.process_raw_message(rec_payload)
    assert res.is_valid is True
    assert len(kafka_messages) == 1
    assert "subsense.telemetry.SS-PANEL7-N042" in kafka_messages[0][0]
    assert len(timescale_rows) == 1


def test_qos_tracker_mesh_summary():
    """Verifies mesh summary statistics and packet jitter calculations."""
    tracker = QoSTracker(nominal_interval_sec=1.0)
    now = datetime.now(timezone.utc)

    for i in range(5):
        rec1 = RawSensorRecord(
            node_id="N01",
            timestamp=now + timedelta(seconds=i),
            gps=GPSData(lat=23.79, lon=86.43, elevation_m=240.0),
            sensors=SensorData(tilt_deg=0.1, vibration_rms_mm_s=1.0, displacement_mm=1.0, crack_index=0.01),
            node_health=NodeHealthData(battery_pct=95.0, rssi_dbm=-65.0, hop_count=1),
        )
        rec2 = RawSensorRecord(
            node_id="N02",
            timestamp=now + timedelta(seconds=i * 2), # Slower interval
            gps=GPSData(lat=23.791, lon=86.431, elevation_m=240.0),
            sensors=SensorData(tilt_deg=0.1, vibration_rms_mm_s=1.0, displacement_mm=1.0, crack_index=0.01),
            node_health=NodeHealthData(battery_pct=80.0, rssi_dbm=-75.0, hop_count=2),
        )
        tracker.record_packet(rec1)
        tracker.record_packet(rec2)

    summary = tracker.get_mesh_summary()
    assert summary["active_nodes"] == 2
    assert 0.0 <= summary["mean_pdr"] <= 1.0
    assert 0.0 <= summary["mean_q_mesh"] <= 1.0


def test_forecast_deformation_endpoint(client):
    """Verifies POST /v1/forecast/deformation endpoint latency and output schema."""
    history = [[0.05 + 0.001 * i, 1.2 + 0.05 * i, 0.8] for i in range(192)]
    req = {
        "node_id": "SS-PANEL7-N042",
        "history_192x3": history,
        "horizon_hours": 48,
        "d_crit_mm": 25.0,
    }
    resp = client.post("/v1/forecast/deformation", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_id"] == "SS-PANEL7-N042"
    assert len(data["q10_trajectory"]) == 48
    assert len(data["q50_trajectory"]) == 48
    assert len(data["q90_trajectory"]) == 48
    assert data["trend_regime"] in ["STABLE", "SUSTAINED", "ACCELERATING"]
    assert data["inference_latency_ms"] <= 150.0  # Serving budget


def test_kriging_serving_endpoint(client, tmp_path):
    """Verifies POST /v1/geostatistics/interpolate endpoint."""
    tif_path = str(tmp_path / "serving_krig.tif")
    req = {
        "sensor_coords_xy": [[100.0, 100.0], [250.0, 200.0], [350.0, 400.0], [450.0, 500.0]],
        "observed_displacements_mm": [12.0, 24.0, 32.0, 28.0],
        "bounds_extent": [0.0, 500.0, 0.0, 500.0],
        "output_geotiff_path": tif_path,
    }
    resp = client.post("/v1/geostatistics/interpolate", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["recompute_time_sec"] <= 30.0
    assert "variogram_diagnostics" in data
    assert data["geotiff_path"] == tif_path


def test_gnn_mesh_risk_serving_endpoint(client):
    """Verifies POST /v1/gnn/mesh-risk endpoint."""
    N = 4
    req = {
        "node_ids": ["N01", "N02", "N03", "N04"],
        "features_12d": [[0.1] * 12 for _ in range(N)],
        "anomaly_scores": [0.15, 0.25, 0.70, 0.30],
        "coordinates_3d": [[100.0, 100.0, 0.0], [150.0, 120.0, 1.0], [200.0, 180.0, 2.0], [250.0, 220.0, 1.5]],
    }
    resp = client.post("/v1/gnn/mesh-risk", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["num_nodes"] == 4
    assert len(data["node_risk_scores"]) == 4
    for nid, score in data["node_risk_scores"].items():
        assert 0.0 <= score <= 1.0


def test_insar_divergence_serving_endpoint(client):
    """Verifies POST /v1/insar/divergence endpoint."""
    req = {
        "sensor_coords_xy": [[150.0, 150.0], [250.0, 200.0], [200.0, 300.0]],
        "observed_displacements_mm": [15.0, 22.0, 20.0],
        "divergence_threshold_mm": 8.0,
        "bounds_extent": [0.0, 600.0, 0.0, 600.0],
    }
    resp = client.post("/v1/insar/divergence", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["threshold_mm"] == 8.0
    assert "total_blind_spot_area_m2" in data
    assert isinstance(data["candidate_clusters"], list)
