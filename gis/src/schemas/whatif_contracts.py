from pydantic import BaseModel, Field
from typing import Literal, Any, Union
from datetime import datetime

class ProposedPanelGeometry(BaseModel):
    panel_id: str = Field(..., description="Proposed panel designator (e.g. PANEL-PROP-08)")
    site_id: str = Field(..., description="Target mine concession")
    extraction_method: Literal["longwall_caving", "bord_and_pillar_depillaring"] = "longwall_caving"
    polygon_coordinates_utm: list[list[float]]  # [ [x, y], ... ]
    seam_depth_m: float = Field(..., ge=20.0, le=1200.0)
    seam_thickness_m: float = Field(..., ge=0.5, le=25.0)
    panel_width_m: float = Field(..., ge=50.0, le=500.0)
    panel_length_m: float = Field(..., ge=100.0, le=3000.0)
    goaf_treatment: Literal["caving", "hydraulic_sand_stowing"] = "caving"

class SubsidenceSimulationResult(BaseModel):
    simulation_id: str
    panel_id: str
    site_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_simulation: bool = True
    watermark_banner: str = "NON-LIVE PREDICTIVE SIMULATION — STATUTORY WHAT-IF AUDIT"
    max_subsidence_mm: float
    max_tilt_mm_per_m: float
    max_tensile_strain_mm_per_m: float
    max_compressive_strain_mm_per_m: float
    angle_of_draw_deg: float
    affected_surface_area_sq_m: float
    surface_subsidence_grid: list[list[float]]  # 2D calculated subsidence grid (mm)
    contour_isolines_geojson: dict  # Simulated subsidence contour features
    risk_delta_comparison: dict[str, Any]  # comparison vs current baseline
