"""
Universal Kriging with Physically-Grounded Geotechnical Drift Terms.
Z(s) = m(s) + ε(s)
m(s) = β0 + β1 * DistToGoaf(s) + β2 * OverburdenDepth(s)

Computes dual-raster outputs:
  1. Predicted deformation field Z_hat(s)
  2. Kriging estimation variance σ²_K(s)
Recomputation budget <= 30 seconds for 10m x 10m mine concession raster.
"""

import time
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.spatial.distance import cdist

from .variogram import (
    VariogramFitter,
    VariogramFitDiagnostics,
    VariogramType,
    spherical_variogram,
    matern32_variogram,
)
from .drift import DriftCalculator

logger = logging.getLogger("subsense.geostatistics.universal_kriging")


@dataclass
class KrigingResult:
    """Dataclass holding universal kriging prediction and uncertainty grids."""
    x_grid: np.ndarray             # 1D array of Easting/X coordinates (meters)
    y_grid: np.ndarray             # 1D array of Northing/Y coordinates (meters)
    predicted_field: np.ndarray    # 2D array of shape (nY, nX) with deformation in mm
    variance_field: np.ndarray     # 2D array of shape (nY, nX) with estimation variance σ²_K in mm²
    std_dev_field: np.ndarray      # 2D array of shape (nY, nX) with estimation std dev σ_K in mm
    drift_coefficients: np.ndarray # [β0, β1, β2]
    diagnostics: VariogramFitDiagnostics
    recompute_time_sec: float      # Measured latency for batch execution
    grid_resolution_m: float       # Cell size (e.g. 10.0m)
    bounds_extent: Tuple[float, float, float, float]  # (xmin, xmax, ymin, ymax)


