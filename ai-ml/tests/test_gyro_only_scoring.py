"""
Gyro-Only Anomaly Scoring and Explainability Attribution Enforcement Tests.
Verifies Phase 2a requirements:
1. When only physical MPU6050 (gyro/accelerometer) is wired, sensor_availability marks
   tilt=True, vibration=True, displacement=False, crack=False.
2. AnomalyEnsemble filters out uninstrumented channels (displacement_mm, crack_index),
   ensuring contributing_sensors only lists available physical modalities.
3. The Explainability Gatekeeper (validate_and_gate_alert and ValidatedAlertEvent)
   strictly rejects any alert that attempts to attribute an unavailable sensor.
4. Serving endpoint /v1/score respects sensor_availability and returns compliant attributions.
"""

from datetime import datetime, timezone
import numpy as np
import pytest
from fastapi.testclient import TestClient

from features.constants import FEATURE_VECTOR_DIM
from models.anomaly.ensemble import AnomalyEnsemble
from explainability.alert_schema import (
    ValidatedAlertEvent,
    IncompleteExplainabilityAlertError,
    validate_and_gate_alert,
    check_sensor_availability,
)
from models.serving.event_schema import (
    ModelOutputEvent,
    EmptyContributingSensorsError,
    validate_and_serialize_event,
)
from models.serving.app import app
from fusion.schemas import AlertTier


@pytest.fixture
def fitted_ensemble():
    np.random.seed(42)
    baseline = np.random.normal(loc=0.0, scale=0.5, size=(300, FEATURE_VECTOR_DIM)).astype(np.float32)
    baseline[:, 11] = np.random.uniform(0.01, 0.05, size=(300,))
    ensemble = AnomalyEnsemble(alpha=0.55, beta=12.5)
    ensemble.fit(baseline, epochs=10, batch_size=32)
    return ensemble


def test_check_sensor_availability_helper():
    avail = {"tilt": True, "vibration": True, "displacement": False, "crack": False}
    assert check_sensor_availability("tilt_deg", avail) is True
    assert check_sensor_availability("tilt", avail) is True
    assert check_sensor_availability("vibration_rms_mm_s", avail) is True
    assert check_sensor_availability("vibration", avail) is True
    assert check_sensor_availability("displacement_mm", avail) is False
    assert check_sensor_availability("displacement", avail) is False
    assert check_sensor_availability("crack_index", avail) is False
    assert check_sensor_availability("crack", avail) is False
    # None should default to True
    assert check_sensor_availability("displacement_mm", None) is True


def test_gyro_only_ensemble_attribution_filtering(fitted_ensemble):
    """
    Even if displacement and crack feature dimensions have high synthetic values/errors,
    sensor_availability must filter them out so only tilt/vibration appear in contributing_sensors.
    """
    # Create anomalous vector with high values across all 12 dimensions
    anom_vec = np.full((FEATURE_VECTOR_DIM,), 5.0, dtype=np.float32)

    avail_gyro_only = {
        "tilt": True,
        "vibration": True,
        "displacement": False,
        "crack": False,
    }

    result = fitted_ensemble.predict(anom_vec, sensor_availability=avail_gyro_only)

    assert result.is_anomaly is True
    assert len(result.contributing_sensors) > 0
    # Must never attribute uninstrumented channels
    assert "displacement_mm" not in result.contributing_sensors
    assert "crack_index" not in result.contributing_sensors
    # Must attribute instrumented channels
    for s in result.contributing_sensors:
        assert s in ["tilt_deg", "vibration_rms_mm_s"]


def test_explainability_gate_rejects_unavailable_sensor():
    """
    Alert schema gatekeeper must strictly raise IncompleteExplainabilityAlertError
    if an unavailable sensor is present in contributing_sensors.
    """
    gyro_avail = {"tilt": True, "vibration": True, "displacement": False, "crack": False}

    # Violation 1: attributing displacement when displacement=False
    invalid_payload = {
        "alert_id": "ALERT-GYRO-001",
        "node_id": "SS-PANEL7-N042",
        "timestamp": datetime.now(timezone.utc),
        "tier": AlertTier.WARNING,
        "confidence": 0.88,
        "contributing_sensors": ["displacement_mm"],
        "corroborating_node_ids": ["SS-PANEL7-N041"],
        "plain_language_summary": "WARNING (Zone 3B, Panel 7): Triggered by differential displacement at Node SS-PANEL7-N042.",
        "sensor_availability": gyro_avail,
    }

    with pytest.raises(IncompleteExplainabilityAlertError) as exc_info:
        validate_and_gate_alert(invalid_payload)
    assert "unavailable" in str(exc_info.value).lower() or "gate rejection" in str(exc_info.value).lower()

    # Violation 2: attributing crack_index when crack=False
    invalid_payload_crack = dict(invalid_payload)
    invalid_payload_crack["contributing_sensors"] = ["crack_index"]
    with pytest.raises(IncompleteExplainabilityAlertError):
        validate_and_gate_alert(invalid_payload_crack)


