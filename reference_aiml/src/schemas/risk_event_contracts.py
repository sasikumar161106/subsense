from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Optional
from enum import Enum

class ForecastTrendEnum(str, Enum):
    STABLE = "stable"
    SLOW_PROGRESSION = "slow_progression"
    ACCELERATING = "accelerating"
    SUDDEN_ONSET = "sudden_onset"

class ModelVersionMetadata(BaseModel):
    """Traceability metadata recording exact model versions generating the inference."""
    anomaly: str = Field(default="cloud-ensemble-v2.1.0", description="Anomaly detection ensemble version")
    correlation: str = Field(default="gnn-corr-v1.4.0", description="Graph Neural Network correlator version")
    forecast: str = Field(default="lstm-forecast-v1.2.0", description="LSTM progression forecasting version")

class RiskEvent(BaseModel):
    """
    Formal Output Artifact (Section 10) of the SubSense AI/ML Data Inference Layer.
    Consumed by GIS/Digital Twin (Step 5) and Alerting System (Step 6).
    """
    site_id: str = Field(..., description="Unique mine site concession identifier, e.g. SITE-JHARIA-04")
    zone_id: str = Field(..., description="Identified risk zone identifier, e.g. PANEL-7-NE")
    node_ids: List[str] = Field(..., description="List of physical sensor nodes participating in the correlated event")
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Ensemble anomaly score [0.0, 1.0]")
    correlation_score: float = Field(..., ge=0.0, le=1.0, description="Spatial GNN correlation score [0.0, 1.0]")
    forecast_trend: ForecastTrendEnum = Field(..., description="LSTM trend: stable, slow_progression, accelerating, sudden_onset")
    time_to_critical_hours: Optional[float] = Field(None, description="Estimated hours remaining to critical deformation, or null if stable")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Machine-derived confidence score [0.0, 1.0]")
    contributing_sensors: List[str] = Field(..., description="Sensor channels driving alert, e.g. ['tilt', 'vibration', 'crack']")
    explanation_text: str = Field(..., description="Non-hallucinated, auditable natural language explanation")
    model_versions: ModelVersionMetadata = Field(default_factory=ModelVersionMetadata)
    event_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="ISO 8601 UTC timestamp of inference")
