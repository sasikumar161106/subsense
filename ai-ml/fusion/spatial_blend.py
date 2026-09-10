"""
Adaptive Entropy-Weighted Spatial Risk-Surface Blending Module.
Dynamically blends continuous Universal Kriging fields with discrete GNN fracture graph risk.
Shifts interpolation weight toward the GNN in regions showing strong spatial covariance gradients
and directional fracture channeling, honoring physical strata fracture mechanics.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import numpy as np
from scipy.ndimage import sobel, uniform_filter


@dataclass
class SpatialBlendResult:
    blended_field: np.ndarray             # (H, W) composite risk surface in [0.0, 1.0]
    gnn_weight_map: np.ndarray            # (H, W) adaptive GNN weights w_GNN in [0.0, 1.0]
    kriging_weight_map: np.ndarray        # (H, W) adaptive Kriging weights (1 - w_GNN)
    spatial_gradient_magnitude: np.ndarray# (H, W) |grad(Z_kriging)|
    local_entropy_field: np.ndarray       # (H, W) Shannon spatial gradient entropy
    mean_gnn_weight: float
    max_gnn_weight: float
    high_gradient_cell_ratio: float


class AdaptiveSpatialBlender:
    """
    Blends smooth isotropic Universal Kriging fields with directional GNN fracture channeling.
    Prevents isotropic smoothing of sharp fault shears while avoiding point-instability.
    """

    def __init__(
        self,
        base_gnn_weight: float = 0.35,
        min_gnn_weight: float = 0.10,
        max_gnn_weight: float = 0.90,
        gradient_sensitivity: float = 2.5,
        entropy_window_size: int = 3,
    ):
        self.base_gnn_weight = float(base_gnn_weight)
        self.min_gnn_weight = float(min_gnn_weight)
        self.max_gnn_weight = float(max_gnn_weight)
        self.gradient_sensitivity = float(gradient_sensitivity)
        self.window_size = int(entropy_window_size)

    def compute_spatial_gradient(self, field: np.ndarray) -> np.ndarray:
        """Computes gradient magnitude using 2D Sobel spatial operators."""
        gx = sobel(field, axis=1, mode="reflect")
        gy = sobel(field, axis=0, mode="reflect")
        grad_mag = np.sqrt(gx**2 + gy**2)
        return grad_mag

    def compute_local_entropy(self, grad_mag: np.ndarray) -> np.ndarray:
        """
        Computes local Shannon spatial entropy across sliding neighborhood.
        High entropy denotes turbulent/heterogeneous fracture dynamics.
        """
        eps = 1e-7
        # Local mean gradient in neighborhood
        local_sum = uniform_filter(grad_mag, size=self.window_size, mode="reflect") * (self.window_size**2) + eps
        p = grad_mag / local_sum
        p = np.clip(p, eps, 1.0)
        
        # Local entropy approximation
        local_entropy = -uniform_filter(p * np.log2(p), size=self.window_size, mode="reflect") * (self.window_size**2)
        return np.clip(local_entropy, 0.0, 5.0)

    def blend_fields(
        self,
        kriging_field: np.ndarray,
        kriging_variance: np.ndarray,
        gnn_field: np.ndarray,
        reference_gradient_threshold: float = 1.0,
    ) -> SpatialBlendResult:
        """
        Performs adaptive entropy-weighted blending:
            Z_blended(x, y) = (1 - w_GNN(x, y)) * Z_krig + w_GNN(x, y) * Z_GNN
        where w_GNN shifts dynamically toward GNN in regions with steep spatial covariance gradients
        and directional fracture channeling.
        """
        assert kriging_field.shape == gnn_field.shape, "Kriging and GNN grids must have matching shape"
        assert kriging_field.shape == kriging_variance.shape, "Variance grid must match field shape"

        # 1. Compute spatial gradient of kriging surface
        grad_mag = self.compute_spatial_gradient(kriging_field)

        # 2. Local gradient standard deviation (anisotropy / fracture discontinuity)
        local_mean = uniform_filter(grad_mag, size=self.window_size, mode="reflect")
        local_sq = uniform_filter(grad_mag**2, size=self.window_size, mode="reflect")
        local_std = np.sqrt(np.maximum(0.0, local_sq - local_mean**2))

        # Local entropy/discontinuity index: high when there is localized contrast
        eps = 1e-6
        discontinuity_index = local_std / (local_mean + eps)
        discontinuity_index = np.clip(discontinuity_index, 0.0, 3.0)

        # 3. Dynamic activation based on gradient exceedance
        # In smooth low-gradient fields, grad_mag << reference_gradient_threshold, so activation ~ 0
        norm_grad = grad_mag / float(reference_gradient_threshold)
        grad_activation = np.tanh(self.gradient_sensitivity * norm_grad)

        # Variance uncertainty boost
        var_mean = float(np.mean(kriging_variance)) + eps
        norm_var = np.clip(kriging_variance / var_mean, 0.5, 2.0) - 1.0

        # Combine gradient exceedance with local discontinuity
        combined_factor = np.clip(grad_activation + 0.25 * norm_var + 0.15 * discontinuity_index, 0.0, 1.0)

        # Adaptive GNN weight shifts from min_gnn_weight up to max_gnn_weight
        w_gnn = self.min_gnn_weight + (self.max_gnn_weight - self.min_gnn_weight) * combined_factor
        w_krig = 1.0 - w_gnn

        # 4. Composite blend
        blended = w_krig * kriging_field + w_gnn * gnn_field

        high_grad_cells = float(np.mean(norm_grad > 1.0))

        return SpatialBlendResult(
            blended_field=blended,
            gnn_weight_map=w_gnn,
            kriging_weight_map=w_krig,
            spatial_gradient_magnitude=grad_mag,
            local_entropy_field=discontinuity_index,
            mean_gnn_weight=float(np.mean(w_gnn)),
            max_gnn_weight=float(np.max(w_gnn)),
            high_gradient_cell_ratio=high_grad_cells,
        )


    def interpolate_gnn_nodes_to_grid(
        self,
        node_coords_2d: np.ndarray,
        node_risks: np.ndarray,
        grid_shape: Tuple[int, int],
        grid_bounds: Tuple[float, float, float, float],
    ) -> np.ndarray:
        """
        Projects discrete GNN node risks onto target 2D raster grid using
        inverse-distance weighting along the coordinate bounds.
        """
        x_min, x_max, y_min, y_max = grid_bounds
        H, W = grid_shape
        xs = np.linspace(x_min, x_max, W)
        ys = np.linspace(y_min, y_max, H)
        grid_x, grid_y = np.meshgrid(xs, ys)

        gnn_grid = np.zeros(grid_shape, dtype=float)
        weight_sum = np.zeros(grid_shape, dtype=float)
        eps = 1e-4

        for (nx, ny), risk in zip(node_coords_2d, node_risks):
            dist = np.sqrt((grid_x - nx)**2 + (grid_y - ny)**2)
            w = 1.0 / (dist + eps)**2
            gnn_grid += w * risk
            weight_sum += w

        gnn_grid /= np.maximum(weight_sum, eps)
        return np.clip(gnn_grid, 0.0, 1.0)
