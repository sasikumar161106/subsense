from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import date

class InSARLocation(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)

class InSARDiscrepancyMarker(BaseModel):
    """Formal Data Contract 6.3: InSAR Discrepancy Annotation Marker Schema"""
    annotation_id: str = Field(..., description="Unique discrepancy audit identifier")
    site_id: str = Field(..., description="Target mine concession identifier")
    location: InSARLocation = Field(..., description="Geographic point of anomalous geodetic basin")
    insar_acquisition_date: str = Field(..., description="Sentinel-1 satellite pass date (YYYY-MM-DD)")
    discrepancy_type: str = Field(
        ..., 
        description="Classification (e.g. satellite_motion_unmonitored_by_ground_mesh, sensor_satellite_velocity_mismatch)"
    )
    los_velocity_mm_year: float = Field(..., description="Sentinel-1 Line-of-Sight deformation velocity in mm/year")
    description: str = Field(..., description="Detailed geotechnical interpretation of the geodetic anomaly")
    recommended_action: str = Field(..., description="Actionable preventative guidance for survey/safety teams")

class InSAROverlayPayload(BaseModel):
    site_id: str
    pass_date: str
    satellite_mission: Literal["Sentinel-1A", "Sentinel-1B", "Sentinel-1C"] = "Sentinel-1A"
    heading_deg: float = 192.5  # Descending pass azimuth
    incidence_angle_deg: float = 38.2
    markers: list[InSARDiscrepancyMarker]
    hatched_polygon_geojson: dict
