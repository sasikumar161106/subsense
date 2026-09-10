"""
InSAR vs Sensor Mesh Spatial Divergence Analyzer.
Computes:
  Δ_InSAR = |Z_sensor - Z_InSAR|
Identifies candidate blind spots outside the active sensor mesh footprint
for physical sensor relocation.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.ndimage import label, center_of_mass
from scipy.spatial.distance import cdist

from geostatistics.universal_kriging import KrigingResult
from .slc_ingestion import Sentinel1IngestionPipeline, InSARScene


@dataclass
class BlindSpotCluster:
    """Candidate relocation target identified from InSAR divergence."""
    cluster_id: int
    centroid_x_m: float
    centroid_y_m: float
    peak_divergence_mm: float
    mean_divergence_mm: float
    area_m2: float
    distance_to_nearest_sensor_m: float
    priority: str  # "HIGH", "MEDIUM", "LOW"
    recommendation: str


@dataclass
class BlindSpotDetectionResult:
    """Dataclass holding divergence analysis artifacts."""
    divergence_raster_mm: np.ndarray        # 2D array Δ_InSAR
    blind_spot_mask: np.ndarray             # 2D boolean array
    candidate_clusters: List[BlindSpotCluster]
    threshold_mm: float                     # Explicit divergence cutoff
    mesh_buffer_radius_m: float
    total_blind_spot_area_m2: float
    x_grid: np.ndarray
    y_grid: np.ndarray
    validation_source: str                  # Real vs synthetic scene disclaimer


class InSARDivergenceAnalyzer:
    """
    Overlays InSAR displacement against Kriging sensor deformation surface.
    Identifies unmonitored subsidence basins outside the sensor network footprint.
    """

    def __init__(
        self,
        divergence_threshold_mm: float = 8.0,
        mesh_buffer_radius_m: float = 120.0,
        min_coherence: float = 0.35,
    ):
        self.divergence_threshold = float(divergence_threshold_mm)
        self.mesh_buffer_radius = float(mesh_buffer_radius_m)
        self.min_coherence = float(min_coherence)
        self.ingest_pipeline = Sentinel1IngestionPipeline(min_coherence_threshold=min_coherence)

    def compute_divergence(
        self,
        kriging_result: KrigingResult,
        insar_scene: InSARScene,
        sensor_coords: np.ndarray,  # (N, 2) [X, Y]
    ) -> BlindSpotDetectionResult:
        """
        Executes spatial divergence analysis and clusters candidate relocation zones.
        """
        target_x = kriging_result.x_grid
        target_y = kriging_result.y_grid
        z_sensor = kriging_result.predicted_field  # (nY, nX)

        # 1. Resample InSAR scene onto kriging raster coordinates
        z_insar, coherence = self.ingest_pipeline.resample_to_grid(insar_scene, target_x, target_y)

        # 2. Pointwise absolute divergence Δ_InSAR = |Z_sensor - Z_InSAR|
        divergence = np.abs(z_sensor - z_insar)

        # 3. Calculate distance from every grid cell to nearest physical sensor
        YY, XX = np.meshgrid(target_y, target_x, indexing="ij")
        grid_pts = np.column_stack([XX.ravel(), YY.ravel()])  # (M, 2)
        dists_to_sensors = cdist(grid_pts, sensor_coords)     # (M, N)
        min_dist_to_sensor = np.min(dists_to_sensors, axis=1).reshape(len(target_y), len(target_x))

        # 4. Formulate boolean criteria
        is_high_div = divergence >= self.divergence_threshold
        is_outside_footprint = min_dist_to_sensor > self.mesh_buffer_radius
        is_coherent = coherence >= self.min_coherence

        blind_spot_mask = is_high_div & is_outside_footprint & is_coherent

        # 5. Connected component clustering of candidate relocation zones
        labeled_array, num_features = label(blind_spot_mask)
        cell_area_m2 = kriging_result.grid_resolution_m ** 2

        candidate_clusters = []
        for feat_id in range(1, num_features + 1):
            mask_feat = (labeled_array == feat_id)
            num_cells = int(np.sum(mask_feat))
            area_m2 = float(num_cells * cell_area_m2)

            # Filter small single-cell noise spikes (< 400 m² = 4 cells)
            if area_m2 < 300.0:
                continue

            # Centroid in grid indices
            cy_idx, cx_idx = center_of_mass(mask_feat)
            # Map to real-world coordinates
            cx_m = float(target_x[int(round(cx_idx))])
            cy_m = float(target_y[int(round(cy_idx))])

            peak_div = float(np.max(divergence[mask_feat]))
            mean_div = float(np.mean(divergence[mask_feat]))
            dist_sensor = float(np.min(min_dist_to_sensor[mask_feat]))

            if peak_div >= self.divergence_threshold * 1.5 and area_m2 >= 1000.0:
                priority = "HIGH"
            elif peak_div >= self.divergence_threshold:
                priority = "MEDIUM"
            else:
                priority = "LOW"

            rec = (
                f"Candidate sensor relocation target: InSAR detects {peak_div:.1f}mm unmonitored subsidence "
                f"at ({cx_m:.1f}E, {cy_m:.1f}N), {dist_sensor:.1f}m beyond active mesh perimeter. "
                f"Priority: {priority} (Affected Area: {area_m2:.0f} m²)."
            )

            cluster = BlindSpotCluster(
                cluster_id=feat_id,
                centroid_x_m=cx_m,
                centroid_y_m=cy_m,
                peak_divergence_mm=peak_div,
                mean_divergence_mm=mean_div,
                area_m2=area_m2,
                distance_to_nearest_sensor_m=dist_sensor,
                priority=priority,
                recommendation=rec,
            )
            candidate_clusters.append(cluster)

        # Sort clusters by peak divergence descending
        candidate_clusters.sort(key=lambda c: c.peak_divergence_mm, reverse=True)

        total_area = float(np.sum(blind_spot_mask) * cell_area_m2)

        source_disclaimer = (
            "Representative synthetic Sentinel-1 scene (calibrated to Jharia concession)"
            if insar_scene.is_synthetic_validation
            else "Live Sentinel-1 Level-1 SLC interferogram"
        )

        return BlindSpotDetectionResult(
            divergence_raster_mm=divergence,
            blind_spot_mask=blind_spot_mask,
            candidate_clusters=candidate_clusters,
            threshold_mm=self.divergence_threshold,
            mesh_buffer_radius_m=self.mesh_buffer_radius,
            total_blind_spot_area_m2=total_area,
            x_grid=target_x,
            y_grid=target_y,
            validation_source=source_disclaimer,
        )
