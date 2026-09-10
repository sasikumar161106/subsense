import numpy as np
from typing import List, Dict, Tuple, Any
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid

class ContourExtractor:
    """
    SubSense Contour Extraction Engine (Section 5.2).
    Extracts closed isoline polygons from continuous risk raster matching
    statutory alert thresholds:
      - Advisory: >= 0.65
      - Warning:  >= 0.75
      - Critical: >= 0.85
    """
    THRESHOLDS = {
        "advisory": 0.65,
        "warning": 0.75,
        "critical": 0.85
    }

    @classmethod
    def extract_isolines(
        cls,
        risk_grid: np.ndarray,
        bounds_utm: Tuple[float, float, float, float]  # (min_x, min_y, max_x, max_y)
    ) -> Dict[str, List[Polygon]]:
        """
        Extracts polygons for each threshold level using marching-squares / contour extraction.
        Returns dict: {'advisory': [Polygon, ...], 'warning': [...], 'critical': [...]} in UTM coordinates.
        """
        H, W = risk_grid.shape
        min_x, min_y, max_x, max_y = bounds_utm

        x_coords = np.linspace(min_x, max_x, W)
        y_coords = np.linspace(min_y, max_y, H)
        X, Y = np.meshgrid(x_coords, y_coords)

        extracted_zones = {
            "advisory": [],
            "warning": [],
            "critical": []
        }

        fig, ax = plt.subplots()
        try:
            for tier, level in cls.THRESHOLDS.items():
                cs = ax.contour(X, Y, risk_grid, levels=[level])
                # Support both modern matplotlib (get_paths) and legacy (collections)
                paths = []
                if hasattr(cs, "get_paths"):
                    paths = cs.get_paths()
                elif hasattr(cs, "collections"):
                    for col in cs.collections:
                        paths.extend(col.get_paths())

                for path in paths:
                    polys = path.to_polygons()
                    for poly_coords in polys:
                        if len(poly_coords) >= 4:
                            try:
                                poly = Polygon(poly_coords)
                                valid_poly = make_valid(poly)
                                if valid_poly.is_empty:
                                    continue
                                if isinstance(valid_poly, Polygon):
                                    extracted_zones[tier].append(valid_poly)
                                elif isinstance(valid_poly, MultiPolygon):
                                    for p in valid_poly.geoms:
                                        if not p.is_empty:
                                            extracted_zones[tier].append(p)
                            except Exception:
                                continue
        finally:
            plt.close(fig)

        return extracted_zones
