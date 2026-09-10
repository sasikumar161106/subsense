from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Any

class InSARLocation(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)

class InSARDiscrepancyMarker(BaseModel):
    """Direct interoperability with GIS Layer 5 Section 6.3 InSAR Discrepancy Annotation Marker."""
    annotation_id: str = Field(..., description="Unique discrepancy audit identifier")
    site_id: str = Field(..., description="Target mine concession identifier")
    location: InSARLocation = Field(..., description="Geographic point of anomalous geodetic basin")
    insar_acquisition_date: str = Field(..., description="Sentinel-1 satellite pass date (YYYY-MM-DD)")
    discrepancy_type: str = Field(
        ...,
        description="Classification: satellite_motion_unmonitored_by_ground_mesh or sensor_satellite_velocity_mismatch"
    )
    los_velocity_mm_year: float = Field(..., description="Sentinel-1 Line-of-Sight deformation velocity in mm/year")
    description: str = Field(..., description="Geotechnical interpretation of geodetic anomaly")
    recommended_action: str = Field(..., description="Actionable guidance for survey/safety teams")

class InSAROverlayPayload(BaseModel):
    site_id: str
    pass_date: str
    satellite_mission: Literal["Sentinel-1A", "Sentinel-1B", "Sentinel-1C"] = "Sentinel-1A"
    heading_deg: float = 192.5
    incidence_angle_deg: float = 38.2
    markers: List[InSARDiscrepancyMarker] = Field(default_factory=list)
    hatched_polygon_geojson: Dict[str, Any] = Field(default_factory=dict)
