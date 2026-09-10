from typing import Tuple, List, Dict, Optional
import numpy as np
from datetime import datetime, timezone
from .variogram import SemivariogramModel
from src.schemas.gis_interop_contracts import IngestionRasterPayload

class OrdinaryKrigingInterpolator:
    """
    Ordinary Kriging Geostatistical Spatial Interpolator (Section 6.2).
    Generates a continuous subsidence/risk surface and Kriging estimation variance
    from discrete wireless sensor mesh nodes across the mine panel.
    Directly produces the IngestionRasterPayload expected by GIS Layer 5 (heatmap_contracts.py).
    """

    def __init__(
        self,
        variogram: Optional[SemivariogramModel] = None,
        grid_resolution_m: float = 20.0,
    ):
        self.variogram = variogram or SemivariogramModel()
        self.grid_resolution_m = grid_resolution_m

    def interpolate_raster(
        self,
        site_id: str,
        node_coords: Dict[str, Tuple[float, float]],  # {node_id: (utm_x, utm_y)}
        node_values: Dict[str, float],               # {node_id: risk_or_anomaly_score [0,1]}
        bounds_utm: Tuple[float, float, float, float],# (min_x, min_y, max_x, max_y)
        utm_epsg: int = 32645,
        timestamp: Optional[datetime] = None,
    ) -> IngestionRasterPayload:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        min_x, min_y, max_x, max_y = bounds_utm
        xs = np.arange(min_x, max_x + self.grid_resolution_m, self.grid_resolution_m)
        ys = np.arange(min_y, max_y + self.grid_resolution_m, self.grid_resolution_m)
        grid_width = len(xs)
        grid_height = len(ys)

        # Extract sampled node arrays
        common_nodes = [nid for nid in node_coords if nid in node_values]
        n_samples = len(common_nodes)

        if n_samples < 2:
            # Fallback uniform raster if insufficient nodes
            uniform_val = float(list(node_values.values())[0]) if n_samples == 1 else 0.0
            risk_grid = np.full((grid_height, grid_width), uniform_val, dtype=np.float32)
            variance_grid = np.full((grid_height, grid_width), 1.0, dtype=np.float32)

            return IngestionRasterPayload(
                site_id=site_id,
                timestamp=timestamp,
                grid_width=grid_width,
                grid_height=grid_height,
                bounds_utm=bounds_utm,
                utm_epsg=utm_epsg,
                risk_values=risk_grid.tolist(),
                variance_values=variance_grid.tolist(),
                gateway_sync_age_seconds=1.2,
            )

        coords_arr = np.array([node_coords[nid] for nid in common_nodes], dtype=np.float64)  # [N, 2]
        vals_arr = np.array([node_values[nid] for nid in common_nodes], dtype=np.float64)     # [N]

        # 1. Build sample-to-sample semivariance matrix Gamma [N+1, N+1]
        diff = coords_arr[:, np.newaxis, :] - coords_arr[np.newaxis, :, :]
        sample_dist = np.sqrt(np.sum(diff ** 2, axis=-1))
        gamma_mat = self.variogram.evaluate(sample_dist)

        # Ordinary Kriging matrix with Lagrange multiplier row & col
        K = np.zeros((n_samples + 1, n_samples + 1), dtype=np.float64)
        K[:n_samples, :n_samples] = gamma_mat
        K[:n_samples, n_samples] = 1.0
        K[n_samples, :n_samples] = 1.0
        K[n_samples, n_samples] = 0.0

        # Regularization for numerical stability
        np.fill_diagonal(K[:n_samples, :n_samples], 0.0)
        K_inv = np.linalg.pinv(K)

        # 2. Grid evaluation
        grid_x, grid_y = np.meshgrid(xs, ys)
        grid_points = np.stack([grid_x.ravel(), grid_y.ravel()], axis=1)  # [P, 2]
        n_points = len(grid_points)

        # Distance from all grid points to each sample node: [P, N]
        diff_grid = grid_points[:, np.newaxis, :] - coords_arr[np.newaxis, :, :]
        grid_dist = np.sqrt(np.sum(diff_grid ** 2, axis=-1))  # [P, N]

        gamma_0 = self.variogram.evaluate(grid_dist)  # [P, N]
        # Append 1.0 for Lagrange condition
        gamma_0_ext = np.ones((n_points, n_samples + 1), dtype=np.float64)
        gamma_0_ext[:, :n_samples] = gamma_0

        # Solve weights for all grid points: weights = gamma_0_ext @ K_inv.T -> [P, N+1]
        weights = np.dot(gamma_0_ext, K_inv.T)
        lambda_w = weights[:, :n_samples]
        mu = weights[:, n_samples]

        # Estimated values: Z_hat = lambda_w @ vals_arr -> [P]
        z_hat = np.dot(lambda_w, vals_arr)
        z_hat = np.clip(z_hat, 0.0, 1.0)

        # Kriging estimation variance: sigma_K^2 = sum(lambda_i * gamma_0_i) + mu -> [P]
        var_k = np.sum(lambda_w * gamma_0, axis=1) + mu
        var_k = np.clip(var_k, 0.0, 2.0)

        risk_grid = z_hat.reshape((grid_height, grid_width))
        variance_grid = var_k.reshape((grid_height, grid_width))

        return IngestionRasterPayload(
            site_id=site_id,
            timestamp=timestamp,
            grid_width=grid_width,
            grid_height=grid_height,
            bounds_utm=bounds_utm,
            utm_epsg=utm_epsg,
            risk_values=risk_grid.tolist(),
            variance_values=variance_grid.tolist(),
            gateway_sync_age_seconds=1.2,
        )
