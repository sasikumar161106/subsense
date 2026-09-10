"""
Mine geometry reference layer loader.
Loads versioned static GeoJSON defining goaf extraction boundaries and chain pillars.
Computes spatial topology context features: dist_to_goaf_edge_m and pillar_stress_index.
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def point_to_segment_distance_m(
    plat: float, plon: float,
    alat: float, alon: float,
    blat: float, blon: float
) -> float:
    """
    Computes shortest distance from point P to line segment AB in local meter coordinates.
    """
    # Reference origin at P
    cos_lat = math.cos(math.radians(plat))
    m_per_deg_lat = 111139.0
    m_per_deg_lon = 111139.0 * cos_lat

    ax = (alon - plon) * m_per_deg_lon
    ay = (alat - plat) * m_per_deg_lat
    bx = (blon - plon) * m_per_deg_lon
    by = (blat - plat) * m_per_deg_lat

    dx = bx - ax
    dy = by - ay

    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-9:
        return math.sqrt(ax * ax + ay * ay)

    # Project origin (0, 0) onto segment AB
    t = - (ax * dx + ay * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))

    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.sqrt(proj_x * proj_x + proj_y * proj_y)


class MineGeometryLoader:
    """
    Parses versioned mine spatial layout to provide physical context to feature extraction.
    """

    def __init__(self, geojson_path: Optional[str] = None):
        self.geojson_path = geojson_path or str(
            Path(__file__).resolve().parent.parent / "config" / "mine_geometry.geojson"
        )
        self.data: Dict[str, Any] = {}
        self.goaf_polygons: List[List[Tuple[float, float]]] = []
        self.pillar_info: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        p = Path(self.geojson_path)
        if not p.exists():
            # Fallback default goaf boundary for testing/standalone
            self.goaf_polygons = [
                [(86.432000, 23.790500), (86.434500, 23.790500),
                 (86.434500, 23.792500), (86.432000, 23.792500),
                 (86.432000, 23.790500)]
            ]
            self.pillar_info = {"overburden_depth_m": 210.0}
            return

        with open(p, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        features = self.data.get("features", [])
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            f_type = props.get("feature_type", "")

            if f_type == "goaf_void" and geom.get("type") == "Polygon":
                coords = geom.get("coordinates", [])
                if coords and len(coords) > 0:
                    # GeoJSON is [lon, lat]
                    poly = [(pt[0], pt[1]) for pt in coords[0]]
                    self.goaf_polygons.append(poly)
            elif f_type == "chain_pillars":
                self.pillar_info = props

    def dist_to_goaf_edge_m(self, lat: float, lon: float) -> float:
        """
        Calculates the distance from a node to the closest edge of an active goaf void.
        """
        if not self.goaf_polygons:
            return 50.0  # Safe default if no geometry loaded

        min_dist = float("inf")
        for poly in self.goaf_polygons:
            n = len(poly)
            for i in range(n - 1):
                alon, alat = poly[i]
                blon, blat = poly[i + 1]
                d = point_to_segment_distance_m(lat, lon, alat, alon, blat, blon)
                if d < min_dist:
                    min_dist = d

        return float(min_dist)

    def pillar_stress_index(self, lat: float, lon: float) -> float:
        """
        Computes geotechnical abutment pressure index [0.0, 1.0].
        Abutment pressure peaks near the active goaf extraction boundary
        and increases with overburden depth.
        """
        dist_m = self.dist_to_goaf_edge_m(lat, lon)
        depth_m = self.pillar_info.get("overburden_depth_m", 210.0)

        # Geotechnical formulation: stress peak within abutment zone (~30m decay length)
        # S = (depth / ref_depth) * exp(-dist / decay)
        decay_m = 35.0
        depth_ratio = min(1.5, depth_m / 200.0)
        raw_stress = depth_ratio * math.exp(-dist_m / decay_m)
        return float(min(1.0, max(0.0, raw_stress)))
