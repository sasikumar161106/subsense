import numpy as np
from typing import Dict, Any

class VerticalExaggerationEngine:
    """
    SubSense Vertical Exaggeration Calibration Engine (Section 5.3 & Section 9).
    At true scale (1:1), 15mm to 300mm of ground subsidence over a 500m-1500m panel
    is completely imperceptible on a 3D monitor.
    This engine applies calibrated vertical displacement scaling (10x to 50x, default 25x)
    and computes the permanent on-screen DGMS compliance scale ruler.
    """
    DEFAULT_FACTOR = 25.0
    MIN_FACTOR = 10.0
    MAX_FACTOR = 50.0

    @classmethod
    def apply_exaggeration(
        cls,
        base_elevation_m: np.ndarray,
        subsidence_displacement_mm: np.ndarray,
        factor: float = DEFAULT_FACTOR
    ) -> np.ndarray:
        """
        Calculates display elevation in meters with exaggerated subsidence:
          Z_display = Z_base - (subsidence_mm / 1000.0) * factor
        """
        clamped_factor = np.clip(factor, cls.MIN_FACTOR, cls.MAX_FACTOR)
        disp_meters = (subsidence_displacement_mm / 1000.0) * clamped_factor
        return base_elevation_m - disp_meters

    @classmethod
    def generate_scale_ruler_spec(cls, factor: float = DEFAULT_FACTOR) -> Dict[str, Any]:
        """
        Generates metadata for the permanent on-screen DGMS statutory scale ruler.
        """
        clamped_factor = float(np.clip(factor, cls.MIN_FACTOR, cls.MAX_FACTOR))
        # 10 mm real subsidence = (10 * factor) mm visually
        sample_real_subsidence_mm = 20.0
        visual_vertical_displacement_mm = sample_real_subsidence_mm * clamped_factor

        return {
            "factor": clamped_factor,
            "is_standard_dgms": (abs(clamped_factor - 25.0) < 1e-3),
            "watermark_text": f"VERTICAL EXAGGERATION: {int(clamped_factor)}X (DGMS CALIBRATED)",
            "warning_disclaimer": "Ground vertical deformation is exaggerated for situational awareness. Consult metric readouts for true displacement.",
            "ruler_notches": [
                {"real_mm": 5.0, "visual_scale_ratio": f"{int(clamped_factor)}:1"},
                {"real_mm": 10.0, "visual_scale_ratio": f"{int(clamped_factor)}:1"},
                {"real_mm": 25.0, "visual_scale_ratio": f"{int(clamped_factor)}:1"},
                {"real_mm": 50.0, "visual_scale_ratio": f"{int(clamped_factor)}:1"},
                {"real_mm": 100.0, "visual_scale_ratio": f"{int(clamped_factor)}:1"}
            ]
        }
