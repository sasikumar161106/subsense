"""
SubSense Explainability Gatekeeper and Alert Schema.
Enforces non-negotiable regulatory mandate:
Zero alerts may ship without:
1. Contributing sensors (non-empty list)
2. Corroborating neighbor node IDs (non-empty list)
3. Plain-language geotechnical summary (non-empty valid structure)
"""

from datetime import datetime, timezone
from typing import Annotated, Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from fusion.schemas import AlertTier


class IncompleteExplainabilityAlertError(ValueError):
    """Raised when an alert fails the Explainability-by-Construction validation gate."""
    pass


def check_sensor_availability(
    sensor_name: str,
    sensor_availability: Optional[Dict[str, bool]],
) -> bool:
    """
    Returns False if the sensor is explicitly marked unavailable (False) in sensor_availability.
    Returns True if available (True) or if not specified.
    """
    if not sensor_availability:
        return True

    aliases = {
        "tilt_deg": ["tilt_deg", "tilt"],
        "tilt": ["tilt_deg", "tilt"],
        "vibration_rms_mm_s": ["vibration_rms_mm_s", "vibration"],
        "vibration": ["vibration_rms_mm_s", "vibration"],
        "displacement_mm": ["displacement_mm", "displacement"],
        "displacement": ["displacement_mm", "displacement"],
        "crack_index": ["crack_index", "crack"],
        "crack": ["crack_index", "crack"],
    }
    keys_to_check = aliases.get(sensor_name.lower().strip(), [sensor_name.lower().strip()])
    for k in keys_to_check:
        if k in sensor_availability and sensor_availability[k] is False:
            return False
    return True


class ValidatedAlertEvent(BaseModel):
    """
    Cryptographically tracked, validated alert publication payload.
    Strictly forbids omission of any attribution or plain-language fields.
    """
    model_config = ConfigDict(extra="forbid")

    alert_id: Annotated[str, Field(min_length=3, max_length=128)]
    node_id: Annotated[str, Field(min_length=1, max_length=64)]
    timestamp: Annotated[datetime, Field()]
    tier: AlertTier
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    contributing_sensors: Annotated[List[str], Field(min_length=1, description="Physical sensor modalities; CANNOT BE EMPTY")]
    corroborating_node_ids: Annotated[List[str], Field(min_length=1, description="Corroborating mesh nodes; CANNOT BE EMPTY")]
    plain_language_summary: Annotated[str, Field(min_length=15, description="Audited natural language geotechnical summary")]
    actions: List[str] = Field(default_factory=list)
    audit_level: int = 1
    sensor_availability: Optional[Dict[str, bool]] = Field(default=None, description="Hardware instrument availability flags")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_sensor_attribution_against_availability(self) -> "ValidatedAlertEvent":
        avail = self.sensor_availability or (self.metadata.get("sensor_availability") if isinstance(self.metadata, dict) else None)
        if avail and isinstance(avail, dict):
            for s in self.contributing_sensors:
                if not check_sensor_availability(s, avail):
                    raise IncompleteExplainabilityAlertError(
                        f"VIOLATION: Alert rejected at publish gate: Sensor '{s}' in 'contributing_sensors' is marked unavailable in sensor_availability."
                    )
        return self

    @field_validator("contributing_sensors")
    @classmethod
    def validate_contributing_sensors(cls, v: List[str]) -> List[str]:
        if not v or len(v) == 0:
            raise IncompleteExplainabilityAlertError(
                "VIOLATION: Alert rejected at publish gate: 'contributing_sensors' is missing or empty."
            )
        for s in v:
            if not isinstance(s, str) or not s.strip():
                raise IncompleteExplainabilityAlertError(
                    "VIOLATION: Alert rejected at publish gate: 'contributing_sensors' contains empty/blank strings."
                )
        return v

    @field_validator("corroborating_node_ids")
    @classmethod
    def validate_corroborating_node_ids(cls, v: List[str]) -> List[str]:
        if not v or len(v) == 0:
            raise IncompleteExplainabilityAlertError(
                "VIOLATION: Alert rejected at publish gate: 'corroborating_node_ids' is missing or empty."
            )
        for nid in v:
            if not isinstance(nid, str) or not nid.strip():
                raise IncompleteExplainabilityAlertError(
                    "VIOLATION: Alert rejected at publish gate: 'corroborating_node_ids' contains empty/blank strings."
                )
        return v

    @field_validator("plain_language_summary")
    @classmethod
    def validate_plain_language_summary(cls, v: str) -> str:
        if not v or not v.strip():
            raise IncompleteExplainabilityAlertError(
                "VIOLATION: Alert rejected at publish gate: 'plain_language_summary' is empty."
            )
        if len(v.strip()) < 15:
            raise IncompleteExplainabilityAlertError(
                "VIOLATION: Alert rejected at publish gate: 'plain_language_summary' is too short or incomplete."
            )
        return v.strip()


def validate_and_gate_alert(
    payload: Union[Dict[str, Any], ValidatedAlertEvent],
) -> ValidatedAlertEvent:
    """
    Enforced blocking validation gate before any alert is dispatched to Kafka, sirens, or DGMS logs.
    Raises IncompleteExplainabilityAlertError immediately if any required explainability field is omitted.
    """
    if isinstance(payload, dict):
        # Explicit pre-check to give clear custom error before pydantic generic error
        if not payload.get("contributing_sensors") or len(payload.get("contributing_sensors", [])) == 0:
            raise IncompleteExplainabilityAlertError(
                "GATE REJECTION: Missing or empty 'contributing_sensors'."
            )
        if not payload.get("corroborating_node_ids") or len(payload.get("corroborating_node_ids", [])) == 0:
            raise IncompleteExplainabilityAlertError(
                "GATE REJECTION: Missing or empty 'corroborating_node_ids'."
            )
        if not payload.get("plain_language_summary") or not str(payload.get("plain_language_summary", "")).strip():
            raise IncompleteExplainabilityAlertError(
                "GATE REJECTION: Missing or empty 'plain_language_summary'."
            )
        avail = payload.get("sensor_availability") or (payload.get("metadata", {}).get("sensor_availability") if isinstance(payload.get("metadata"), dict) else None)
        if avail and isinstance(avail, dict):
            for s in payload.get("contributing_sensors", []):
                if not check_sensor_availability(s, avail):
                    raise IncompleteExplainabilityAlertError(
                        f"GATE REJECTION: Sensor '{s}' in 'contributing_sensors' is marked unavailable in sensor_availability."
                    )
        try:
            event = ValidatedAlertEvent.model_validate(payload)
        except IncompleteExplainabilityAlertError:
            raise
        except Exception as e:
            raise IncompleteExplainabilityAlertError(f"GATE REJECTION: Schema validation failed: {str(e)}") from e
    else:
        event = payload
        avail = event.sensor_availability or (event.metadata.get("sensor_availability") if isinstance(event.metadata, dict) else None)
        if avail and isinstance(avail, dict):
            for s in event.contributing_sensors:
                if not check_sensor_availability(s, avail):
                    raise IncompleteExplainabilityAlertError(
                        f"GATE REJECTION: Sensor '{s}' in 'contributing_sensors' is marked unavailable in sensor_availability."
                    )

    return event
