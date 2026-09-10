from typing import List, Dict, Any, Optional
from src.normalizer.crs_normalizer import SpatialDataNormalizer

class SubsurfaceMeshBuilder:
    """
    SubSense 3D Subsurface Mesh Builder (Section 5.3).
    Constructs translucent volumetric meshes for underground extraction workings:
      - Haulage Galleries & Roadways
      - Intact Coal Pillars (Bord-and-Pillar)
      - Extracted Goaf Voids (Longwall / Depillaring)
      - Overburden Lithology Strata
    Supports graceful fallback to surface-only 2.5D drape when CAD is missing.
    """
    def __init__(self, normalizer: Optional[SpatialDataNormalizer] = None):
        self.normalizer = normalizer or SpatialDataNormalizer()

    def build_scene_manifest(
        self,
        site_id: str,
        cad_layout: Optional[Dict[str, Any]],
        dem_mesh: Dict[str, Any],
        vertical_exaggeration: float = 25.0
    ) -> Dict[str, Any]:
        """
        Builds the unified 3D Digital Twin scene manifest.
        If cad_layout is None, gracefully falls back to 2.5D surface drape mode.
        """
        has_cad = cad_layout is not None and (
            len(cad_layout.get("pillars", [])) > 0 or len(cad_layout.get("galleries", [])) > 0
        )
        scene_mode = "full_3d_integrated" if has_cad else "surface_2_5d_fallback"

        subsurface_elements = []
        if has_cad:
            seam_depth = cad_layout.get("seam_depth_m", 180.0)
            seam_thickness = 4.0

            # 1. Extrude Coal Pillars into 3D Volumetric Prisms
            for pillar in cad_layout.get("pillars", []):
                coords = pillar["coordinates_utm"]
                coords_wgs84 = pillar["coordinates_wgs84"]
                subsurface_elements.append({
                    "id": pillar["id"],
                    "element_type": "pillar",
                    "geometry": "extruded_polygon",
                    "coordinates_utm": coords,
                    "coordinates_wgs84": coords_wgs84,
                    "base_depth_m": seam_depth,
                    "height_m": seam_thickness,
                    "status": pillar["status"],
                    "color_rgba": [0.18, 0.20, 0.24, 0.75]  # Dense coal seam tint
                })

            # 2. Extrude Goaf Voids
            for goaf in cad_layout.get("goaf_panels", []):
                coords = goaf["coordinates_utm"]
                coords_wgs84 = goaf["coordinates_wgs84"]
                subsurface_elements.append({
                    "id": goaf["id"],
                    "element_type": "goaf_void",
                    "geometry": "extruded_polygon",
                    "coordinates_utm": coords,
                    "coordinates_wgs84": coords_wgs84,
                    "base_depth_m": seam_depth,
                    "height_m": seam_thickness * 1.5,
                    "status": "depleted_goaf",
                    "color_rgba": [0.85, 0.15, 0.20, 0.35]  # Highlighted translucent hazard goaf
                })

            # 3. Galleries & Roadways
            for gall in cad_layout.get("galleries", []):
                coords = gall["coordinates_utm"]
                coords_wgs84 = gall["coordinates_wgs84"]
                subsurface_elements.append({
                    "id": gall["id"],
                    "element_type": "gallery",
                    "geometry": "tubular_path",
                    "coordinates_utm": coords,
                    "coordinates_wgs84": coords_wgs84,
                    "depth_m": seam_depth,
                    "width_m": gall.get("width_m", 5.0),
                    "height_m": 3.2,
                    "status": "haulage_way",
                    "color_rgba": [0.35, 0.45, 0.55, 0.60]
                })

        return {
            "site_id": site_id,
            "scene_mode": scene_mode,
            "has_subsurface_cad": has_cad,
            "vertical_exaggeration": vertical_exaggeration,
            "scale_watermark_text": f"VERTICAL EXAGGERATION: {int(vertical_exaggeration)}X (DGMS GEOTECHNICAL STANDARD)",
            "dem_mesh": {
                "vertex_count": dem_mesh["vertex_count"],
                "triangle_count": dem_mesh["triangle_count"],
                "elevation_min_m": dem_mesh["elevation_min_m"],
                "elevation_max_m": dem_mesh["elevation_max_m"],
                "bounds_utm": dem_mesh["bounds_utm"]
            },
            "subsurface_elements_count": len(subsurface_elements),
            "subsurface_elements": subsurface_elements
        }
