"""
Per-Node Anomaly Engine and Retraining Test Suite.
Verifies IsoForest + Conv1D-AE composite scoring, score bounds in [0.0, 1.0],
Explainability-by-Construction attribution, GPS relocation trigger,
and end-to-end scheduled weekly retrain audit logging.
"""

from pathlib import Path
import numpy as np
import pytest

from features.constants import FEATURE_VECTOR_DIM
from models.anomaly.isoforest import MineIsolationForest
from models.anomaly.autoencoder import MineAutoencoder
from models.anomaly.ensemble import AnomalyEnsemble
from models.anomaly.relocation import GPSRelocationDetector
from models.anomaly.retrain import ModelRetrainer


@pytest.fixture
def baseline_data():
    np.random.seed(42)
    # 300 normal baseline samples
    X = np.random.normal(loc=0.0, scale=0.5, size=(300, FEATURE_VECTOR_DIM)).astype(np.float32)
    X[:, 11] = np.random.uniform(0.01, 0.04, size=(300,))
    return X


def test_isolation_forest_scoring(baseline_data):
    """Tests Isolation Forest normalization and score bounds [0.0, 1.0]."""
    iso = MineIsolationForest(n_estimators=100, max_samples=0.75)
    iso.fit(baseline_data)

    # Normal sample
    norm_sample = np.zeros((FEATURE_VECTOR_DIM,), dtype=np.float32)
    s_norm = iso.score(norm_sample)
    assert 0.0 <= s_norm <= 1.0
    assert s_norm < 0.40  # Normal sample should have low anomaly score

    # Anomalous sample
    anom_sample = np.full((FEATURE_VECTOR_DIM,), 5.0, dtype=np.float32)
    s_anom = iso.score(anom_sample)
    assert 0.0 <= s_anom <= 1.0
    assert s_anom > s_norm


def test_autoencoder_reconstruction(baseline_data):
    """Tests 1D-Conv Autoencoder training, MSE computation, and error attribution."""
    ae = MineAutoencoder(latent_dim=4)
    loss = ae.train_baseline(baseline_data, epochs=15, batch_size=32)
    assert loss >= 0.0

    # Evaluate single vector
    test_vec = np.zeros((FEATURE_VECTOR_DIM,), dtype=np.float32)
    overall_mse, per_feat_mse = ae.evaluate(test_vec)
    assert overall_mse >= 0.0
    assert len(per_feat_mse) == FEATURE_VECTOR_DIM


def test_ensemble_composite_score_bounds_and_attribution(baseline_data):
    """
    Asserts:
    1. Composite score S_node in [0.0, 1.0] for all inputs.
    2. contributing_sensors is NEVER empty (Explainability-by-Construction).
    """
    ensemble = AnomalyEnsemble(alpha=0.55, beta=12.5)
    ensemble.fit(baseline_data, epochs=10, batch_size=32)

    # Test range of 50 varied test vectors (normal, noisy, extreme anomalies)
    np.random.seed(123)
    test_matrix = np.random.normal(loc=1.0, scale=3.0, size=(50, FEATURE_VECTOR_DIM)).astype(np.float32)

    for i in range(len(test_matrix)):
        vec = test_matrix[i]
        res = ensemble.predict(vec)

        assert 0.0 <= res.anomaly_score <= 1.0, f"Score {res.anomaly_score} out of [0, 1]"
        assert 0.0 <= res.isoforest_score <= 1.0
        assert 0.0 <= res.ae_score_component <= 1.0
        assert res.reconstruction_error >= 0.0

        # MANDATORY: Attribution must never be empty
        assert len(res.contributing_sensors) > 0, "contributing_sensors was empty!"
        assert any(s in ["tilt_deg", "displacement_mm", "vibration_rms_mm_s", "crack_index"] for s in res.contributing_sensors)


def test_gps_relocation_detector():
    """Verifies that centroid drift beyond threshold flags physical relocation."""
    detector = GPSRelocationDetector(threshold_m=15.0)
    node_id = "SS-PANEL7-N042"
    base_lat, base_lon = 23.791204, 86.433129

    # First observation initializes baseline
    st1 = detector.check_position(node_id, base_lat, base_lon)
    assert st1.is_relocated is False
    assert st1.drift_distance_m == 0.0

    # Minor GPS jitter: ~5 meters drift (below 15m threshold)
    # 0.000045 deg lat ~ 5m
    st2 = detector.check_position(node_id, base_lat + 0.000045, base_lon)
    assert st2.is_relocated is False
    assert st2.drift_distance_m < 15.0

    # Physical relocation: ~35 meters drift (> 15m threshold)
    # 0.000300 deg lat ~ 33m
    st3 = detector.check_position(node_id, base_lat + 0.000300, base_lon)
    assert st3.is_relocated is True
    assert st3.drift_distance_m > 15.0


def test_end_to_end_retrain_service(tmp_path, baseline_data):
    """
    Verifies that scheduled weekly retrain runs end-to-end,
    logs inspectable before/after score distributions, and handles relocation.
    """
    audit_file = tmp_path / "retrain_audit.jsonl"
    ensemble = AnomalyEnsemble()
    ensemble.fit(baseline_data, epochs=5, batch_size=32)

    retrainer = ModelRetrainer(
        ensemble=ensemble,
        audit_log_path=str(audit_file),
    )

    # 1. Run scheduled weekly retrain
    val_set = baseline_data[:100]
    report = retrainer.run_retrain(
        X_train_baseline=baseline_data,
        X_val=val_set,
        trigger_type="WEEKLY_SCHEDULED",
        epochs=5,
    )

    assert report.status == "SUCCESS"
    assert report.trigger_type == "WEEKLY_SCHEDULED"
    assert report.before_distribution.sample_count == len(val_set)
    assert report.after_distribution.sample_count == len(val_set)
    assert 0.0 <= report.before_distribution.mean <= 1.0
    assert 0.0 <= report.after_distribution.mean <= 1.0
    assert audit_file.exists()

    # 2. Test instant retrain on node relocation
    node_id = "SS-PANEL7-N042"
    retrainer.relocation_detector.set_baseline(node_id, 23.791204, 86.433129)
    # Move node by 50m
    reloc_report = retrainer.handle_node_telemetry_relocation(
        node_id=node_id,
        lat=23.791700, # ~55m north
        lon=86.433129,
        X_train_baseline=baseline_data,
        X_val=val_set,
    )
    assert reloc_report is not None
    assert reloc_report.trigger_type == "INSTANT_RELOCATION"
    assert reloc_report.node_id == node_id
