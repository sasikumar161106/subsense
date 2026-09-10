import numpy as np
from typing import Tuple, List, Dict, Optional

class AffineGeoreferencer:
    """
    SubSense 2D Affine Georeferencer (Section 4).
    Transforms local mine CAD coordinate grids (DXF/LandXML) to planar UTM coordinates:
      X_UTM = A * x_local + B * y_local + C
      Y_UTM = D * x_local + E * y_local + F
    """
    def __init__(self, a: float = 1.0, b: float = 0.0, c: float = 0.0,
                 d: float = 0.0, e: float = 1.0, f: float = 0.0):
        self.a = float(a)
        self.b = float(b)
        self.c = float(c)
        self.d = float(d)
        self.e = float(e)
        self.f = float(f)
        self._compute_inverse()

    def _compute_inverse(self):
        """Compute the 2D inverse affine transformation matrix."""
        det = self.a * self.e - self.b * self.d
        if abs(det) < 1e-12:
            raise ValueError("Degenerate affine matrix: determinant is nearly zero.")
        self.inv_a = self.e / det
        self.inv_b = -self.b / det
        self.inv_c = (self.b * self.f - self.c * self.e) / det
        self.inv_d = -self.d / det
        self.inv_e = self.a / det
        self.inv_f = (self.c * self.d - self.a * self.f) / det

    def local_to_utm(self, x_local: float, y_local: float) -> Tuple[float, float]:
        """Transform local CAD coordinate to UTM (Easting, Northing)."""
        x_utm = self.a * x_local + self.b * y_local + self.c
        y_utm = self.d * x_local + self.e * y_local + self.f
        return float(x_utm), float(y_utm)

    def utm_to_local(self, x_utm: float, y_utm: float) -> Tuple[float, float]:
        """Transform UTM (Easting, Northing) back to local CAD coordinates."""
        x_loc = self.inv_a * x_utm + self.inv_b * y_utm + self.inv_c
        y_loc = self.inv_d * x_utm + self.inv_e * y_utm + self.inv_f
        return float(x_loc), float(y_loc)

    def transform_points(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Batch transform a list of (x_local, y_local) to (x_utm, y_utm)."""
        return [self.local_to_utm(x, y) for x, y in points]

    @classmethod
    def calibrate_from_tie_points(cls, tie_points: List[Dict[str, float]]) -> Tuple["AffineGeoreferencer", float]:
        """
        Calibrate affine parameters A, B, C, D, E, F from N >= 3 permanent surface shaft tie-points.
        Each tie-point dict must contain:
          'local_x', 'local_y', 'utm_easting', 'utm_northing'
        Returns:
          (AffineGeoreferencer instance, root_mean_square_error_meters)
        """
        if len(tie_points) < 3:
            raise ValueError(f"Calibration requires at least 3 non-collinear tie-points, got {len(tie_points)}")

        # Construct linear system:
        # [x, y, 1] * [A; B; C] = X_UTM
        # [x, y, 1] * [D; E; F] = Y_UTM
        N = len(tie_points)
        M = np.zeros((N, 3), dtype=np.float64)
        X_target = np.zeros(N, dtype=np.float64)
        Y_target = np.zeros(N, dtype=np.float64)

        for i, tp in enumerate(tie_points):
            M[i, 0] = tp["local_x"]
            M[i, 1] = tp["local_y"]
            M[i, 2] = 1.0
            X_target[i] = tp["utm_easting"]
            Y_target[i] = tp["utm_northing"]

        # Solve via least-squares
        params_x, residuals_x, _, _ = np.linalg.lstsq(M, X_target, rcond=None)
        params_y, residuals_y, _, _ = np.linalg.lstsq(M, Y_target, rcond=None)

        a, b, c = params_x
        d, e, f = params_y

        # Compute RMS error
        predicted_X = M @ params_x
        predicted_Y = M @ params_y
        sq_errors = (predicted_X - X_target) ** 2 + (predicted_Y - Y_target) ** 2
        rmse = float(np.sqrt(np.mean(sq_errors)))

        instance = cls(a=a, b=b, c=c, d=d, e=e, f=f)
        return instance, rmse

    def to_dict(self) -> Dict[str, float]:
        return {
            "a": self.a, "b": self.b, "c": self.c,
            "d": self.d, "e": self.e, "f": self.f
        }
