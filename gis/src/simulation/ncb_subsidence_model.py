import math
import numpy as np
from typing import Tuple, Dict, Any

class NCBSubsidenceModel:
    """
    SubSense Empirical Subsidence Calculation Engine (Section 5.6).
    Implements statutory UK National Coal Board (NCB) and Peck Gaussian profile models
    for predicting surface subsidence troughs over proposed underground mining panels.
    """
    @classmethod
    def calculate_subsidence_profile(
        cls,
        depth_m: float,
        thickness_m: float,
        panel_width_m: float,
        panel_length_m: float,
        extraction_method: str = "longwall_caving",
        goaf_treatment: str = "caving",
        grid_step_m: float = 15.0
    ) -> Dict[str, Any]:
        """
        Calculates 2D surface deformation grid:
          - S_max (Maximum subsidence in mm)
          - Max Tilt (mm/m)
          - Max Horizontal Strain (mm/m)
          - Angle of draw (degrees)
          - 2D Subsidence Grid (mm)
        """
        # Subsidence factor (a): 0.85 for caving, 0.15 for hydraulic sand stowing
        subsidence_factor = 0.15 if goaf_treatment == "hydraulic_sand_stowing" else 0.82
        
        # Width-to-depth ratio (W/h)
        w_to_h = panel_width_m / depth_m
        
        # Supercritical vs subcritical factor
        # If W/h > 1.4, extraction is supercritical and reaches full theoretical S_max
        supercritical_ratio = min(1.0, w_to_h / 1.4)
        
        # Max theoretical subsidence (meters -> mm)
        s_max_m = thickness_m * subsidence_factor * supercritical_ratio
        s_max_mm = s_max_m * 1000.0

        # Angle of draw (beta) in degrees
        angle_of_draw_deg = 32.5  # Typical Indian coal measures strata
        tan_beta = math.tan(math.radians(angle_of_draw_deg))
        
        # Inflection point distance / radius of influence (i)
        influence_radius_m = depth_m * tan_beta

        # Surface evaluation grid dimensions
        pad_m = influence_radius_m * 1.5
        grid_w_m = panel_width_m + 2 * pad_m
        grid_l_m = panel_length_m + 2 * pad_m

        nx = int(np.ceil(grid_w_m / grid_step_m)) + 1
        ny = int(np.ceil(grid_l_m / grid_step_m)) + 1

        xs = np.linspace(-grid_w_m / 2.0, grid_w_m / 2.0, nx)
        ys = np.linspace(-grid_l_m / 2.0, grid_l_m / 2.0, ny)
        X, Y = np.meshgrid(xs, ys)

        # 2D Gaussian / error-function subsidence distribution
        # Along X (across panel width)
        half_w = panel_width_m / 2.0
        half_l = panel_length_m / 2.0

        # Approximate NCB integral via erf
        from scipy.special import erf
        dist_x1 = (X + half_w) / (math.sqrt(2.0) * (influence_radius_m / 2.5))
        dist_x2 = (X - half_w) / (math.sqrt(2.0) * (influence_radius_m / 2.5))
        f_x = 0.5 * (erf(dist_x1) - erf(dist_x2))

        dist_y1 = (Y + half_l) / (math.sqrt(2.0) * (influence_radius_m / 2.5))
        dist_y2 = (Y - half_l) / (math.sqrt(2.0) * (influence_radius_m / 2.5))
        f_y = 0.5 * (erf(dist_y1) - erf(dist_y2))

        # 2D subsidence grid in millimeters
        subsidence_grid_mm = s_max_mm * f_x * f_y

        # Compute max tilt (first spatial derivative dT = dS / dx) in mm/m
        d_subs_dx = np.gradient(subsidence_grid_mm, grid_step_m, axis=1)
        d_subs_dy = np.gradient(subsidence_grid_mm, grid_step_m, axis=0)
        tilt_magnitude = np.sqrt(d_subs_dx**2 + d_subs_dy**2)
        max_tilt_mm_per_m = float(np.max(tilt_magnitude))

        # Max horizontal tensile & compressive strain (mm/m)
        max_tensile = float(max_tilt_mm_per_m * 0.65)
        max_compressive = float(max_tilt_mm_per_m * 0.80)

        # Affected surface area where subsidence >= 10mm
        affected_cells = np.sum(subsidence_grid_mm >= 10.0)
        affected_area_sq_m = float(affected_cells * (grid_step_m ** 2))

        # DGMS CMR 2017 Statutory Geotechnical Damage Classification
        # Tensile strain >= 3.0 mm/m triggers visible surface fissuring
        # Tilt >= 5.0 mm/m induces masonry structural cracking
        crack_initiation = bool(max_tensile >= 3.0)
        if max_tilt_mm_per_m >= 5.0 or max_tensile >= 3.0:
            damage_class = "SEVERE_STRUCTURAL_DISTRESS_OR_SURFACE_FISSURES"
        elif max_tilt_mm_per_m >= 2.0 or max_tensile >= 1.5:
            damage_class = "APPRECIABLE_TILTING_REQUIRING_PRECAUTION"
        else:
            damage_class = "SLIGHT_OR_NEGLIGIBLE_IMPACT"

        return {
            "max_subsidence_mm": round(s_max_mm, 1),
            "max_tilt_mm_per_m": round(max_tilt_mm_per_m, 2),
            "max_tensile_strain_mm_per_m": round(max_tensile, 2),
            "max_compressive_strain_mm_per_m": round(max_compressive, 2),
            "angle_of_draw_deg": angle_of_draw_deg,
            "affected_surface_area_sq_m": round(affected_area_sq_m, 1),
            "grid_step_m": grid_step_m,
            "grid_dimensions": (ny, nx),
            "subsidence_grid_mm": subsidence_grid_mm,
            "crack_initiation_risk": crack_initiation,
            "damage_classification": damage_class,
            "statutory_buffer_m": 45.0  # DGMS CMR 2017 Regulation 123
        }

