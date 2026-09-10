"""
Model output event schema for published Kafka anomaly events.
Enforces Explainability-by-Construction: contributing_sensors must NEVER be empty.
"""

from datetime import datetime
from typing import Annotated, List, Union, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class EmptyContributingSensorsError(ValueError):
    """Raised when an alert or event is emitted without sensor attribution."""
    pass


class ModelOutputEvent(BaseModel):
    """
    Formal schema for anomaly events published to the fusion engine Kafka topic.
    Strictly adheres to Section 4.3.
    """
    model_config = ConfigDict(extra="forbid")

    node_id: Annotated[str, Field(min_length=3, max_length=64, description="Node identifier")]
    window_start: Annotated[datetime, Field(description="Window start ISO timestamp")]
    window_end: Annotated[datetime, Field(description="Window end ISO timestamp")]
    anomaly_score: Annotated[float, Field(ge=0.0, le=1.0, description="Normalized score S_node in [0.0, 1.0]")]
    reconstruction_error: Annotated[float, Field(ge=0.0, description="Raw autoencoder MSE")]
    contributing_sensors: Annotated[
        List[str],
        Field(min_length=1, description="Attributing sensor channels; CANNOT BE EMPTY")
    ]
    model_signature: Annotated[str, Field(min_length=1, description="Versioned signature e.g. isoforest_ae_ensemble_v3.2.1")]
    confidence: Annotated[float, Field(ge=0.0, le=1.0, description="Calibrated confidence metric")]
    inference_latency_ms: Annotated[float, Field(ge=0.0, description="Inference execution latency in milliseconds")]

    @field_validator("contributing_sensors")
    @classmethod
    def enforce_non_empty_attribution(cls, v: List[str]) -> List[str]:
        if not v or len(v) == 0:
            raise EmptyContributingSensorsError(
                "VIOLATION: Explainability-by-Construction mandate violated! "
                "Emitted anomaly event has empty contributing_sensors."
            )
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise EmptyContributingSensorsError(
                    "VIOLATION: Empty or whitespace string found in contributing_sensors."
                )
        return v


def validate_and_serialize_event(payload: Union[Dict[str, Any], ModelOutputEvent]) -> str:
    """
    Schema-level gatekeeper before Kafka publish.
    Raises ValidationError or EmptyContributingSensorsError if invalid.
    """
    if isinstance(payload, dict):
        event = ModelOutputEvent.model_validate(payload)
    else:
        event = payload

    # Extra programmatic assertion
    if not event.contributing_sensors or len(event.contributing_sensors) == 0:
        raise EmptyContributingSensorsError("contributing_sensors cannot be empty")

    return event.model_dump_json()
