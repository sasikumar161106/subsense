"""
SubSense Layer 4 - Temporal Forecasting Module.
2-layer Stacked Seq2Seq LSTM with multi-head quantile regression (q=0.1, 0.5, 0.9),
trend classification (Stable, Sustained, Accelerating),
and Predictive Time-to-Critical (TTC) countdown.
"""

from .lstm_model import LSTMDeformationForecaster, QuantileLoss, ForecastResult
from .trend_classifier import TrendClassifier, TrendRegime, TrendClassificationResult
from .ttc import TTCCountdown, TTCCountdownResult
from .calibration import ForecasterBacktestHarness, CalibrationReport

__all__ = [
    "LSTMDeformationForecaster",
    "QuantileLoss",
    "ForecastResult",
    "TrendClassifier",
    "TrendRegime",
    "TrendClassificationResult",
    "TTCCountdown",
    "TTCCountdownResult",
    "ForecasterBacktestHarness",
    "CalibrationReport",
]
