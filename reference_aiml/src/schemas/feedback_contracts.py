from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any
from datetime import datetime, timezone

class OperatorFeedbackEvent(BaseModel):
    """
    Closes the loop described in Section 8.2 & Alerting System Section 9.
    Delivered via internal message queue (alert-feedback topic).
    """
    feedback_id: str = Field(..., description="Unique feedback event identifier")
    alert_id: str = Field(..., description="Referenced Risk Event / Alert ID")
    site_id: str = Field(..., description="Mine site identifier e.g. SITE-JHARIA-04")
    zone_id: str = Field(..., description="Associated risk zone identifier")
    operator_id: str = Field(..., description="Identifier of safety officer or geotechnical engineer")
    feedback_type: Literal["false_positive", "confirmed_positive", "unresolved"] = Field(...)
    geotechnical_notes: Optional[str] = Field(None, description="Observations from ground inspection team")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ModelRegistryEntry(BaseModel):
    """Model versioning, audit logging, and rollback entry (Section 8.3 & Section 12)."""
    model_name: str = Field(..., description="Name of model: anomaly_ensemble, mesh_gnn, or lstm_forecaster")
    version: str = Field(..., description="Semantic version tag e.g. cloud-ensemble-v2.1.0")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = Field(default=True)
    training_sample_count: int = Field(default=0)
    validation_metrics: Dict[str, float] = Field(default_factory=dict)
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    model_artifact_path: Optional[str] = None
