import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from src.schemas.sensor_contracts import SensorReading, NodeHealthMetadata, EngineeredFeatureVector
from src.schemas.risk_event_contracts import ForecastTrendEnum
from src.ingestion.fault_filter import SensorFaultFilter
from src.ingestion.feature_extractor import FeatureExtractor
from src.ingestion.window_buffer import SlidingWindowBuffer
from src.models.mesh_gnn_correlator import MeshGNNCorrelator
from src.models.lstm_forecaster import LSTMProgressionForecaster
from src.geostats.ordinary_kriging import OrdinaryKrigingInterpolator
from src.insar.insar_cross_validator import InSARCrossValidator
from src.pipeline.inference_pipeline import InferencePipeline
from src.feedback_loop.retraining_orchestrator import RetrainingOrchestrator
from src.feedback_loop.model_registry import ModelRegistry
from src.models.anomaly_ensemble import AnomalyDetectionEnsemble

def test_pipeline_empty_mesh():
    """Pipeline should handle completely empty telemetry gracefully without crashing."""
    pipeline = InferencePipeline()
    results = pipeline.run_inference_cycle(
        site_id="SITE-EMPTY",
        node_readings_map={},
        node_health_map={},
        node_coords_utm={},
        bounds_utm=(442000.0, 2631200.0, 443000.0, 2632200.0),
    )
    assert results["risk_events"] == []
    assert results["node_count_analyzed"] == 0
    assert results["quarantined_nodes"] == {}
    assert results["sla_passed"] is True
    assert results["raster_payload"] is not None

def test_pipeline_all_nodes_quarantined():
    """If all nodes have faults (e.g. low battery), pipeline should quarantine all and not trigger false alerts."""
    now = datetime.now(timezone.utc)
    pipeline = InferencePipeline()

    node_readings = {
        "N-BAD1": [SensorReading(node_id="N-BAD1", timestamp=now, tilt_deg=0.5, vibration_g=0.02, displacement_mm=1.0, crack_sensor_active=False) for _ in range(20)],
        "N-BAD2": [SensorReading(node_id="N-BAD2", timestamp=now, tilt_deg=0.5, vibration_g=0.02, displacement_mm=1.0, crack_sensor_active=False) for _ in range(20)],
    }
    node_health = {
        "N-BAD1": NodeHealthMetadata(node_id="N-BAD1", timestamp=now, battery_voltage=1.9, rssi_dbm=-75.0), # Low battery
        "N-BAD2": NodeHealthMetadata(node_id="N-BAD2", timestamp=now, battery_voltage=3.3, rssi_dbm=-125.0), # Severe RSSI loss
    }
    node_coords = {
        "N-BAD1": (442400.0, 2631600.0),
        "N-BAD2": (442450.0, 2631650.0),
    }

    results = pipeline.run_inference_cycle(
        site_id="SITE-ALL-BAD",
        node_readings_map=node_readings,
        node_health_map=node_health,
        node_coords_utm=node_coords,
        bounds_utm=(442000.0, 2631200.0, 443000.0, 2632200.0),
    )

    assert results["risk_events"] == []
    assert results["node_count_analyzed"] == 0
    assert len(results["quarantined_nodes"]) == 2
    assert "N-BAD1" in results["quarantined_nodes"]
    assert "N-BAD2" in results["quarantined_nodes"]

def test_kriging_collinear_and_duplicate_coords():
    """Kriging should remain numerically stable with collinear or identical coordinates using pinv."""
    interpolator = OrdinaryKrigingInterpolator(grid_resolution_m=30.0)

    # Identical coordinates for 2 nodes
    node_coords = {
        "N-01": (442400.0, 2631600.0),
        "N-02": (442400.0, 2631600.0), # duplicate
        "N-03": (442450.0, 2631600.0), # collinear on Y=2631600
    }
    node_values = {
        "N-01": 0.8,
        "N-02": 0.82,
        "N-03": 0.75,
    }
    bounds = (442300.0, 2631500.0, 442600.0, 2631700.0)

    payload = interpolator.interpolate_raster(
        site_id="SITE-COLLINEAR",
        node_coords=node_coords,
        node_values=node_values,
        bounds_utm=bounds,
    )

    risk_arr = np.array(payload.risk_values)
    var_arr = np.array(payload.variance_values)

    assert not np.any(np.isnan(risk_arr))
    assert not np.any(np.isinf(risk_arr))
    assert not np.any(np.isnan(var_arr))
    assert not np.any(np.isinf(var_arr))
    assert np.all(risk_arr >= 0.0)
    assert np.all(risk_arr <= 1.0)

def test_gnn_isolated_nodes_discounting():
    """GNN should heavily discount isolated nodes spaced far apart (> 200m)."""
    gnn = MeshGNNCorrelator(spatial_radius_m=100.0)

    node_ids = ["N-ISO-1", "N-ISO-2", "N-ISO-3"]
    # Nodes are 1 km apart: no graph edges
    node_coords = {
        "N-ISO-1": (441000.0, 2630000.0),
        "N-ISO-2": (442000.0, 2631000.0),
        "N-ISO-3": (443000.0, 2632000.0),
    }
    now = datetime.now(timezone.utc)
    feature_map = {
        nid: EngineeredFeatureVector(
            node_id=nid,
            timestamp=now,
            tilt_mean=5.0,
            tilt_rate=1.0,
            tilt_var_short=0.5,
            tilt_var_long=0.5,
            vibration_rms=0.2,
            vibration_peak_ratio=2.0,
            displacement_delta=10.0,
            displacement_cum_drift=5.0,
            crack_active_ratio=0.0,
        ) for nid in node_ids
    }
    anomaly_scores = {"N-ISO-1": 0.85, "N-ISO-2": 0.1, "N-ISO-3": 0.1}

    zones = gnn.correlate(node_ids, node_coords, feature_map, anomaly_scores)
    # N-ISO-1 is isolated without neighbors, so its cluster_size is 1 and correlation score is heavily discounted
    if zones:
        for z in zones:
            if "N-ISO-1" in z["node_ids"]:
                assert z["cluster_size"] == 1
                assert z["correlation_score"] < 0.55  # Discounted below alert threshold

def test_lstm_heave_negative_velocity():
    """LSTM forecaster should handle negative displacement (rebound/heave) as STABLE with null TTC."""
    forecaster = LSTMProgressionForecaster(critical_displacement_mm=40.0)

    # 20 timesteps of decreasing displacement (heave/rebound)
    t = np.arange(20, dtype=np.float32)
    tilts = np.full(20, 0.5, dtype=np.float32)
    vibes = np.full(20, 0.02, dtype=np.float32)
    disps = 5.0 - 0.1 * t  # decreasing
    anoms = np.full(20, 0.2, dtype=np.float32)
    temporal_matrix = np.column_stack([tilts, vibes, disps, anoms])

    trend, ttc, metrics = forecaster.forecast_zone(
        temporal_features=temporal_matrix,
        current_displacement_mm=float(disps[-1]),
    )

    assert trend == ForecastTrendEnum.STABLE
    assert ttc is None

def test_retraining_empty_feedback_events():
    """Retraining orchestrator should handle empty feedback list gracefully without crashing."""
    registry = ModelRegistry()
    ensemble = AnomalyDetectionEnsemble()
    orchestrator = RetrainingOrchestrator(registry=registry, ensemble=ensemble)

    result = orchestrator.trigger_retraining(feedback_events=[])
    assert result["status"] == "completed"
    assert result["promoted"] is True
    assert result["metrics"]["false_positives_incorporated"] == 0
    assert result["metrics"]["confirmed_positives_incorporated"] == 0
