from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class TileCoordinates(BaseModel):
    z: int = Field(..., description="Zoom level (12 to 18)", ge=12, le=18)
    x: int = Field(..., description="Tile X index")
    y: int = Field(..., description="Tile Y index")

class HeatmapMetadataHeader(BaseModel):
    """Formal Data Contract 6.1: Heatmap Tile Request & Metadata Response Header"""
    site_id: str = Field(..., description="Identifier of the mine concession (e.g. PANEL7-JHARIA)")
    layer: str = Field(default="risk_deformation_heatmap", description="Layer identifier name")
    tile_coordinates: TileCoordinates = Field(..., description="XYZ tile coordinates")
    as_of: datetime = Field(..., description="ISO 8601 timestamp of data currency")
    data_currency_seconds: float = Field(..., description="Seconds elapsed since telemetry sync")
    is_stale: bool = Field(..., description="True if telemetry currency exceeds staleness SLA (30s)")
    kriging_variance_included: bool = Field(default=True, description="Whether estimation variance confidence mask is applied")

class IngestionRasterPayload(BaseModel):
    """Payload representing upstream Layer 4 Kriging surface and variance input"""
    site_id: str
    timestamp: datetime
    grid_width: int
    grid_height: int
    bounds_utm: tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    utm_epsg: int
    risk_values: list[list[float]]  # 2D continuous array [0.0, 1.0]
    variance_values: Optional[list[list[float]]] = None  # 2D variance array
    gateway_sync_age_seconds: float = 0.0
