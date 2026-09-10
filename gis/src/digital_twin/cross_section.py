import numpy as np
from typing import Dict, Any, List, Tuple

class StratigraphicCrossSectionEngine:
    """
    SubSense Stratigraphic Overburden Slicing Plane Engine (Section 5.3 Enhancement).
    Computes 2D vertical cross-sections through the surface terrain, overburden strata,
    and underground coal seams along any arbitrary survey line.
    """
    @classmethod
    def compute_vertical_cross_section(
        cls,
        start_point_utm: Tuple[float, float],
        end_point_utm: Tuple[float, float],
        num_samples: int = 100,
        seam_depth_m: float = 180.0,
        seam_thickness_m: float = 4.5,
        vertical_exaggeration: float = 25.0
    ) -> Dict[str, Any]:
        """
        Samples a vertical cross-section line:
          - Surface profile (baseline DEM and deformed surface)
          - Overburden lithological horizons (Alluvium, Sandstone, Shale)
          - Seam roof and floor lines
          - Goaf void status
        """
        x1, y1 = start_point_utm
        x2, y2 = end_point_utm

        t = np.linspace(0.0, 1.0, num_samples)
        xs = x1 + t * (x2 - x1)
        ys = y1 + t * (y2 - y1)

        distances_m = t * np.hypot(x2 - x1, y2 - y1)

        # Baseline Surface DEM (undulating terrain around 220m)
        base_dem = 220.0 + 8.0 * np.sin(distances_m / 150.0)

        # Simulated subsidence flexure trough centered at midpoint
        mid_dist = distances_m[-1] / 2.0
        dist_from_center = distances_m - mid_dist
        
        # Subsidence trough (Gaussian depression up to 600mm)
        subsidence_mm = 600.0 * np.exp(-(dist_from_center ** 2) / (2 * (80.0 ** 2)))
        
        # Exaggerated deformed surface
        deformed_surface = base_dem - (subsidence_mm / 1000.0) * vertical_exaggeration

        # Overburden Strata Horizons
        # Horizon 1: Alluvium Base (12m below surface)
        alluvium_base = base_dem - 12.0
        # Horizon 2: Massive Sandstone Main Roof (130m below surface)
        sandstone_base = base_dem - 130.0
        # Horizon 3: Seam Roof
        seam_roof = base_dem - seam_depth_m
        # Horizon 4: Seam Floor
        seam_floor = seam_roof - seam_thickness_m

        profile_points = []
        for i in range(num_samples):
            profile_points.append({
                "distance_m": round(float(distances_m[i]), 1),
                "utm_x": round(float(xs[i]), 2),
                "utm_y": round(float(ys[i]), 2),
                "surface_baseline_m": round(float(base_dem[i]), 2),
                "surface_deformed_m": round(float(deformed_surface[i]), 2),
                "subsidence_mm": round(float(subsidence_mm[i]), 1),
                "alluvium_base_m": round(float(alluvium_base[i]), 2),
                "sandstone_base_m": round(float(sandstone_base[i]), 2),
                "seam_roof_m": round(float(seam_roof[i]), 2),
                "seam_floor_m": round(float(seam_floor[i]), 2)
            })

        return {
            "survey_line": {
                "start_utm": start_point_utm,
                "end_utm": end_point_utm,
                "total_length_m": round(float(distances_m[-1]), 1)
            },
            "vertical_exaggeration": vertical_exaggeration,
            "max_subsidence_mm": round(float(np.max(subsidence_mm)), 1),
            "lithology_units": [
                {"name": "Surface Alluvium & Topsoil", "color_rgba": [0.76, 0.60, 0.42, 0.6]},
                {"name": "Barakar Massive Sandstone Strata", "color_rgba": [0.82, 0.77, 0.65, 0.4]},
                {"name": "Interbedded Carbonaceous Shale", "color_rgba": [0.38, 0.40, 0.45, 0.5]},
                {"name": "Coal Seam No. VII (Extraction Zone)", "color_rgba": [0.12, 0.14, 0.16, 0.85]}
            ],
            "profile_points": profile_points
        }
