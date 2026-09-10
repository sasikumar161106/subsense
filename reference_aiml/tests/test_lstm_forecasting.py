import pytest
import numpy as np
from src.schemas.risk_event_contracts import ForecastTrendEnum
from src.models.lstm_forecaster import LSTMProgressionForecaster

def test_lstm_forecast_accelerating_trend():
    forecaster = LSTMProgressionForecaster(critical_displacement_mm=40.0)

    # 20 timesteps of accelerating displacement
    # shape [20, 4] -> [tilt, vibration, displacement, anomaly]
    t = np.arange(20, dtype=np.float32)
    tilts = 0.5 + 0.1 * t
    vibes = 0.02 + 0.01 * t
    disps = 2.0 + 0.05 * (t ** 2)  # accelerating quadratic curve
    anoms = 0.5 + 0.02 * t
    temporal_matrix = np.column_stack([tilts, vibes, disps, anoms])

    trend, ttc, metrics = forecaster.forecast_zone(
        temporal_features=temporal_matrix,
        current_displacement_mm=float(disps[-1]),
        time_step_hours=1.0 / 60.0,
    )

    assert trend in (ForecastTrendEnum.ACCELERATING, ForecastTrendEnum.SUDDEN_ONSET)
    assert ttc is not None
    assert ttc > 0.0
    assert metrics["velocity_mm_hr"] > 0.0

def test_lstm_forecast_stable_trend():
    forecaster = LSTMProgressionForecaster(critical_displacement_mm=40.0)

    # Flat stable sequence
    t = np.arange(20, dtype=np.float32)
    tilts = np.full(20, 0.5, dtype=np.float32)
    vibes = np.full(20, 0.02, dtype=np.float32)
    disps = np.full(20, 1.2, dtype=np.float32)
    anoms = np.full(20, 0.05, dtype=np.float32)
    temporal_matrix = np.column_stack([tilts, vibes, disps, anoms])

    trend, ttc, metrics = forecaster.forecast_zone(
        temporal_features=temporal_matrix,
        current_displacement_mm=1.2,
    )

    assert trend == ForecastTrendEnum.STABLE
    # Per Section 6.3: Reported as null when trend is stable
    assert ttc is None
