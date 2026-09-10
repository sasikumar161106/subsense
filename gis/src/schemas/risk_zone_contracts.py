from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

class CentroidGPS(BaseModel):
    lat: float
    lon: float

class RiskZoneProperties(BaseModel):
    site_id: str = Field(..., description="Concession identifier")
    zone_name: str = Field(..., description="Human-readable zone name (e.g. Goaf Abutment Zone C)")
    severity_tier: Literal["advisory", "warning", "critical", "low"] = Field(..., description="DGMS alert classification")
    time_to_critical_hours: tuple[float, float] = Field(..., description="[min_hours, max_hours] to critical threshold")
    model_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from Layer 4 ML model")
    affected_node_ids: list[str] = Field(default_factory=list, description="IDs of ground mesh sensor nodes inside/adjacent")
    primary_contributing_sensors: list[str] = Field(default_factory=list, description="Sensor channels driving alert (tilt, displacement)")
    explanation_summary: str = Field(..., description="Synthesized SHAP narrative for geotechnical inspectors")
    area_sq_meters: float = Field(..., ge=250.0, description="Surface area in square meters (cutoff >= 250m²)")
    centroid_gps: CentroidGPS = Field(..., description="Geographic centroid in WGS84")
    last_updated: datetime = Field(..., description="Timestamp of last refresh cycle")

class PolygonGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon"] = "Polygon"
    coordinates: list[list[list[float]]]  # Outer and optional inner rings [ [ [lon, lat], ... ] ]

class RiskZoneFeature(BaseModel):
    """Formal Data Contract 6.2: Risk-Zone Polygon Feature Schema (GeoJSON Output)"""
    type: Literal["Feature"] = "Feature"
    id: str = Field(..., description="Stable zone identifier (e.g. ZONE-PANEL7-C)")
    properties: RiskZoneProperties
    geometry: PolygonGeometry

class RiskZoneFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection wrapper for all active risk zones across a site"""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[RiskZoneFeature]
    as_of: datetime = Field(default_factory=datetime.utcnow)
    tenant_id: Optional[str] = None
    site_id: Optional[str] = None