def test_explainability_gate_accepts_compliant_gyro_only_alert():
    """
    Legitimate gyro-only alerts attributing tilt_deg or vibration_rms_mm_s must pass the gate.
    """
    gyro_avail = {"tilt": True, "vibration": True, "displacement": False, "crack": False}

    valid_payload = {
        "alert_id": "ALERT-GYRO-002",
        "node_id": "SS-PANEL7-N042",
        "timestamp": datetime.now(timezone.utc),
        "tier": AlertTier.WARNING,
        "confidence": 0.88,
        "contributing_sensors": ["tilt_deg", "vibration_rms_mm_s"],
        "corroborating_node_ids": ["SS-PANEL7-N041"],
        "plain_language_summary": "WARNING (Zone 3B, Panel 7): Triggered by tilt surge (+4.20°) and vibration surge at Node SS-PANEL7-N042.",
        "sensor_availability": gyro_avail,
    }

    event = validate_and_gate_alert(valid_payload)
    assert isinstance(event, ValidatedAlertEvent)
    assert event.contributing_sensors == ["tilt_deg", "vibration_rms_mm_s"]


def test_model_output_event_rejects_unavailable_sensor():
    """
    Kafka ModelOutputEvent must also reject unavailable sensor attributions.
    """
    gyro_avail = {"tilt": True, "vibration": True, "displacement": False, "crack": False}

    with pytest.raises(Exception) as exc_info:
        ModelOutputEvent(
            node_id="SS-PANEL7-N042",
            window_start=datetime.now(timezone.utc),
            window_end=datetime.now(timezone.utc),
            anomaly_score=0.92,
            reconstruction_error=0.45,
            contributing_sensors=["displacement_mm"],
            model_signature="isoforest_ae_ensemble_v3.2.1",
            confidence=0.88,
            inference_latency_ms=4.2,
            sensor_availability=gyro_avail,
        )
    assert "unavailable" in str(exc_info.value).lower()

    with pytest.raises(EmptyContributingSensorsError):
        validate_and_serialize_event({
            "node_id": "SS-PANEL7-N042",
            "window_start": datetime.now(timezone.utc),
            "window_end": datetime.now(timezone.utc),
            "anomaly_score": 0.92,
            "reconstruction_error": 0.45,
            "contributing_sensors": ["displacement_mm"],
            "model_signature": "isoforest_ae_ensemble_v3.2.1",
            "confidence": 0.88,
            "inference_latency_ms": 4.2,
            "sensor_availability": gyro_avail,
        })


def test_serving_score_endpoint_gyro_only():
    """
    FastAPI /v1/score endpoint test verifying end-to-end gyro-only inference.
    """
    client = TestClient(app)

    now = datetime.now(timezone.utc)
    # High anomaly 12-D vector
    feat_vec = [4.5] * FEATURE_VECTOR_DIM

    payload = {
        "node_id": "SS-PANEL7-N042",
        "window_start": now.isoformat(),
        "window_end": now.isoformat(),
        "feature_vector_12d": feat_vec,
        "sensor_availability": {
            "tilt": True,
            "vibration": True,
            "displacement": False,
            "crack": False,
        },
    }

    response = client.post("/v1/score", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["node_id"] == "SS-PANEL7-N042"
    assert data["anomaly_score"] > 0.6
    assert len(data["contributing_sensors"]) > 0
    assert "displacement_mm" not in data["contributing_sensors"]
    assert "crack_index" not in data["contributing_sensors"]
    for s in data["contributing_sensors"]:
        assert s in ["tilt_deg", "vibration_rms_mm_s"]
