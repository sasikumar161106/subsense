from pydantic import BaseModel, Field
from typing import Optional, List, Tuple, Literal
from datetime import datetime, timezone

class IngestionRasterPayload(BaseModel):
    """
    Direct interoperability contract with GIS Layer 5 (heatmap_contracts.py).
    Transfers 2D continuous Kriging risk estimates and estimation variance confidence mask.
    """
    site_id: str = Field(..., description="Identifier of the mine concession (e.g. SITE-JHARIA-04)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="ISO 8601 timestamp")
    grid_width: int = Field(..., description="Number of grid columns in raster")
    grid_height: int = Field(..., description="Number of grid rows in raster")
    bounds_utm: Tuple[float, float, float, float] = Field(..., description="[min_x, min_y, max_x, max_y] in UTM meters")
    utm_epsg: int = Field(..., description="EPSG code of UTM projection, e.g. 32645")
    risk_values: List[List[float]] = Field(..., description="2D continuous array [0.0, 1.0]")
    variance_values: Optional[List[List[float]]] = Field(None, description="2D Kriging estimation variance array")
    gateway_sync_age_seconds: float = Field(default=0.0, description="Age of telemetry in seconds")

class CentroidGPS(BaseModel):
    lat: float
    lon: float

class RiskZoneProperties(BaseModel):
    site_id: str
    zone_name: str
    severity_tier: Literal["advisory", "warning", "critical", "low"]
    time_to_critical_hours: Tuple[float, float]
    model_confidence: float
    affected_node_ids: List[str] = Field(default_factory=list)
    primary_contributing_sensors: List[str] = Field(default_factory=list)
    explanation_summary: str
    area_sq_meters: float
    centroid_gps: CentroidGPS
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PolygonGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon"] = "Polygon"
    coordinates: List[List[List[float]]]

class RiskZoneFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    properties: RiskZoneProperties
    geometry: PolygonGeometry

class RiskZoneFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[RiskZoneFeature] = Field(default_factory=list)
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tenant_id: Optional[str] = None
    site_id: Optional[str] = None
