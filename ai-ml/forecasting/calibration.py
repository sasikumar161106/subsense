"""
Backtesting and Calibration Evaluation Harness for LSTM Forecaster.
Measures Expected Calibration Error (ECE), empirical coverage of quantile bands,
and generates auditable DGMS safety validation reports.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn

from .lstm_model import LSTMDeformationForecaster, QuantileLoss


@dataclass
class CalibrationReport:
    """Dataclass holding calibration and backtesting metrics."""
    expected_calibration_error: float   # ECE across quantiles
    q10_coverage: float                 # Empirical P(y <= q10)
    q50_coverage: float                 # Empirical P(y <= q50)
    q90_coverage: float                 # Empirical P(y <= q90)
    interval_80_coverage: float         # Empirical P(q10 <= y <= q90)
    mean_pinball_loss: float            # Average pinball loss on held-out test set
    rmse: float                         # Root Mean Square Error of median (q50) forecast
    mae: float                          # Mean Absolute Error of median (q50) forecast
    meets_safety_target: bool           # True if ECE < 0.08
    num_eval_samples: int
    horizon_hours: int


class ForecasterBacktestHarness:
    """
    Backtesting harness for evaluating LSTM quantile forecast calibration.
    Verifies that empirical coverage matches nominal quantiles within ECE < 0.08.
    """

    def __init__(
        self,
        model: LSTMDeformationForecaster,
        quantiles: Optional[List[float]] = None,
        ece_threshold: float = 0.08,
    ):
        self.model = model
        self.quantiles = quantiles or [0.1, 0.5, 0.9]
        self.ece_threshold = ece_threshold
        self.criterion = QuantileLoss(quantiles=self.quantiles)

    def evaluate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        device: Optional[torch.device] = None,
    ) -> CalibrationReport:
        """
        Runs backtest evaluation on held-out test sequences.
        Args:
            X_test: Input array of shape (N, 192, 3)
            y_test: Ground-truth target array of shape (N, 48)
            device: Evaluation device
        Returns:
            CalibrationReport
        """
        self.model.eval()
        dev = device or next(self.model.parameters()).device
        
        N, seq_len, num_feats = X_test.shape
        _, horizon = y_test.shape

        X_t = torch.tensor(X_test, dtype=torch.float32, device=dev)
        y_t = torch.tensor(y_test, dtype=torch.float32, device=dev)

        with torch.no_grad():
            preds_t = self.model(X_t, horizon=horizon)  # (N, horizon, 3)
            loss_val = float(self.criterion(preds_t, y_t).item())
            preds_np = preds_t.cpu().numpy()  # (N, horizon, 3)

        q10_pred = preds_np[:, :, 0]
        q50_pred = preds_np[:, :, 1]
        q90_pred = preds_np[:, :, 2]

        total_points = float(N * horizon)

        # Empirical quantile coverage: fraction of true y <= predicted quantile
        q10_cov = float(np.sum(y_test <= q10_pred) / total_points)
        q50_cov = float(np.sum(y_test <= q50_pred) / total_points)
        q90_cov = float(np.sum(y_test <= q90_pred) / total_points)

        # Central 80% interval coverage [q10, q90]
        interval_80 = float(np.sum((y_test >= q10_pred) & (y_test <= q90_pred)) / total_points)

        # Expected Calibration Error (ECE) across the 3 nominal quantiles
        nominal_quantiles = np.array(self.quantiles)
        empirical_quantiles = np.array([q10_cov, q50_cov, q90_cov])
        ece = float(np.mean(np.abs(empirical_quantiles - nominal_quantiles)))

        # Median forecast error metrics
        median_err = y_test - q50_pred
        rmse = float(np.sqrt(np.mean(median_err ** 2)))
        mae = float(np.mean(np.abs(median_err)))

        meets_target = ece < self.ece_threshold

        return CalibrationReport(
            expected_calibration_error=ece,
            q10_coverage=q10_cov,
            q50_coverage=q50_cov,
            q90_coverage=q90_cov,
            interval_80_coverage=interval_80,
            mean_pinball_loss=loss_val,
            rmse=rmse,
            mae=mae,
            meets_safety_target=meets_target,
            num_eval_samples=N,
            horizon_hours=horizon,
        )
