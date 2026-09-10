from pydantic import BaseModel, Field
from typing import Literal, Optional

class MeshElement(BaseModel):
    id: str
    element_type: Literal["gallery", "pillar", "goaf_void", "overburden_strata", "shaft"]
    geometry_type: Literal["box", "cylinder", "extruded_polygon", "mesh"]
    coordinates_utm: list[list[float]]  # polygon base or line [ [x, y, z], ... ]
    dimensions: Optional[dict[str, float]] = None  # width, height, length
    depth_below_surface_m: float
    status: Literal["active_extraction", "depleted_goaf", "intact_pillar", "haulage_way"]
    color_rgba: list[float]  # [r, g, b, a]

class DigitalTwinSceneManifest(BaseModel):
    site_id: str
    scene_mode: Literal["full_3d_integrated", "surface_2_5d_fallback"] = "full_3d_integrated"
    vertical_exaggeration: float = Field(default=25.0, ge=10.0, le=50.0)
    dgms_scale_watermark: str = Field(default="VERTICAL EXAGGERATION: 25X (DGMS AUDIT PROJECTION)")
    surface_dem_bounds_utm: tuple[float, float, float, float]
    surface_dem_elevation_range_m: tuple[float, float]
    draped_heatmap_tile_url_template: str
    subsurface_elements: list[MeshElement] = Field(default_factory=list)
    has_subsurface_cad: bool = True
    camera_target_gps: dict[str, float] = Field(default_factory=lambda: {"lat": 23.7915, "lon": 86.4335, "altitude_m": 850.0})