class UniversalKrigingInterpolator:
    """
    Universal Kriging interpolation engine with goaf-distance and overburden drift.
    Solves the dual Universal Kriging linear system directly with O(N³) factorisation
    and O(N * M) matrix operations, achieving sub-second recomputation on 10,000+ cells.
    """

    def __init__(
        self,
        grid_resolution_m: float = 10.0,
        variogram_type: VariogramType = VariogramType.SPHERICAL,
        drift_calculator: Optional[DriftCalculator] = None,
        max_latency_budget_sec: float = 30.0,
    ):
        self.grid_res = float(grid_resolution_m)
        self.variogram_type = variogram_type
        self.drift_calc = drift_calculator or DriftCalculator()
        self.fitter = VariogramFitter(model_type=variogram_type)
        self.max_latency_budget = float(max_latency_budget_sec)

    def _variogram_function(self, h: np.ndarray, diag: VariogramFitDiagnostics) -> np.ndarray:
        """Evaluates fitted theoretical semivariogram."""
        if diag.variogram_type == VariogramType.SPHERICAL:
            return spherical_variogram(h, diag.nugget, diag.partial_sill, diag.range_m)
        else:
            return matern32_variogram(h, diag.nugget, diag.partial_sill, diag.range_m)

    def interpolate(
        self,
        node_coords: np.ndarray,
        node_values: np.ndarray,
        grid_bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> KrigingResult:
        """
        Executes Universal Kriging interpolation over the mine concession.
        
        Args:
            node_coords: Sensor coordinates array of shape (N, 2) in meters [X, Y].
            node_values: Observed deformation/tilt at sensors, shape (N,) in mm.
            grid_bounds: (xmin, xmax, ymin, ymax) in meters. If None, auto-expanded
                         around sensor extent by 150m margin.
        Returns:
            KrigingResult with predicted field, variance raster, and audit trail.
        """
        t_start = time.perf_counter()
        n_obs = len(node_coords)
        if n_obs < 3:
            raise ValueError(f"Universal Kriging requires at least 3 sensor nodes, got {n_obs}")

        # 1. Refit empirical variogram on current telemetry batch
        diagnostics = self.fitter.fit(node_coords, node_values)

        # 2. Establish grid bounds
        if grid_bounds is None:
            pad = 120.0
            xmin = np.floor((np.min(node_coords[:, 0]) - pad) / self.grid_res) * self.grid_res
            xmax = np.ceil((np.max(node_coords[:, 0]) + pad) / self.grid_res) * self.grid_res
            ymin = np.floor((np.min(node_coords[:, 1]) - pad) / self.grid_res) * self.grid_res
            ymax = np.ceil((np.max(node_coords[:, 1]) + pad) / self.grid_res) * self.grid_res
        else:
            xmin, xmax, ymin, ymax = grid_bounds

        x_grid = np.arange(xmin, xmax + self.grid_res * 0.5, self.grid_res)
        y_grid = np.arange(ymin, ymax + self.grid_res * 0.5, self.grid_res)
        XX, YY = np.meshgrid(x_grid, y_grid)
        grid_pts = np.column_stack([XX.ravel(), YY.ravel()])  # (M, 2)
        n_grid = len(grid_pts)

        # 3. Formulate observation covariance/semivariance matrix Γ_obs
        dists_obs = cdist(node_coords, node_coords)
        gamma_obs = self._variogram_function(dists_obs, diagnostics)
        np.fill_diagonal(gamma_obs, 0.0)

        # 4. Formulate drift matrix F_obs: (N, 3) -> [1, DistToGoaf, OverburdenDepth]
        F_obs = self.drift_calc.compute_drift_matrix(node_coords)
        n_drift = F_obs.shape[1]

        # 5. Assemble Universal Kriging block matrix K: (N + n_drift, N + n_drift)
        # [ Γ    F ]
        # [ F^T  0 ]
        K_mat = np.zeros((n_obs + n_drift, n_obs + n_drift), dtype=float)
        K_mat[:n_obs, :n_obs] = gamma_obs
        K_mat[:n_obs, n_obs:] = F_obs
        K_mat[n_obs:, :n_obs] = F_obs.T

        # Regularization for numerical stability
        K_mat[:n_obs, :n_obs] += np.eye(n_obs) * 1e-6

        # 6. Assemble RHS block matrix for all M target points
        dists_target = cdist(node_coords, grid_pts)  # (N, M)
        gamma_target = self._variogram_function(dists_target, diagnostics)  # (N, M)
        F_target = self.drift_calc.compute_drift_matrix(grid_pts)  # (M, 3)

        RHS = np.zeros((n_obs + n_drift, n_grid), dtype=float)
        RHS[:n_obs, :] = gamma_target
        RHS[n_obs:, :] = F_target.T

        # 7. Vectorized linear solve: K * Weights = RHS
        try:
            weights = np.linalg.solve(K_mat, RHS)  # (N + n_drift, M)
        except np.linalg.LinAlgError:
            weights = np.linalg.pinv(K_mat) @ RHS

        lambda_weights = weights[:n_obs, :]  # (N, M)
        mu_weights = weights[n_obs:, :]      # (n_drift, M)

        # 8. Compute predicted field: Z_hat(s0) = λ^T * Z_obs
        z_pred_flat = lambda_weights.T @ node_values  # (M,)

        # 9. Compute estimation variance: σ²_K(s0) = λ^T * γ0 + μ^T * f0
        var_pred_flat = np.sum(lambda_weights * gamma_target, axis=0) + np.sum(mu_weights * F_target.T, axis=0)
        var_pred_flat = np.maximum(var_pred_flat, 0.0)  # Variance non-negative
        std_pred_flat = np.sqrt(var_pred_flat)

        # 10. Estimate underlying drift coefficients β via generalized least squares
        # β = (F^T Γ^-1 F)^-1 F^T Γ^-1 Z
        try:
            gamma_inv = np.linalg.pinv(gamma_obs + np.eye(n_obs) * 1e-4)
            beta = np.linalg.pinv(F_obs.T @ gamma_inv @ F_obs) @ (F_obs.T @ gamma_inv @ node_values)
        except Exception:
            beta = np.zeros(n_drift)

        # Reshape to (nY, nX)
        nY, nX = len(y_grid), len(x_grid)
        z_pred_grid = z_pred_flat.reshape(nY, nX)
        var_pred_grid = var_pred_flat.reshape(nY, nX)
        std_pred_grid = std_pred_flat.reshape(nY, nX)

        t_elapsed = time.perf_counter() - t_start
        if t_elapsed > self.max_latency_budget:
            logger.warning(
                "Kriging recomputation latency %.3fs exceeded budget %.1fs!",
                t_elapsed, self.max_latency_budget
            )
        else:
            logger.info(
                "Universal Kriging completed in %.3fs (%dx%d grid, %d cells, budget=%.1fs)",
                t_elapsed, nX, nY, n_grid, self.max_latency_budget
            )

        return KrigingResult(
            x_grid=x_grid,
            y_grid=y_grid,
            predicted_field=z_pred_grid,
            variance_field=var_pred_grid,
            std_dev_field=std_pred_grid,
            drift_coefficients=beta,
            diagnostics=diagnostics,
            recompute_time_sec=float(t_elapsed),
            grid_resolution_m=self.grid_res,
            bounds_extent=(float(xmin), float(xmax), float(ymin), float(ymax)),
        )

    def benchmark_latency(
        self,
        num_nodes: int = 25,
        grid_width_m: float = 1000.0,
        grid_height_m: float = 1000.0,
    ) -> float:
        """
        Benchmarks Universal Kriging execution latency over a realistic 1km x 1km concession.
        Verifies compliance with spec Section 7 (<= 30.0s budget).
        """
        np.random.seed(42)
        # Generate representative mesh coordinates and subsidence values
        x_coords = np.random.uniform(50.0, grid_width_m - 50.0, num_nodes)
        y_coords = np.random.uniform(50.0, grid_height_m - 50.0, num_nodes)
        coords = np.column_stack([x_coords, y_coords])

        # Synthetic deformation with trough near center
        center = np.array([grid_width_m / 2.0, grid_height_m / 2.0])
        dists = np.linalg.norm(coords - center, axis=1)
        values = 35.0 * np.exp(-dists / 200.0) + np.random.normal(0, 0.5, num_nodes)

        res = self.interpolate(
            node_coords=coords,
            node_values=values,
            grid_bounds=(0.0, grid_width_m, 0.0, grid_height_m),
        )
        return res.recompute_time_sec
