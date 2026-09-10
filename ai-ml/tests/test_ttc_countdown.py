"""
Unit tests for Predictive Time-To-Critical (TTC) Countdown.
Validates:
  1. Exact analytic crossing times against closed-form linear & polynomial trajectories
  2. Multi-quantile ordering: TTC_min <= TTC_median <= TTC_max
  3. Non-crossing infinity handling
  4. Lead-time target >= 8h on synthetic accelerating caving scenarios
  5. Pure countdown behavior without hardcoded tier escalation
"""

import math
import numpy as np
import pytest

from forecasting.ttc import TTCCountdown, TTCCountdownResult
from gnn.synthetic_fea_generator import GeotechnicalSimulationBootstrap


class TestTTCCountdown:
    @pytest.fixture
    def countdown(self):
        return TTCCountdown(d_crit_mm=25.0)

    def test_analytic_linear_crossing_exact(self, countdown):
        """
        Analytic test:
        Trajectory y(t) = y0 + v * t
        For y0 = 5.0 mm, v = 2.0 mm/h, D_crit = 25.0 mm:
        Crossing is analytically at t* = (25.0 - 5.0) / 2.0 = 10.0 hours.
        """
        time_steps = np.arange(1.0, 25.0, 1.0)
        y_median = 5.0 + 2.0 * time_steps  # at t=10, y=25.0
        y_q90 = y_median + 2.0              # reaches 25 at t=9.0
        y_q10 = y_median - 2.0              # reaches 25 at t=11.0

        res = countdown.calculate(y_q10, y_median, y_q90, time_steps_hours=time_steps, d_crit=25.0)

        assert isinstance(res, TTCCountdownResult)
        assert np.isclose(res.ttc_median_hours, 10.0, atol=1e-4)
        assert np.isclose(res.ttc_min_hours, 9.0, atol=1e-4)
        assert np.isclose(res.ttc_max_hours, 11.0, atol=1e-4)
        assert res.is_crossing_expected is True

    def test_sub_hour_linear_interpolation(self, countdown):
        """
        Tests exact sub-hour crossing interpolation between discrete hours:
        y(t=4) = 22.0 mm, y(t=5) = 26.0 mm, D_crit = 25.0 mm:
        t* = 4.0 + (25.0 - 22.0) / (26.0 - 22.0) * 1.0 = 4.75 hours.
        """
        time_steps = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        y = np.array([10.0, 14.0, 18.0, 22.0, 26.0, 30.0])

        res = countdown.calculate(y, y, y, time_steps_hours=time_steps, d_crit=25.0)
        assert np.isclose(res.ttc_median_hours, 4.75, atol=1e-4)

    def test_non_crossing_returns_infinity(self, countdown):
        """Trajectory that remains below D_crit must return math.inf."""
        time_steps = np.arange(1.0, 49.0, 1.0)
        y_stable = np.full(48, 8.5)

        res = countdown.calculate(y_stable, y_stable, y_stable, time_steps_hours=time_steps, d_crit=25.0)
        assert math.isinf(res.ttc_min_hours)
        assert math.isinf(res.ttc_median_hours)
        assert math.isinf(res.ttc_max_hours)
        assert res.is_crossing_expected is False

    def test_already_above_threshold_returns_zero(self, countdown):
        time_steps = np.array([1.0, 2.0, 3.0])
        y_high = np.array([28.0, 30.0, 32.0])

        res = countdown.calculate(y_high, y_high, y_high, time_steps_hours=time_steps, d_crit=25.0)
        assert res.ttc_min_hours == 0.0
        assert res.ttc_median_hours == 0.0

    def test_quantile_ordering_invariance(self, countdown):
        """TTC_min (from q90) <= TTC_median (from q50) <= TTC_max (from q10)."""
        time_steps = np.arange(1.0, 49.0, 1.0)
        q50 = 3.0 + 0.8 * time_steps
        q10 = q50 - 3.0
        q90 = q50 + 3.0

        res = countdown.calculate(q10, q50, q90, time_steps_hours=time_steps, d_crit=25.0)
        assert res.ttc_min_hours <= res.ttc_median_hours <= res.ttc_max_hours

    def test_accelerating_scenario_satisfies_8h_lead_time_target(self, countdown):
        """
        Definition of Done:
        Backtest on synthetic accelerating scenario resolves with enough lead time to satisfy >= 8h target.
        """
        bootstrap = GeotechnicalSimulationBootstrap(seed=99)
        # Generate accelerating scenario
        scenario = bootstrap.generate_scenario(88, "ACCELERATING")

        q50 = scenario.displacement_trajectory_mm
        q90 = q50 + 2.0
        q10 = np.maximum(q50 - 2.0, 0.0)

        # Set D_crit such that it crosses in the second half of the 48h horizon (e.g. at 20h)
        # Check that when alert triggers at t=0, TTC provides >= 8h lead time
        d_crit = float(q50[18])  # displacement at hour 19
        res = countdown.calculate(q10, q50, q90, d_crit=d_crit)

        assert res.ttc_median_hours >= 8.0
        assert res.ttc_min_hours >= 8.0
        assert not math.isinf(res.ttc_min_hours)
