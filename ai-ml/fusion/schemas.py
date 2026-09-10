"""
Formal Pydantic schemas and enums for SubSense Multi-Source Evidence Fusion Engine.
Enforces safety-critical type integrity and strict schema validation across all 10 signal streams.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class AlertTier(str, Enum):
    NONE = "NONE"
    ADVISORY = "ADVISORY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class FusionInputSignals(BaseModel):
    """
    Unified 10-signal input data structure fed into the Multi-Source Evidence Fusion Engine.
    All fields map strictly to verified outputs from Phase 1 and Phase 2.
    """
    model_config = ConfigDict(extra="forbid")

    node_id: Annotated[str, Field(min_length=1, max_length=64, description="Primary sensor node identifier")]
    timestamp: Annotated[datetime, Field(description="Event timestamp in UTC")]
    zone_id: Annotated[str, Field(default="Zone 3B", description="Geotechnical mine zone identifier")]
    panel_id: Annotated[str, Field(default="Panel 7", description="Active extraction panel identifier")]

    # Phase 1 Signals
    s_node: Annotated[float, Field(ge=0.0, le=1.0, description="Composite anomaly score S_node from AnomalyEnsemble")]
    isoforest_score: Annotated[float, Field(ge=0.0, le=1.0, description="Normalized Isolation Forest score S_IF")]
    ae_reconstruction_error: Annotated[float, Field(ge=0.0, description="Raw autoencoder MSE")]
    concordant_channel_count: Annotated[int, Field(ge=0, description="Number of concordant sensor channels within-node")]
    is_single_sensor_uncorroborated: Annotated[bool, Field(description="True if only 1 physical channel flagged without mesh corroboration")]
    c_corr: Annotated[float, Field(ge=0.0, le=1.0, description="Spatial-temporal cross-correlation coefficient C_corr")]
    c_corr_distance_m: Annotated[float, Field(ge=0.0, description="Distance to nearest corroborating neighbor in meters")]
    q_mesh: Annotated[float, Field(ge=0.0, le=1.0, description="Telemetry mesh quality score Q_mesh from QoSTracker")]
    instantaneous_delta_disp_mm: Annotated[float, Field(description="Instantaneous differential displacement in mm")]
    instantaneous_tilt_surge_deg: Annotated[float, Field(default=0.0, description="Instantaneous tilt surge in degrees")]
    contributing_sensors: Annotated[List[str], Field(min_length=1, description="Physical sensor channels attributing the trigger; CANNOT BE EMPTY")]

    # Phase 2 Signals
    r_gnn: Annotated[float, Field(ge=0.0, le=1.0, description="Spatial fracture risk score R_GNN from SubSenseGATv2")]
    lstm_regime: Annotated[str, Field(description="Deformation progression regime: STABLE, SUSTAINED, or ACCELERATING")]
    lstm_velocity_mm_h: Annotated[float, Field(default=0.0, description="Deformation velocity dy/dt from LSTM trajectory")]
    lstm_accel_mm_h2: Annotated[float, Field(default=0.0, description="Deformation acceleration d2y/dt2 from LSTM trajectory")]
    ttc_median_hours: Annotated[Optional[float], Field(default=None, description="Median time-to-critical countdown in hours")]
    gat_neighbor_attentions: Annotated[Dict[str, float], Field(default_factory=dict, description="Attention weights alpha_ij to neighbor nodes")]
    corroborating_node_ids: Annotated[List[str], Field(default_factory=list, description="Neighbor node IDs corroborating the physical movement")]
    insar_displacement_mm: Annotated[Optional[float], Field(default=None, description="InSAR satellite vertical subsidence observation if available")]

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class EvidenceAttribution(BaseModel):
    """
    Detailed audit explanation of which boolean conditions fired within the decision engine.
    """
    model_config = ConfigDict(extra="forbid")

    tier: AlertTier
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    triggered_rules: List[str]
    rule_evidence: Dict[str, Any]
    contributing_sensors: List[str]
    corroborating_node_ids: List[str]
    plain_language_summary: str


class FusionDecisionResult(BaseModel):
    """
    Final decision output emitted by the Fusion Engine.
    Directly drives sirens, conveyor cutoff, Telegram/SMS dispatch, and DGMS audit logs.
    """
    model_config = ConfigDict(extra="forbid")

    node_id: str
    timestamp: datetime
    tier: AlertTier
    confidence: float
    audit_level: int
    actions: List[str]
    evidence_attribution: EvidenceAttribution
    plain_language_summary: str
    published_payload: Optional[Dict[str, Any]] = None
