import pytest
import numpy as np
from datetime import datetime, timezone
from src.schemas.sensor_contracts import EngineeredFeatureVector
from src.models.isolation_forest_detector import IsolationForestAnomalyDetector
from src.models.autoencoder_detector import PyTorchAutoencoderDetector
from src.models.anomaly_ensemble import AnomalyDetectionEnsemble

@pytest.fixture
def normal_training_data():
    np.random.seed(42)
    # Normal background features: 100 samples of 8 dimensions around 0.5
    return np.random.normal(loc=0.5, scale=0.1, size=(100, 8))

def test_isolation_forest(normal_training_data):
    detector = IsolationForestAnomalyDetector(n_estimators=50, random_state=42)
    detector.fit(normal_training_data)
    assert detector.is_fitted

    # Normal sample (drawn from center of distribution)
    normal_sample = np.array([[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]])
    normal_score = detector.predict_anomaly_score(normal_sample)[0]

    # Extreme anomalous sample
    anom_sample = np.array([[15.0, 5.0, 4.0, 3.0, 2.5, 8.0, 50.0, 20.0]])
    anom_score = detector.predict_anomaly_score(anom_sample)[0]

    assert 0.0 <= normal_score <= 1.0
    assert 0.0 <= anom_score <= 1.0
    assert anom_score > normal_score
    assert normal_score < 0.5
    assert anom_score > 0.6

def test_pytorch_autoencoder(normal_training_data):
    ae = PyTorchAutoencoderDetector(input_dim=8, latent_dim=2, epochs=15)
    ae.fit(normal_training_data)
    assert ae.is_fitted

    normal_sample = np.array([[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]])
    normal_score = ae.predict_anomaly_score(normal_sample)[0]

    anom_sample = np.array([[12.0, 4.0, 3.0, 2.0, 2.0, 6.0, 45.0, 15.0]])
    anom_score = ae.predict_anomaly_score(anom_sample)[0]

    assert 0.0 <= normal_score <= 1.0
    assert 0.0 <= anom_score <= 1.0
    assert anom_score > normal_score

def test_anomaly_ensemble(normal_training_data):
    ensemble = AnomalyDetectionEnsemble()
    ensemble.fit(normal_training_data)

    fvec_normal = EngineeredFeatureVector(
        node_id="N-NORMAL",
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

    fvec_anom = EngineeredFeatureVector(
        node_id="N-ANOM",
        timestamp=datetime.now(timezone.utc),
        tilt_mean=14.0,
        tilt_rate=4.5,
        tilt_var_short=2.5,
        tilt_var_long=3.0,
        vibration_rms=1.8,
        vibration_peak_ratio=7.0,
        displacement_delta=35.0,
        displacement_cum_drift=18.0,
        crack_active_ratio=1.0,
    )

    ens_norm, if_norm, ae_norm, agr_norm = ensemble.score_vector(fvec_normal)
    ens_anom, if_anom, ae_anom, agr_anom = ensemble.score_vector(fvec_anom)

    assert 0.0 <= ens_norm <= 1.0
    assert 0.0 <= ens_anom <= 1.0
    assert ens_anom > ens_norm
    assert 0.0 <= agr_anom <= 1.0
