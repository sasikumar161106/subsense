from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import ezdxf
from shapely.geometry import Polygon, LineString, mapping
from shapely.validation import make_valid

from src.normalizer.affine_georeferencer import AffineGeoreferencer
from src.normalizer.crs_normalizer import SpatialDataNormalizer

class CADMineParser:
    """
    SubSense CAD/Mine Working Ingestion Engine (Section 4 & 5.3).
    Parses statutory mine extraction drawings (DXF, LandXML, GeoJSON) and applies
    affine georeferencing to align galleries, pillars, and goaf boundaries with UTM/WGS84.
    """
    def __init__(self, georeferencer: Optional[AffineGeoreferencer] = None,
                 crs_normalizer: Optional[SpatialDataNormalizer] = None):
        self.georeferencer = georeferencer or AffineGeoreferencer()
        self.crs_normalizer = crs_normalizer or SpatialDataNormalizer()

    def parse_dxf(self, dxf_path: Path, default_seam_depth_m: float = 180.0) -> Dict[str, Any]:
        """
        Parses an AutoCAD DXF file and extracts underground galleries, coal pillars,
        and goaf extraction panels.
        """
        if not dxf_path.exists():
            raise FileNotFoundError(f"CAD DXF file not found: {dxf_path}")

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        galleries = []
        pillars = []
        goaf_panels = []

        for entity in msp:
            layer = entity.dxf.layer.upper()
            dxftype = entity.dxftype()

            pts_local = []
            if dxftype in ("LWPOLYLINE", "POLYLINE"):
                pts_local = [(p[0], p[1]) for p in entity.get_points()]
            elif dxftype == "LINE":
                pts_local = [(entity.dxf.start.x, entity.dxf.start.y),
                             (entity.dxf.end.x, entity.dxf.end.y)]

            if not pts_local or len(pts_local) < 2:
                continue

            # Georeference to UTM
            pts_utm = self.georeferencer.transform_points(pts_local)
            # Transform to WGS84
            pts_wgs84 = [self.crs_normalizer.utm_to_wgs84(x, y) for x, y in pts_utm]

            feature = {
                "layer": layer,
                "dxftype": dxftype,
                "coordinates_utm": pts_utm,
                "coordinates_wgs84": pts_wgs84,
                "depth_m": default_seam_depth_m
            }

            if "PILLAR" in layer:
                pillars.append(feature)
            elif "GOAF" in layer or "EXTRACT" in layer:
                goaf_panels.append(feature)
            else:
                galleries.append(feature)

        return {
            "dxf_source": str(dxf_path),
            "galleries_count": len(galleries),
            "pillars_count": len(pillars),
            "goaf_panels_count": len(goaf_panels),
            "galleries": galleries,
            "pillars": pillars,
            "goaf_panels": goaf_panels
        }

    def generate_synthetic_bord_and_pillar_layout(
        self,
        center_utm: tuple[float, float] = (442500.0, 2632000.0),
        seam_depth_m: float = 180.0,
        num_pillars_x: int = 6,
        num_pillars_y: int = 5,
        pillar_size_m: float = 35.0,
        gallery_width_m: float = 5.0
    ) -> Dict[str, Any]:
        """
        Generates standard DGMS-compliant synthetic Bord-and-Pillar mine layout
        for testing, simulation, and concessions lacking digitized CAD.
        """
        cx, cy = center_utm
        step = pillar_size_m + gallery_width_m
        start_x = cx - (num_pillars_x * step) / 2.0
        start_y = cy - (num_pillars_y * step) / 2.0

        pillars = []
        galleries = []
        goaf_panels = []

        # Generate rectangular coal pillars
        for ix in range(num_pillars_x):
            for iy in range(num_pillars_y):
                px = start_x + ix * step
                py = start_y + iy * step
                coords_utm = [
                    (px, py),
                    (px + pillar_size_m, py),
                    (px + pillar_size_m, py + pillar_size_m),
                    (px, py + pillar_size_m),
                    (px, py)
                ]
                coords_wgs84 = [self.crs_normalizer.utm_to_wgs84(x, y) for x, y in coords_utm]
                
                # Check if this pillar is extracted into goaf void
                is_goaf = (ix >= 4 and iy >= 3)
                pillar_obj = {
                    "id": f"PILLAR-{ix}-{iy}",
                    "is_goaf": is_goaf,
                    "depth_m": seam_depth_m,
                    "coordinates_utm": coords_utm,
                    "coordinates_wgs84": coords_wgs84,
                    "status": "depleted_goaf" if is_goaf else "intact_pillar"
                }
                if is_goaf:
                    goaf_panels.append(pillar_obj)
                else:
                    pillars.append(pillar_obj)

        # Generate haulage gallery centerlines
        for ix in range(num_pillars_x + 1):
            gx = start_x + ix * step - gallery_width_m / 2.0
            line_utm = [(gx, start_y), (gx, start_y + num_pillars_y * step)]
            line_wgs84 = [self.crs_normalizer.utm_to_wgs84(x, y) for x, y in line_utm]
            galleries.append({
                "id": f"GALLERY-DIP-{ix}",
                "coordinates_utm": line_utm,
                "coordinates_wgs84": line_wgs84,
                "depth_m": seam_depth_m,
                "width_m": gallery_width_m
            })

        for iy in range(num_pillars_y + 1):
            gy = start_y + iy * step - gallery_width_m / 2.0
            line_utm = [(start_x, gy), (start_x + num_pillars_x * step, gy)]
            line_wgs84 = [self.crs_normalizer.utm_to_wgs84(x, y) for x, y in line_utm]
            galleries.append({
                "id": f"GALLERY-STRIKE-{iy}",
                "coordinates_utm": line_utm,
                "coordinates_wgs84": line_wgs84,
                "depth_m": seam_depth_m,
                "width_m": gallery_width_m
            })

        return {
            "type": "synthetic_bord_and_pillar",
            "seam_depth_m": seam_depth_m,
            "pillars": pillars,
            "goaf_panels": goaf_panels,
            "galleries": galleries
        }
