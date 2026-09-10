import pytest
from datetime import datetime, timezone
from src.schemas.feedback_contracts import OperatorFeedbackEvent
from src.feedback_loop.online_calibrator import OnlineCalibrator
from src.feedback_loop.feedback_consumer import FeedbackConsumer
from src.feedback_loop.model_registry import ModelRegistry
from src.feedback_loop.retraining_orchestrator import RetrainingOrchestrator
from src.models.anomaly_ensemble import AnomalyDetectionEnsemble

def test_online_calibrator_nudge():
    calibrator = OnlineCalibrator(base_anomaly_threshold=0.60)

    # Initial threshold
    t0 = calibrator.get_effective_threshold("SITE-01")
    assert t0 == 0.60

    # Operator flags false alarm -> threshold nudged up (less sensitive)
    t1 = calibrator.record_feedback("SITE-01", "false_positive")
    assert t1 > t0

    # Operator confirms true positive -> threshold nudged down (more sensitive)
    t2 = calibrator.record_feedback("SITE-01", "confirmed_positive")
    assert t2 < t1

def test_retraining_and_model_registry():
    registry = ModelRegistry()
    ensemble = AnomalyDetectionEnsemble()
    orchestrator = RetrainingOrchestrator(registry=registry, ensemble=ensemble)

    feedback_events = [
        OperatorFeedbackEvent(
            feedback_id=f"FB-{i}",
            alert_id=f"ALT-{i}",
            site_id="SITE-JHARIA-04",
            zone_id="PANEL-7-NE",
            operator_id="OP-SAFETY-01",
            feedback_type="confirmed_positive" if i % 2 == 0 else "false_positive",
            timestamp=datetime.now(timezone.utc),
        ) for i in range(10)
    ]

    retrain_res = orchestrator.trigger_retraining(feedback_events)
    assert retrain_res["status"] == "completed"
    assert retrain_res["promoted"] is True
    new_version = retrain_res["new_active_version"]

    active_versions = registry.get_active_versions()
    assert active_versions["anomaly"] == new_version

    # Test rollback
    success = registry.rollback("anomaly", "cloud-ensemble-v2.1.0")
    assert success
    assert registry.get_active_versions()["anomaly"] == "cloud-ensemble-v2.1.0"
