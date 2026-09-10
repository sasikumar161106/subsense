import numpy as np
from typing import Tuple

class ColorRampEngine:
    """
    SubSense DGMS Colorblind-Safe Color Ramp (Section 5.1).
    Maps continuous Kriging risk values [0.0, 1.0] to RGBA color space:
      - Low (< 0.65): #22c55e (34, 197, 94) - Green
      - Advisory (0.65 <= r < 0.75): #eab308 (234, 179, 8) - Yellow
      - Warning (0.75 <= r < 0.85): #f97316 (249, 115, 22) - Orange
      - Critical (r >= 0.85): #ef4444 (239, 68, 68) - Red
    """
    # Color hex references
    COLOR_LOW = (34, 197, 94)       # #22c55e
    COLOR_ADVISORY = (234, 179, 8)   # #eab308
    COLOR_WARNING = (249, 115, 22)   # #f97316
    COLOR_CRITICAL = (239, 68, 68)   # #ef4444

    @classmethod
    def apply_color_ramp(cls, risk_grid: np.ndarray, alpha: float = 0.78) -> np.ndarray:
        """
        Converts 2D float array of risk [0.0, 1.0] into RGBA image array (H, W, 4) uint8.
        Smooth piecewise linear interpolation across hazard boundaries.
        """
        H, W = risk_grid.shape
        rgba = np.zeros((H, W, 4), dtype=np.uint8)
        r_clamped = np.clip(risk_grid, 0.0, 1.0)

        # Vectorized color interpolation
        # Keypoints: 0.0 -> Low (faded), 0.50 -> Low, 0.65 -> Advisory, 0.75 -> Warning, 0.85 -> Critical, 1.0 -> Deep Critical
        c_low = np.array(cls.COLOR_LOW, dtype=np.float32)
        c_adv = np.array(cls.COLOR_ADVISORY, dtype=np.float32)
        c_wrn = np.array(cls.COLOR_WARNING, dtype=np.float32)
        c_crt = np.array(cls.COLOR_CRITICAL, dtype=np.float32)

        rgb = np.zeros((H, W, 3), dtype=np.float32)

        # Region 1: 0.0 to 0.65 (Low)
        m1 = (r_clamped < 0.65)
        t1 = np.where(m1, r_clamped / 0.65, 0.0)
        for c in range(3):
            rgb[:, :, c] += m1 * (c_low[c] * (0.6 + 0.4 * t1))

        # Region 2: 0.65 to 0.75 (Advisory)
        m2 = (r_clamped >= 0.65) & (r_clamped < 0.75)
        t2 = np.where(m2, (r_clamped - 0.65) / 0.10, 0.0)
        for c in range(3):
            rgb[:, :, c] += m2 * (c_adv[c] * (1.0 - t2 * 0.1) + c_wrn[c] * (t2 * 0.1))

        # Region 3: 0.75 to 0.85 (Warning)
        m3 = (r_clamped >= 0.75) & (r_clamped < 0.85)
        t3 = np.where(m3, (r_clamped - 0.75) / 0.10, 0.0)
        for c in range(3):
            rgb[:, :, c] += m3 * (c_wrn[c] * (1.0 - t3) + c_crt[c] * t3)

        # Region 4: 0.85 to 1.00 (Critical)
        m4 = (r_clamped >= 0.85)
        t4 = np.where(m4, (r_clamped - 0.85) / 0.15, 0.0)
        for c in range(3):
            rgb[:, :, c] += m4 * (c_crt[c] * (0.9 + 0.1 * t4))

        rgba[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
        
        # Transparent for background near 0
        base_alpha = np.where(r_clamped < 0.05, (r_clamped / 0.05) * alpha * 255.0, alpha * 255.0)
        rgba[:, :, 3] = np.clip(base_alpha, 0, 255).astype(np.uint8)

        return rgba
