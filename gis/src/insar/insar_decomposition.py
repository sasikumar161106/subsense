import math
import numpy as np
from typing import Tuple, Dict, Any, Optional

class InSARDecompositionEngine:
    """
    SubSense Dual-Pass InSAR Vector Decomposition Engine (Section 5.4 Enhancement).
    Decomposes ascending and descending Sentinel-1 Line-of-Sight (LOS) velocities
    into true vertical subsidence (d_vert) and east-west horizontal shear (d_EW).
    Applies interferometric coherence thresholding (gamma >= 0.35) to eliminate
    decorrelated vegetation/water noise.
    """
    # Sentinel-1 Baseline Flight Geometries (IW mode)
    DEFAULT_INCIDENCE_ASC_DEG = 38.2
    DEFAULT_INCIDENCE_DESC_DEG = 39.1
    DEFAULT_HEADING_ASC_DEG = 348.5   # Ascending pass azimuth
    DEFAULT_HEADING_DESC_DEG = 191.5  # Descending pass azimuth
    COHERENCE_THRESHOLD = 0.35

    @classmethod
    def decompose_los_to_2d(
        cls,
        los_vel_asc_mm_yr: float,
        los_vel_desc_mm_yr: float,
        coherence_asc: float = 0.65,
        coherence_desc: float = 0.70,
        theta_asc_deg: float = DEFAULT_INCIDENCE_ASC_DEG,
        theta_desc_deg: float = DEFAULT_INCIDENCE_DESC_DEG,
        alpha_asc_deg: float = DEFAULT_HEADING_ASC_DEG,
        alpha_desc_deg: float = DEFAULT_HEADING_DESC_DEG
    ) -> Dict[str, Any]:
        """
        Decomposes dual LOS velocities into true vertical and east-west velocities:
          [ S_asc_ew,   C_asc_vert  ] [ d_ew   ] = [ los_asc  ]
          [ S_desc_ew,  C_desc_vert ] [ d_vert ] = [ los_desc ]
        """
        # Check coherence mask
        min_coherence = min(coherence_asc, coherence_desc)
        is_decorrelated = (min_coherence < cls.COHERENCE_THRESHOLD)

        if is_decorrelated:
            return {
                "status": "DECORRELATED_FILTERED",
                "reason": f"Interferometric coherence ({min_coherence:.2f}) below threshold ({cls.COHERENCE_THRESHOLD})",
                "vertical_velocity_mm_year": None,
                "horizontal_ew_velocity_mm_year": None,
                "is_valid": False
            }

        # Trigonometric directional components
        # Ascending
        rad_th_a = math.radians(theta_asc_deg)
        rad_al_a = math.radians(alpha_asc_deg)
        coeff_ew_a = -math.sin(rad_th_a) * math.cos(rad_al_a)
        coeff_vert_a = math.cos(rad_th_a)

        # Descending
        rad_th_d = math.radians(theta_desc_deg)
        rad_al_d = math.radians(alpha_desc_deg)
        coeff_ew_d = -math.sin(rad_th_d) * math.cos(rad_al_d)
        coeff_vert_d = math.cos(rad_th_d)

        A = np.array([
            [coeff_ew_a, coeff_vert_a],
            [coeff_ew_d, coeff_vert_d]
        ], dtype=np.float64)

        B = np.array([los_vel_asc_mm_yr, los_vel_desc_mm_yr], dtype=np.float64)

        # Solve linear system
        solution = np.linalg.solve(A, B)
        d_ew, d_vert = solution[0], solution[1]

        return {
            "status": "VALID_DECOMPOSED",
            "vertical_velocity_mm_year": round(float(d_vert), 2),
            "horizontal_ew_velocity_mm_year": round(float(d_ew), 2),
            "coherence_min": round(min_coherence, 2),
            "is_subsiding": bool(d_vert < 0.0),
            "subsidence_rate_mm_year": abs(round(float(d_vert), 2)) if d_vert < 0.0 else 0.0,
            "shear_direction": "EAST" if d_ew > 0 else "WEST",
            "is_valid": True
        }

    @classmethod
    def decompose_raster_grids(
        cls,
        grid_asc: np.ndarray,
        grid_desc: np.ndarray,
        coherence_grid: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Batch 2D raster decomposition across an entire Sentinel-1 swath.
        Returns: (vertical_grid, horizontal_ew_grid, valid_mask)
        """
        H, W = grid_asc.shape
        rad_th_a = math.radians(cls.DEFAULT_INCIDENCE_ASC_DEG)
        rad_al_a = math.radians(cls.DEFAULT_HEADING_ASC_DEG)
        c_ew_a = -math.sin(rad_th_a) * math.cos(rad_al_a)
        c_v_a = math.cos(rad_th_a)

        rad_th_d = math.radians(cls.DEFAULT_INCIDENCE_DESC_DEG)
        rad_al_d = math.radians(cls.DEFAULT_HEADING_DESC_DEG)
        c_ew_d = -math.sin(rad_th_d) * math.cos(rad_al_d)
        c_v_d = math.cos(rad_th_d)

        # Determinant of 2x2
        det = c_ew_a * c_v_d - c_v_a * c_ew_d

        inv_00 = c_v_d / det
        inv_01 = -c_v_a / det
        inv_10 = -c_ew_d / det
        inv_11 = c_ew_a / det

        d_ew_grid = inv_00 * grid_asc + inv_01 * grid_desc
        d_vert_grid = inv_10 * grid_asc + inv_11 * grid_desc

        if coherence_grid is not None:
            valid_mask = (coherence_grid >= cls.COHERENCE_THRESHOLD)
        else:
            valid_mask = np.ones((H, W), dtype=bool)

        return d_vert_grid, d_ew_grid, valid_mask
