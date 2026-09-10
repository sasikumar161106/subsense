import pytest
from datetime import datetime, timezone
from src.schemas.sensor_contracts import EngineeredFeatureVector
from src.models.mesh_gnn_correlator import MeshGNNCorrelator

def create_dummy_fvec(node_id: str, is_anom: bool = False) -> EngineeredFeatureVector:
    if is_anom:
        return EngineeredFeatureVector(
            node_id=node_id,
            timestamp=datetime.now(timezone.utc),
            tilt_mean=8.0,
            tilt_rate=2.0,
            tilt_var_short=1.0,
            tilt_var_long=1.5,
            vibration_rms=0.5,
            vibration_peak_ratio=4.0,
            displacement_delta=20.0,
            displacement_cum_drift=10.0,
            crack_active_ratio=0.8,
        )
    return EngineeredFeatureVector(
        node_id=node_id,
        timestamp=datetime.now(timezone.utc),
        tilt_mean=0.5,
        tilt_rate=0.01,
        tilt_var_short=0.001,
        tilt_var_long=0.001,
        vibration_rms=0.02,
        vibration_peak_ratio=1.0,
        displacement_delta=0.1,
        displacement_cum_drift=0.2,
        crack_active_ratio=0.0,
    )

def test_gnn_build_adjacency():
    gnn = MeshGNNCorrelator(spatial_radius_m=100.0)
    node_ids = ["N-01", "N-02", "N-03"]
    node_coords = {
        "N-01": (442400.0, 2631600.0),
        "N-02": (442450.0, 2631600.0), # 50m away (connected)
        "N-03": (442900.0, 2631600.0), # 500m away (not connected)
    }
    adj_norm, graph = gnn.build_adjacency(node_ids, node_coords)

    assert adj_norm.shape == (3, 3)
    assert graph.has_edge("N-01", "N-02")
    assert not graph.has_edge("N-01", "N-03")

def test_gnn_correlates_coherent_cluster():
    gnn = MeshGNNCorrelator(spatial_radius_m=150.0)
    # Cluster of 3 adjacent anomalous nodes
    node_ids = ["N-014", "N-015", "N-021", "N-099"]
    node_coords = {
        "N-014": (442420.0, 2631650.0),
        "N-015": (442480.0, 2631680.0), # ~67m
        "N-021": (442450.0, 2631720.0), # ~76m
        "N-099": (443200.0, 2632500.0), # far away normal node
    }

    feature_map = {
        "N-014": create_dummy_fvec("N-014", is_anom=True),
        "N-015": create_dummy_fvec("N-015", is_anom=True),
        "N-021": create_dummy_fvec("N-021", is_anom=True),
        "N-099": create_dummy_fvec("N-099", is_anom=False),
    }

    anomaly_scores = {
        "N-014": 0.85,
        "N-015": 0.82,
        "N-021": 0.88,
        "N-099": 0.05,
    }

    zones = gnn.correlate(node_ids, node_coords, feature_map, anomaly_scores)
    assert len(zones) >= 1
    top_zone = zones[0]

    assert top_zone["correlation_score"] >= 0.70
    assert set(top_zone["node_ids"]).issuperset({"N-014", "N-015", "N-021"})
    assert "N-099" not in top_zone["node_ids"]
