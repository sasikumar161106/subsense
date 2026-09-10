"""
Predictive Time-to-Critical (TTC) Countdown Module.
Calculates raw first-crossing times of critical deformation threshold D_crit:
    TTC_critical = inf{ t > t0 : ŷ(t) >= D_crit } -> [TTC_min, TTC_median, TTC_max]
Pure countdown model without baked-in tier escalation thresholds (Phase 3 fusion handles triggers).
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np


@dataclass
class TTCCountdownResult:
    """Dataclass holding raw time-to-critical countdown outputs."""
    ttc_min_hours: float       # From 90th percentile (upper displacement curve)
    ttc_median_hours: float    # From 50th percentile (median curve)
    ttc_max_hours: float       # From 10th percentile (lower displacement curve)
    d_crit_mm: float           # Critical deformation threshold evaluated
    is_crossing_expected: bool # True if at least one quantile crosses within horizon
    horizon_hours: float       # Length of the forecast evaluated


class TTCCountdown:
    """
    Evaluates first-passage / first-crossing time across quantile trajectories.
    Interpolates linearly between discrete hourly steps for exact sub-hour resolution.
    """

    def __init__(self, d_crit_mm: float = 25.0):
        self.d_crit = float(d_crit_mm)

    @staticmethod
    def _find_first_crossing(
        trajectory: np.ndarray,
        time_steps: np.ndarray,
        threshold: float,
    ) -> float:
        """
        Finds exact first crossing time using linear interpolation.
        Returns float('inf') if threshold is never reached in the window.
        """
        if len(trajectory) == 0:
            return float("inf")

        # If already at or above threshold at t=0
        if trajectory[0] >= threshold:
            return 0.0

        for i in range(len(trajectory) - 1):
            y_curr = trajectory[i]
            y_next = trajectory[i + 1]
            t_curr = time_steps[i]
            t_next = time_steps[i + 1]

            if y_next >= threshold:
                # Linear interpolation
                denom = y_next - y_curr
                if abs(denom) < 1e-9:
                    return float(t_curr)
                alpha = (threshold - y_curr) / denom
                return float(t_curr + alpha * (t_next - t_curr))

        return float("inf")

    def calculate(
        self,
        q10: np.ndarray,
        q50: np.ndarray,
        q90: np.ndarray,
        time_steps_hours: Optional[np.ndarray] = None,
        d_crit: Optional[float] = None,
    ) -> TTCCountdownResult:
        """
        Calculates [TTC_min, TTC_median, TTC_max].
        Note:
          q90 is the pessimistic (upper) displacement curve -> yields TTC_min.
          q50 is the median curve -> yields TTC_median.
          q10 is the optimistic (lower) displacement curve -> yields TTC_max.
        """
        threshold = float(d_crit) if d_crit is not None else self.d_crit
        num_steps = len(q50)

        if time_steps_hours is None:
            time_steps = np.arange(1.0, num_steps + 1.0, dtype=float)
        else:
            time_steps = np.asarray(time_steps_hours, dtype=float)

        horizon = float(time_steps[-1]) if len(time_steps) > 0 else 0.0

        ttc_min = self._find_first_crossing(q90, time_steps, threshold)
        ttc_median = self._find_first_crossing(q50, time_steps, threshold)
        ttc_max = self._find_first_crossing(q10, time_steps, threshold)

        is_crossing = not math.isinf(ttc_min)

        return TTCCountdownResult(
            ttc_min_hours=ttc_min,
            ttc_median_hours=ttc_median,
            ttc_max_hours=ttc_max,
            d_crit_mm=threshold,
            is_crossing_expected=is_crossing,
            horizon_hours=horizon,
        )
