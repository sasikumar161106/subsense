"""
Unit tests for Adaptive Entropy-Weighted Spatial Risk-Surface Blending.
Verifies dynamic weight shift toward GNN in high spatial covariance gradient zones.
"""

import numpy as np
import pytest

from fusion.spatial_blend import AdaptiveSpatialBlender, SpatialBlendResult


class TestSpatialBlending:
    def test_smooth_field_favors_kriging(self):
        blender = AdaptiveSpatialBlender(
            base_gnn_weight=0.35,
            min_gnn_weight=0.10,
            max_gnn_weight=0.90,
            gradient_sensitivity=2.5,
        )

        # Smooth, continuous Kriging surface with small gradient
        H, W = 40, 40
        x = np.linspace(0, 1, W)
        y = np.linspace(0, 1, H)
        xx, yy = np.meshgrid(x, y)
        kriging_field = 0.2 + 0.05 * xx + 0.03 * yy
        kriging_var = np.full((H, W), 0.01, dtype=float)
        gnn_field = np.full((H, W), 0.3, dtype=float)

        res = blender.blend_fields(kriging_field, kriging_var, gnn_field)
        assert isinstance(res, SpatialBlendResult)
        assert res.blended_field.shape == (H, W)
        # In smooth low-gradient regime, Kriging dominates (Kriging weight > GNN weight)
        assert np.mean(res.kriging_weight_map) > np.mean(res.gnn_weight_map)
        assert res.mean_gnn_weight < 0.50

    def test_steep_gradient_shifts_weight_to_gnn(self):
        blender = AdaptiveSpatialBlender(
            base_gnn_weight=0.35,
            min_gnn_weight=0.10,
            max_gnn_weight=0.90,
            gradient_sensitivity=3.0,
        )

        H, W = 40, 40
        # Field with a sharp fracture fault line step
        kriging_field = np.zeros((H, W), dtype=float)
        kriging_field[:, 20:] = 8.5  # Sharp 8.5mm fault shear step
        kriging_var = np.full((H, W), 0.15, dtype=float)
        gnn_field = np.ones((H, W), dtype=float) * 0.85

        res = blender.blend_fields(kriging_field, kriging_var, gnn_field)
        assert res.max_gnn_weight >= 0.70
        # Check that cells along the fault step (col 19-21) have elevated GNN weight
        fault_gnn_weight = np.mean(res.gnn_weight_map[:, 19:22])
        far_gnn_weight = np.mean(res.gnn_weight_map[:, :10])
        assert fault_gnn_weight > far_gnn_weight

    def test_gnn_node_interpolation_to_grid(self):
        blender = AdaptiveSpatialBlender()
        node_coords = np.array([
            [100.0, 100.0],
            [200.0, 100.0],
            [100.0, 200.0],
            [200.0, 200.0],
        ])
        node_risks = np.array([0.2, 0.8, 0.3, 0.9])
        grid_bounds = (50.0, 250.0, 50.0, 250.0)

        grid = blender.interpolate_gnn_nodes_to_grid(
            node_coords_2d=node_coords,
            node_risks=node_risks,
            grid_shape=(30, 30),
            grid_bounds=grid_bounds,
        )

        assert grid.shape == (30, 30)
        assert np.all(grid >= 0.0) and np.all(grid <= 1.0)
