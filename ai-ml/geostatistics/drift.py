"""
Physical drift calculation for Universal Kriging in underground coal mining.
Evaluates:
  m(s) = β0 + β1 * DistToGoaf(s) + β2 * OverburdenDepth(s)
"""

from typing import List, Optional, Tuple, Union
import numpy as np


class DriftCalculator:
    """
    Computes physically-grounded drift covariates for Universal Kriging:
      1. Constant term (β0 * 1.0)
      2. Distance to nearest active goaf boundary (β1 * DistToGoaf)
      3. Overburden depth at location s (β2 * OverburdenDepth)
    """

    def __init__(
        self,
        goaf_boundaries: Optional[List[np.ndarray]] = None,
        base_overburden_depth_m: float = 210.0,
        seam_dip_degrees: float = 4.5,
        dip_direction_azimuth_deg: float = 85.0,
    ):
        """
        Args:
            goaf_boundaries: List of (K, 2) coordinate arrays defining extracted goaf polygon edges (in local meters).
            base_overburden_depth_m: Nominal depth of coal seam at origin (0, 0).
            seam_dip_degrees: Coal seam geological inclination angle.
            dip_direction_azimuth_deg: Strike/dip azimuth direction.
        """
        # Default goaf boundary if none provided (e.g. Panel 7 extraction void centered around x=200..400, y=200..600)
        if goaf_boundaries is None:
            default_goaf = np.array([
                [200.0, 200.0],
                [450.0, 200.0],
                [450.0, 650.0],
                [200.0, 650.0],
                [200.0, 200.0],
            ])
            self.goaf_boundaries = [default_goaf]
        else:
            self.goaf_boundaries = goaf_boundaries

        self.base_depth = float(base_overburden_depth_m)
        self.dip_rad = np.radians(seam_dip_degrees)
        self.dip_az_rad = np.radians(dip_direction_azimuth_deg)

    def distance_to_goaf_m(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """
        Computes minimum Euclidean distance from coordinate(s) (x, y) in meters
        to the nearest goaf polygon perimeter.
        """
        x_flat = np.atleast_1d(x).ravel()
        y_flat = np.atleast_1d(y).ravel()
        pts = np.column_stack([x_flat, y_flat])  # (P, 2)

        min_dists = np.full(len(pts), np.inf)

        for poly in self.goaf_boundaries:
            # Distance to polygon boundary segments
            for i in range(len(poly) - 1):
                p1 = poly[i]
                p2 = poly[i + 1]
                seg_vec = p2 - p1
                seg_len_sq = np.sum(seg_vec ** 2)
                if seg_len_sq < 1e-8:
                    d = np.linalg.norm(pts - p1, axis=1)
                else:
                    # Projection factor t in [0, 1]
                    t = np.clip(np.sum((pts - p1) * seg_vec, axis=1) / seg_len_sq, 0.0, 1.0)
                    proj = p1 + t[:, None] * seg_vec
                    d = np.linalg.norm(pts - proj, axis=1)
                min_dists = np.minimum(min_dists, d)

        out = min_dists.reshape(x.shape) if hasattr(x, "shape") and x.ndim > 0 else float(min_dists[0])
        return out

    def overburden_depth_m(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """
        Calculates strata overburden thickness at coordinate(s) accounting for seam dip.
        """
        # Dip gradient components along x (East) and y (North)
        grad_x = np.sin(self.dip_rad) * np.sin(self.dip_az_rad)
        grad_y = np.sin(self.dip_rad) * np.cos(self.dip_az_rad)

        depth = self.base_depth + (x * grad_x + y * grad_y)
        # Ensure physical positive depth
        return np.maximum(depth, 25.0)

    def compute_drift_matrix(self, coords: np.ndarray) -> np.ndarray:
        """
        Constructs drift design matrix F of shape (N, 3):
            [1.0, DistToGoaf, OverburdenDepth]
        """
        x = coords[:, 0]
        y = coords[:, 1]
        dist_goaf = self.distance_to_goaf_m(x, y)
        depth = self.overburden_depth_m(x, y)
        n = len(coords)

        F = np.column_stack([
            np.ones(n, dtype=float),
            dist_goaf,
            depth,
        ])
        return F
