"""
Sentinel-1 Level-1 Single Look Complex (SLC) InSAR Ingestion Pipeline.
Georeferences radar interferograms and converts Line-Of-Sight (LOS) phase
to vertical surface displacement rasters.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
from scipy.interpolate import RegularGridInterpolator


@dataclass
class InSARScene:
    """Dataclass holding georeferenced InSAR displacement scene."""
    scene_id: str
    acquisition_date: str
    incidence_angle_deg: float
    wavelength_m: float
    x_coords: np.ndarray             # 1D array of Easting (m)
    y_coords: np.ndarray             # 1D array of Northing (m)
    los_displacement_mm: np.ndarray  # 2D array (nY, nX) LOS displacement
    vertical_displacement_mm: np.ndarray # 2D array (nY, nX) projected vertical displacement
    coherence: np.ndarray            # 2D array (nY, nX) interferometric coherence in [0, 1]
    is_synthetic_validation: bool    # Mandatory audit flag per spec


class Sentinel1IngestionPipeline:
    """
    Ingestion and phase unwrapping processor for Sentinel-1 C-band SAR interferograms.
    Converts wrapped interferometric phase Δφ to metric Line-of-Sight and vertical subsidence:
      d_LOS = - (λ / (4π)) * Δφ
      d_vert = d_LOS / cos(θ_inc)
    """

    def __init__(
        self,
        wavelength_m: float = 0.05546576,  # Sentinel-1 C-band (5.405 GHz)
        min_coherence_threshold: float = 0.35,
        default_incidence_angle_deg: float = 39.2,
    ):
        self.wavelength = wavelength_m
        self.min_coherence = min_coherence_threshold
        self.default_inc_angle = default_incidence_angle_deg

    def generate_representative_scene(
        self,
        bounds: Tuple[float, float, float, float] = (0.0, 1000.0, 0.0, 1000.0),
        resolution_m: float = 10.0,
        scene_id: str = "S1A_IW_SLC__1SDV_20260901_JHARIA_REP",
        acquisition_date: str = "2026-09-01T00:35:12Z",
        active_trough_center: Tuple[float, float] = (350.0, 450.0),
        blind_spot_center: Tuple[float, float] = (800.0, 800.0),
    ) -> InSARScene:
        """
        Synthesizes a representative calibrated Sentinel-1 scene over the concession coordinate frame.
        Includes primary active mining subsidence bowl plus an unmonitored blind spot.
        """
        xmin, xmax, ymin, ymax = bounds
        x_coords = np.arange(xmin, xmax + resolution_m * 0.5, resolution_m)
        y_coords = np.arange(ymin, ymax + resolution_m * 0.5, resolution_m)
        XX, YY = np.meshgrid(x_coords, y_coords)

        # Primary subsidence bowl over extracted goaf (centered at active_trough_center)
        d1 = np.sqrt((XX - active_trough_center[0]) ** 2 + (YY - active_trough_center[1]) ** 2)
        subsidence_primary = 28.0 * np.exp(-((d1 / 180.0) ** 2))

        # Secondary blind-spot subsidence bowl (outside typical sensor mesh footprint)
        d2 = np.sqrt((XX - blind_spot_center[0]) ** 2 + (YY - blind_spot_center[1]) ** 2)
        subsidence_blind = 22.0 * np.exp(-((d2 / 120.0) ** 2))

        # Total vertical displacement (positive magnitude of settlement)
        vert_disp = subsidence_primary + subsidence_blind + np.random.normal(0, 0.4, XX.shape)
        vert_disp = np.maximum(vert_disp, 0.0)

        # Project vertical to LOS: d_LOS = d_vert * cos(θ_inc)
        inc_rad = np.radians(self.default_inc_angle)
        los_disp = vert_disp * np.cos(inc_rad)

        # Coherence simulation: high over barren/excavated mine ground (0.7-0.9),
        # lower over vegetation or rapid decorrelation zones
        coherence = 0.85 - 0.25 * (vert_disp / 30.0) + np.random.uniform(-0.05, 0.05, XX.shape)
        coherence = np.clip(coherence, 0.1, 0.99)

        return InSARScene(
            scene_id=scene_id,
            acquisition_date=acquisition_date,
            incidence_angle_deg=self.default_inc_angle,
            wavelength_m=self.wavelength,
            x_coords=x_coords,
            y_coords=y_coords,
            los_displacement_mm=los_disp,
            vertical_displacement_mm=vert_disp,
            coherence=coherence,
            is_synthetic_validation=True,
        )

    def resample_to_grid(
        self,
        scene: InSARScene,
        target_x: np.ndarray,
        target_y: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Bilinearly resamples InSAR vertical displacement and coherence to target kriging grid.
        Returns:
            (resampled_vertical_mm, resampled_coherence)
        """
        interp_vert = RegularGridInterpolator(
            (scene.y_coords, scene.x_coords),
            scene.vertical_displacement_mm,
            bounds_error=False,
            fill_value=0.0,
        )
        interp_coh = RegularGridInterpolator(
            (scene.y_coords, scene.x_coords),
            scene.coherence,
            bounds_error=False,
            fill_value=0.5,
        )

        YY_target, XX_target = np.meshgrid(target_y, target_x, indexing="ij")
        pts = np.stack([YY_target.ravel(), XX_target.ravel()], axis=-1)

        vert_grid = interp_vert(pts).reshape(len(target_y), len(target_x))
        coh_grid = interp_coh(pts).reshape(len(target_y), len(target_x))

        return vert_grid, coh_grid
