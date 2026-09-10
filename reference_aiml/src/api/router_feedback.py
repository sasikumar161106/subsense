from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
from pydantic import BaseModel

from src.schemas.feedback_contracts import OperatorFeedbackEvent, ModelRegistryEntry
from src.api.router_inference import get_shared_pipeline
from src.feedback_loop.feedback_consumer import FeedbackConsumer
from src.feedback_loop.retraining_orchestrator import RetrainingOrchestrator

router = APIRouter(prefix="/api/v1/feedback", tags=["Feedback Loop & Model Lifecycle (Section 8)"])

pipeline = get_shared_pipeline()
orchestrator = RetrainingOrchestrator(registry=pipeline.registry, ensemble=pipeline.ensemble)
consumer = FeedbackConsumer(
    calibrator=pipeline.calibrator,
    retrain_trigger_count=30,
    on_retrain_callback=lambda events: orchestrator.trigger_retraining(events),
)

class RollbackRequest(BaseModel):
    model_family: str  # "anomaly", "correlation", "forecast"
    target_version: str

@router.post("/submit")
async def submit_operator_feedback(event: OperatorFeedbackEvent):
    """
    Consumes operator feedback (false alarm / confirmed positive) from the Alerting System.
    Applies immediate short-term calibration and queues examples for retraining.
    """
    result = consumer.consume_event(event)
    return result

@router.post("/retrain/trigger")
async def trigger_manual_retrain():
    """Triggers an on-demand retraining cycle using accumulated feedback."""
    events = consumer.get_buffered_events()
    result = orchestrator.trigger_retraining(events)
    consumer.clear_buffer()
    return result

@router.get("/models/registry", response_model=List[ModelRegistryEntry])
async def list_model_registry():
    """Lists all registered model versions and active status for auditability."""
    return pipeline.registry.list_history()

@router.post("/models/rollback")
async def rollback_model_version(request: RollbackRequest):
    """Rolls back an active model family to an earlier validated version."""
    success = pipeline.registry.rollback(request.model_family, request.target_version)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Version '{request.target_version}' for family '{request.model_family}' not found in registry."
        )
    return {
        "status": "success",
        "message": f"Rolled back {request.model_family} to {request.target_version}",
        "active_versions": pipeline.registry.get_active_versions(),
    }
