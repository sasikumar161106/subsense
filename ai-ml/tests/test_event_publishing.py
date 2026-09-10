"""
Model Output Event Schema and DGMS Audit Logging Test Suite.
Includes failing assertion test proving that events with empty contributing_sensors
are strictly rejected by schema-level validation before Kafka publish.
"""

from datetime import datetime, timezone
import json
import pytest
from pydantic import ValidationError

from models.serving.event_schema import (
    ModelOutputEvent,
    EmptyContributingSensorsError,
    validate_and_serialize_event,
)
from models.serving.structured_logger import DGMSAuditLogger


def test_valid_model_output_event():
    """Verifies that a complete, well-formed model output event validates and serializes."""
    now = datetime(2026, 9, 9, 4, 15, 0, tzinfo=timezone.utc)
    event_data = {
        "node_id": "SS-PANEL7-N042",
        "window_start": datetime(2026, 9, 9, 4, 10, 0, tzinfo=timezone.utc),
        "window_end": now,
        "anomaly_score": 0.86,
        "reconstruction_error": 0.0412,
        "contributing_sensors": ["tilt_deg", "displacement_mm"],
        "model_signature": "isoforest_ae_ensemble_v3.2.1",
        "confidence": 0.79,
        "inference_latency_ms": 14.2,
    }

    serialized = validate_and_serialize_event(event_data)
    parsed = json.loads(serialized)
    assert parsed["node_id"] == "SS-PANEL7-N042"
    assert parsed["anomaly_score"] == 0.86
    assert parsed["contributing_sensors"] == ["tilt_deg", "displacement_mm"]


def test_rejection_of_empty_contributing_sensors():
    """
    CRITICAL MANDATE:
    Failing test proving enforcement strictly rejects any event with empty contributing_sensors.
    An unattributed alert violates Explainability-by-Construction outright.
    """
    now = datetime(2026, 9, 9, 4, 15, 0, tzinfo=timezone.utc)

    # 1. Test with empty list
    bad_event_empty_list = {
        "node_id": "SS-PANEL7-N042",
        "window_start": datetime(2026, 9, 9, 4, 10, 0, tzinfo=timezone.utc),
        "window_end": now,
        "anomaly_score": 0.86,
        "reconstruction_error": 0.0412,
        "contributing_sensors": [],  # EMPTY ATTRIBUTION!
        "model_signature": "isoforest_ae_ensemble_v3.2.1",
        "confidence": 0.79,
        "inference_latency_ms": 14.2,
    }

    with pytest.raises((ValidationError, EmptyContributingSensorsError)) as exc_info:
        validate_and_serialize_event(bad_event_empty_list)

    assert "contributing_sensors" in str(exc_info.value).lower()

    # 2. Test with whitespace/blank sensor name
    bad_event_blank_string = {
        "node_id": "SS-PANEL7-N042",
        "window_start": datetime(2026, 9, 9, 4, 10, 0, tzinfo=timezone.utc),
        "window_end": now,
        "anomaly_score": 0.86,
        "reconstruction_error": 0.0412,
        "contributing_sensors": ["   "],  # Blank whitespace!
        "model_signature": "isoforest_ae_ensemble_v3.2.1",
        "confidence": 0.79,
        "inference_latency_ms": 14.2,
    }

    with pytest.raises((ValidationError, EmptyContributingSensorsError)):
        validate_and_serialize_event(bad_event_blank_string)


def test_dgms_evidentiary_audit_trail(tmp_path):
    """
    Verifies that every inference call is logged with complete input vector,
    scores, and attributions to an immutable evidentiary trail.
    """
    log_file = tmp_path / "dgms_audit_test.jsonl"
    logger = DGMSAuditLogger(log_file_path=str(log_file))

    now = datetime.now(timezone.utc)
    vec_12d = [0.15, 0.02, 1.2, 4.5, 30.0, 3.0, 0.05, 2.25, 45.0, 50.0, 0.25, 0.035]

    logger.log_inference(
        node_id="SS-PANEL7-N042",
        timestamp=now,
        input_vector_12d=vec_12d,
        anomaly_score=0.86,
        reconstruction_error=0.0412,
        contributing_sensors=["tilt_deg", "displacement_mm"],
        confidence=0.79,
        inference_latency_ms=14.2,
        model_signature="isoforest_ae_ensemble_v3.2.1",
    )

    assert log_file.exists()
    with open(log_file, "r", encoding="utf-8") as f:
        line = f.readline()
        record = json.loads(line)

    assert record["node_id"] == "SS-PANEL7-N042"
    assert len(record["input_vector_12d"]) == 12
    assert record["anomaly_score"] == 0.86
    assert record["contributing_sensors"] == ["tilt_deg", "displacement_mm"]
    assert record["model_signature"] == "isoforest_ae_ensemble_v3.2.1"
