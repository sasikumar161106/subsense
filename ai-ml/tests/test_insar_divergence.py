"""
Unit and integration tests for InSAR Macro-Fusion and Spatial Divergence Analysis.
Validates:
  1. Sentinel-1 SLC scene generation and vertical LOS projection
  2. Resampling to arbitrary target grids
  3. Absolute spatial divergence computation: Δ_InSAR = |Z_sensor - Z_InSAR|
  4. Candidate relocation blind spot discovery outside active sensor mesh footprint
  5. Coherence thresholding and cluster prioritization
"""

import numpy as np
import pytest

from geostatistics.universal_kriging import UniversalKrigingInterpolator
from insar.slc_ingestion import Sentinel1IngestionPipeline, InSARScene
from insar.divergence import InSARDivergenceAnalyzer, BlindSpotDetectionResult, BlindSpotCluster


class TestInSARIngestion:
    @pytest.fixture
    def pipeline(self):
        return Sentinel1IngestionPipeline(min_coherence_threshold=0.35)

    def test_representative_scene_generation(self, pipeline):
        scene = pipeline.generate_representative_scene(
            bounds=(0.0, 500.0, 0.0, 500.0),
            resolution_m=20.0,
        )
        assert isinstance(scene, InSARScene)
        assert scene.is_synthetic_validation is True
        assert scene.vertical_displacement_mm.ndim == 2
        assert scene.los_displacement_mm.shape == scene.vertical_displacement_mm.shape
        # Vertical displacement should exceed LOS displacement because cos(θ_inc) < 1
        assert np.all(scene.vertical_displacement_mm >= scene.los_displacement_mm - 1e-4)
        assert np.all((scene.coherence >= 0.0) & (scene.coherence <= 1.0))

    def test_resample_to_target_grid(self, pipeline):
        scene = pipeline.generate_representative_scene(bounds=(0.0, 400.0, 0.0, 400.0), resolution_m=20.0)
        target_x = np.arange(50.0, 350.0, 10.0)
        target_y = np.arange(50.0, 350.0, 10.0)

        z_resampled, coh_resampled = pipeline.resample_to_grid(scene, target_x, target_y)
        assert z_resampled.shape == (len(target_y), len(target_x))
        assert coh_resampled.shape == (len(target_y), len(target_x))
        assert np.all(np.isfinite(z_resampled))


class TestInSARDivergence:
    @pytest.fixture
    def analyzer(self):
        return InSARDivergenceAnalyzer(divergence_threshold_mm=8.0, mesh_buffer_radius_m=100.0)

    def test_blind_spot_detection_outside_footprint(self, analyzer):
        # 1. Setup mock Kriging result: sensor network clustered at bottom-left [100..250, 100..250]
        kriging = UniversalKrigingInterpolator(grid_resolution_m=20.0)
        sensor_coords = np.array([
            [120.0, 120.0], [180.0, 130.0], [140.0, 200.0], [210.0, 220.0]
        ], dtype=float)
        sensor_values = np.array([20.0, 22.0, 21.0, 23.0], dtype=float)

        krig_res = kriging.interpolate(sensor_coords, sensor_values, grid_bounds=(0.0, 800.0, 0.0, 800.0))

        # 2. InSAR scene has an unmonitored subsidence bowl at top-right (650, 650)
        pipeline = Sentinel1IngestionPipeline()
        insar_scene = pipeline.generate_representative_scene(
            bounds=(0.0, 800.0, 0.0, 800.0),
            resolution_m=20.0,
            active_trough_center=(160.0, 160.0),  # Matches sensor zone
            blind_spot_center=(650.0, 650.0),     # Outside sensor mesh zone
        )

        # 3. Analyze divergence
        result = analyzer.compute_divergence(krig_res, insar_scene, sensor_coords)

        assert isinstance(result, BlindSpotDetectionResult)
        assert result.divergence_raster_mm.shape == krig_res.predicted_field.shape
        assert np.all(result.divergence_raster_mm >= 0.0)

        # Blind spot mask should flag the unmonitored region at (650, 650)
        # while NOT flagging the monitored region near sensors
        assert len(result.candidate_clusters) >= 1
        top_cluster = result.candidate_clusters[0]
        assert top_cluster.distance_to_nearest_sensor_m > 100.0  # Outside mesh footprint
        assert top_cluster.peak_divergence_mm >= 8.0
        assert top_cluster.priority in ["HIGH", "MEDIUM"]
        assert "Candidate sensor relocation target" in top_cluster.recommendation

    def test_low_coherence_rejection(self):
        """Points with decorrelated low coherence must not trigger false alarms."""
        analyzer = InSARDivergenceAnalyzer(divergence_threshold_mm=5.0, min_coherence=0.40)
        kriging = UniversalKrigingInterpolator(grid_resolution_m=20.0)
        sensor_coords = np.array([[100, 100], [200, 100], [150, 200]], dtype=float)
        krig_res = kriging.interpolate(sensor_coords, np.array([10, 12, 11], dtype=float), grid_bounds=(0, 400, 0, 400))

        pipeline = Sentinel1IngestionPipeline()
        scene = pipeline.generate_representative_scene(bounds=(0, 400, 0, 400), resolution_m=20.0)
        # Force low coherence across entire scene
        scene.coherence = np.full_like(scene.coherence, 0.10)

        res = analyzer.compute_divergence(krig_res, scene, sensor_coords)
        # No blind spots should be flagged because radar data is too noisy / decorrelated
        assert len(res.candidate_clusters) == 0
        assert np.sum(res.blind_spot_mask) == 0
