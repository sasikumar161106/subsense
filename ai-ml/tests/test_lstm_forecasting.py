"""
Unit and integration tests for LSTM Deformation Forecaster and Trend Classifier.
Validates:
  1. Pinball quantile loss
  2. Seq2Seq LSTM output shapes and non-crossing quantile guarantees
  3. Geotechnical trend classification (Stable, Sustained, Accelerating)
  4. Calibration harness metrics and ECE computation
"""

import numpy as np
import pytest
import torch

from forecasting.lstm_model import LSTMDeformationForecaster, QuantileLoss, ForecastResult
from forecasting.trend_classifier import TrendClassifier, TrendRegime
from forecasting.calibration import ForecasterBacktestHarness, CalibrationReport


class TestQuantileLoss:
    def test_zero_loss_on_exact_match(self):
        loss_fn = QuantileLoss(quantiles=[0.1, 0.5, 0.9])
        y = torch.tensor([[10.0, 15.0]], dtype=torch.float32)
        # Perfect predictions matching target for all quantiles
        preds = torch.tensor([[[10.0, 10.0, 10.0], [15.0, 15.0, 15.0]]], dtype=torch.float32)
        loss = loss_fn(preds, y)
        assert torch.isclose(loss, torch.tensor(0.0), atol=1e-5)

    def test_asymmetric_pinball_penalty(self):
        loss_fn_10 = QuantileLoss(quantiles=[0.1])
        loss_fn_90 = QuantileLoss(quantiles=[0.9])

        target = torch.tensor([[10.0]], dtype=torch.float32)
        # Under-prediction (target > pred)
        pred_under = torch.tensor([[[8.0]]], dtype=torch.float32)  # error = 2.0
        # Over-prediction (pred > target)
        pred_over = torch.tensor([[[12.0]]], dtype=torch.float32)  # error = -2.0

        # For q=0.1, overprediction penalty is (1 - 0.1) * 2 = 1.8; underprediction penalty is 0.1 * 2 = 0.2
        loss_under_10 = loss_fn_10(pred_under, target)
        loss_over_10 = loss_fn_10(pred_over, target)
        assert loss_over_10 > loss_under_10

        # For q=0.9, underprediction penalty is 0.9 * 2 = 1.8; overprediction penalty is 0.1 * 2 = 0.2
        loss_under_90 = loss_fn_90(pred_under, target)
        loss_over_90 = loss_fn_90(pred_over, target)
        assert loss_under_90 > loss_over_90


class TestLSTMForecaster:
    @pytest.fixture
    def forecaster(self):
        return LSTMDeformationForecaster(
            input_dim=3,
            hidden_dim=64,
            num_layers=2,
            horizon_steps=48,
            quantiles=[0.1, 0.5, 0.9],
        )

    def test_forward_output_shape(self, forecaster):
        batch_size = 4
        seq_len = 192
        x = torch.randn(batch_size, seq_len, 3)
        out = forecaster(x)
        assert out.shape == (batch_size, 48, 3)

    def test_custom_horizon(self, forecaster):
        x = torch.randn(2, 192, 3)
        out_24 = forecaster(x, horizon=24)
        assert out_24.shape == (2, 24, 3)
        out_72 = forecaster(x, horizon=72)
        assert out_72.shape == (2, 72, 3)

    def test_quantile_monotonicity_guarantee(self, forecaster):
        """Quantiles must strictly satisfy q10 <= q50 <= q90 at all forecast steps."""
        x = torch.randn(8, 192, 3)
        out = forecaster(x)  # (8, 48, 3)
        q10 = out[:, :, 0]
        q50 = out[:, :, 1]
        q90 = out[:, :, 2]

        # softplus guarantees non-negative increments
        assert torch.all(q50 >= q10 - 1e-5)
        assert torch.all(q90 >= q50 - 1e-5)

    def test_predict_numpy_interface(self, forecaster):
        x_single = np.random.normal(0, 1, (192, 3)).astype(np.float32)
        result = forecaster.predict(x_single, horizon_hours=48)
        assert isinstance(result, ForecastResult)
        assert result.horizon_hours == 48
        assert len(result.q10) == 48
        assert len(result.q50) == 48
        assert len(result.q90) == 48
        assert np.all(result.q90 >= result.q50 - 1e-5)
        assert np.all(result.q50 >= result.q10 - 1e-5)


class TestTrendClassifier:
    @pytest.fixture
    def classifier(self):
        return TrendClassifier(theta_vel_mm_h=0.25, theta_accel_mm_h2=0.050, delta_t_hours=1.0)

    def test_stable_regime_classification(self, classifier):
        # Flat settle trajectory: velocity ~0.02 mm/h, accel ~0.0
        t = np.arange(48, dtype=float)
        y_stable = 5.0 + 0.02 * t + np.random.normal(0, 0.005, 48)
        res = classifier.classify(y_stable)
        assert res.regime == TrendRegime.STABLE
        assert res.velocity_mm_h <= 0.25
        assert res.acceleration_mm_h2 <= 0.050
        assert res.confidence > 0.65

    def test_sustained_regime_classification(self, classifier):
        # Constant linear creep: velocity ~0.50 mm/h (> 0.25), accel ~0.0 (<= 0.050)
        t = np.arange(48, dtype=float)
        y_sustained = 3.0 + 0.50 * t
        res = classifier.classify(y_sustained)
        assert res.regime == TrendRegime.SUSTAINED
        assert res.velocity_mm_h > 0.25
        assert res.acceleration_mm_h2 <= 0.050

    def test_accelerating_regime_classification(self, classifier):
        # Quadratic accelerating collapse: y(t) = 0.5 * a * t^2 with a = 0.12 mm/h² (> 0.050)
        t = np.arange(48, dtype=float)
        y_accel = 2.0 + 0.10 * t + 0.5 * 0.12 * (t ** 2)
        res = classifier.classify(y_accel)
        assert res.regime == TrendRegime.ACCELERATING
        assert res.acceleration_mm_h2 > 0.050
        assert "Tertiary creep" in res.explanation


class TestForecasterBacktestHarness:
    def test_harness_evaluation_metrics(self):
        forecaster = LSTMDeformationForecaster(input_dim=3, hidden_dim=32, num_layers=1, horizon_steps=24)
        harness = ForecasterBacktestHarness(forecaster, ece_threshold=0.08)

        N = 10
        X_test = np.random.normal(0, 1, (N, 192, 3)).astype(np.float32)
        y_test = np.random.uniform(2.0, 10.0, (N, 24)).astype(np.float32)

        report = harness.evaluate(X_test, y_test)
        assert isinstance(report, CalibrationReport)
        assert 0.0 <= report.expected_calibration_error <= 1.0
        assert 0.0 <= report.q10_coverage <= 1.0
        assert 0.0 <= report.q50_coverage <= 1.0
        assert 0.0 <= report.q90_coverage <= 1.0
        assert report.num_eval_samples == N
        assert report.horizon_hours == 24
