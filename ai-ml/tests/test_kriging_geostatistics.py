"""
Unit and integration tests for Universal Kriging Spatial Geostatistics.
Validates:
  1. Variogram fitting and DGMS audit logging
  2. Physically-grounded drift calculations (Goaf distance + Overburden depth)
  3. Dual-raster interpolation (Deformation field + Estimation variance)
  4. Latency budget <= 30 seconds
  5. GeoTIFF and GeoJSON raster export
"""

import os
import json
import numpy as np
import pytest
import tifffile

from geostatistics.variogram import VariogramFitter, VariogramFitDiagnostics, VariogramType
from geostatistics.drift import DriftCalculator
from geostatistics.universal_kriging import UniversalKrigingInterpolator, KrigingResult
from geostatistics.raster_exporter import GeostatisticalRasterExporter


class TestVariogram:
    def test_empirical_variogram_computation(self):
        fitter = VariogramFitter(model_type=VariogramType.SPHERICAL, nlags=6)
        coords = np.array([[0, 0], [10, 0], [20, 0], [30, 0], [40, 0], [50, 0]], dtype=float)
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype=float)

        lags, gamma, counts, total_pairs = fitter.compute_empirical_variogram(coords, values)
        assert len(lags) > 0
        assert len(gamma) == len(lags)
        assert total_pairs == 15

    def test_variogram_fit_diagnostics_logging(self):
        fitter_sph = VariogramFitter(model_type=VariogramType.SPHERICAL)
        fitter_mat = VariogramFitter(model_type=VariogramType.MATERN32)

        np.random.seed(42)
        coords = np.random.uniform(0, 500, (15, 2))
        values = np.random.normal(15, 3, 15)

        diag_sph = fitter_sph.fit(coords, values)
        assert isinstance(diag_sph, VariogramFitDiagnostics)
        assert diag_sph.nugget >= 0.0
        assert diag_sph.sill >= diag_sph.nugget
        assert diag_sph.range_m > 0.0
        assert -1.0 <= diag_sph.r_squared <= 1.0

        diag_mat = fitter_mat.fit(coords, values)
        assert diag_mat.variogram_type == VariogramType.MATERN32
        assert diag_mat.range_m > 0.0


class TestDriftCalculator:
    def test_distance_to_goaf(self):
        # Known goaf boundary square [100, 100] to [200, 200]
        goaf = [np.array([[100, 100], [200, 100], [200, 200], [100, 200], [100, 100]], dtype=float)]
        calc = DriftCalculator(goaf_boundaries=goaf, base_overburden_depth_m=200.0)

        # Point inside or on edge: distance to perimeter
        d_on_edge = calc.distance_to_goaf_m(np.array([100.0]), np.array([150.0]))
        assert np.isclose(d_on_edge, 0.0, atol=1e-3)

        # Point 50m west: (50, 150) -> distance should be 50m
        d_west = calc.distance_to_goaf_m(np.array([50.0]), np.array([150.0]))
        assert np.isclose(d_west, 50.0, atol=1e-3)

    def test_drift_matrix_shape(self):
        calc = DriftCalculator()
        coords = np.array([[100, 100], [200, 200], [300, 300]], dtype=float)
        F = calc.compute_drift_matrix(coords)
        assert F.shape == (3, 3)
        # Column 0 is constant 1.0
        assert np.all(F[:, 0] == 1.0)
        # Column 1 is DistToGoaf >= 0.0
        assert np.all(F[:, 1] >= 0.0)
        # Column 2 is OverburdenDepth >= 25.0
        assert np.all(F[:, 2] >= 25.0)


class TestUniversalKriging:
    @pytest.fixture
    def interpolator(self):
        return UniversalKrigingInterpolator(grid_resolution_m=20.0, max_latency_budget_sec=30.0)

    def test_dual_raster_interpolation(self, interpolator):
        node_coords = np.array([
            [100, 100], [250, 200], [350, 400], [450, 500],
            [200, 450], [500, 250], [300, 150], [150, 350]
        ], dtype=float)
        node_values = np.array([10.0, 25.0, 35.0, 40.0, 30.0, 15.0, 20.0, 22.0], dtype=float)

        res = interpolator.interpolate(node_coords, node_values, grid_bounds=(0, 600, 0, 600))
        assert isinstance(res, KrigingResult)
        assert res.predicted_field.ndim == 2
        assert res.variance_field.ndim == 2
        assert res.std_dev_field.ndim == 2
        assert res.predicted_field.shape == res.variance_field.shape

        # Estimation variance non-negative
        assert np.all(res.variance_field >= 0.0)
        # Recompute latency well within budget
        assert res.recompute_time_sec < 5.0

    def test_variance_lower_near_sensors(self, interpolator):
        """Uncertainty property: variance should be significantly lower near sensors than at unmonitored borders."""
        node_coords = np.array([
            [280, 280], [320, 280], [300, 320]
        ], dtype=float)
        node_values = np.array([20.0, 21.0, 22.0], dtype=float)

        res = interpolator.interpolate(node_coords, node_values, grid_bounds=(0, 600, 0, 600))

        # Center point near sensors (300, 300)
        ix_center = np.argmin(np.abs(res.x_grid - 300.0))
        iy_center = np.argmin(np.abs(res.y_grid - 300.0))
        var_near = res.variance_field[iy_center, ix_center]

        # Far corner (0, 0)
        var_far = res.variance_field[0, 0]
        assert var_far > var_near

    def test_latency_benchmark_under_30s(self, interpolator):
        latency = interpolator.benchmark_latency(num_nodes=25, grid_width_m=1000.0, grid_height_m=1000.0)
        assert latency <= 30.0


class TestRasterExporter:
    def test_geotiff_and_geojson_export(self, tmp_path):
        interpolator = UniversalKrigingInterpolator(grid_resolution_m=25.0)
        node_coords = np.array([[100, 100], [200, 150], [150, 250], [300, 200]], dtype=float)
        node_values = np.array([12.0, 18.0, 24.0, 15.0], dtype=float)
        res = interpolator.interpolate(node_coords, node_values, grid_bounds=(0, 400, 0, 400))

        exporter = GeostatisticalRasterExporter()
        tif_path = str(tmp_path / "test_kriging.tif")
        geojson_path = str(tmp_path / "test_kriging.geojson")

        exporter.export_geotiff(res, tif_path)
        assert os.path.exists(tif_path)
        with tifffile.TiffFile(tif_path) as tif:
            assert len(tif.pages) > 0
            data = tif.asarray()
            assert data.shape[0] == 2  # 2 bands: Prediction and Variance

        exporter.export_geojson(res, geojson_path, stride=2)
        assert os.path.exists(geojson_path)
        with open(geojson_path, "r", encoding="utf-8") as f:
            gj = json.load(f)
            assert gj["type"] == "FeatureCollection"
            assert len(gj["features"]) > 0
            first = gj["features"][0]
            assert "predicted_subsidence_mm" in first["properties"]
            assert "estimation_variance_mm2" in first["properties"]
