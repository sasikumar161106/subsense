"""
Trend Classifier for SubSense Layer 4.
Evaluates 1st (dŷ/dt) and 2nd (d²ŷ/dt²) derivatives of median forecast trajectory
to categorize subsidence regime into Accelerating, Sustained, or Stable.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np


class TrendRegime(str, Enum):
    ACCELERATING = "ACCELERATING"
    SUSTAINED = "SUSTAINED"
    STABLE = "STABLE"


@dataclass
class TrendClassificationResult:
    """Dataclass encapsulating trend classification metrics and audit trail."""
    regime: TrendRegime
    velocity_mm_h: float          # dŷ/dt
    acceleration_mm_h2: float     # d²ŷ/dt²
    theta_vel: float              # Threshold for sustained
    theta_accel: float            # Threshold for accelerating
    confidence: float             # In [0.0, 1.0]
    explanation: str


class TrendClassifier:
    """
    Kinematic regime classification based on empirical geotechnical derivative thresholds:
      - Accelerating: d²ŷ/dt² > θ_accel (Tertiary creep / dynamic roof breakdown)
      - Sustained:    dŷ/dt > θ_vel     (Secondary steady creep)
      - Stable:       otherwise         (Elastic / settling strata)
    """

    def __init__(
        self,
        theta_vel_mm_h: float = 0.25,
        theta_accel_mm_h2: float = 0.050,
        delta_t_hours: float = 1.0,
    ):
        self.theta_vel = float(theta_vel_mm_h)
        self.theta_accel = float(theta_accel_mm_h2)
        self.delta_t = float(delta_t_hours)

    def compute_derivatives(self, y_median: np.ndarray) -> Tuple[float, float, np.ndarray, np.ndarray]:
        """
        Computes numerical 1st and 2nd derivatives using central finite differences.
        Returns:
            (characteristic_velocity, characteristic_acceleration, vel_series, accel_series)
        """
        if len(y_median) < 3:
            raise ValueError("Median trajectory must have at least 3 points for 2nd derivative calculation.")

        # 1st derivative: dŷ/dt (mm/h)
        vel = np.gradient(y_median, self.delta_t)
        # 2nd derivative: d²ŷ/dt² (mm/h²)
        accel = np.gradient(vel, self.delta_t)

        # Characteristic velocity: 90th percentile to capture sustained movement without single-point outlier spike
        char_vel = float(np.percentile(vel, 90))
        # Characteristic acceleration: 90th percentile of acceleration
        char_accel = float(np.percentile(accel, 90))

        return char_vel, char_accel, vel, accel

    def classify(self, y_median: np.ndarray) -> TrendClassificationResult:
        """
        Classifies subsidence regime from 50th percentile (median) predicted trajectory.
        """
        char_vel, char_accel, _, _ = self.compute_derivatives(y_median)

        if char_accel > self.theta_accel:
            regime = TrendRegime.ACCELERATING
            ratio = min(char_accel / self.theta_accel, 3.0) / 3.0
            confidence = float(0.85 + 0.15 * ratio)
            explanation = (
                f"Accelerating regime detected: 2nd derivative {char_accel:.4f} mm/h² "
                f"exceeds critical curvature threshold θ_accel={self.theta_accel:.4f} mm/h². "
                f"Tertiary creep / dynamic roof breakdown pattern."
            )
        elif char_vel > self.theta_vel:
            regime = TrendRegime.SUSTAINED
            ratio = min(char_vel / self.theta_vel, 3.0) / 3.0
            confidence = float(0.75 + 0.20 * ratio)
            explanation = (
                f"Sustained regime detected: 1st derivative {char_vel:.4f} mm/h "
                f"exceeds steady velocity threshold θ_vel={self.theta_vel:.4f} mm/h "
                f"with sub-critical curvature ({char_accel:.4f} <= {self.theta_accel:.4f} mm/h²). "
                f"Secondary steady creep pattern."
            )
        else:
            regime = TrendRegime.STABLE
            confidence = float(max(0.70, 1.0 - (max(char_vel, 0.0) / max(self.theta_vel, 1e-4))))
            explanation = (
                f"Stable regime: 1st derivative {char_vel:.4f} mm/h <= θ_vel ({self.theta_vel:.4f}) "
                f"and 2nd derivative {char_accel:.4f} mm/h² <= θ_accel ({self.theta_accel:.4f}). "
                f"Normal elastic settling strata."
            )

        return TrendClassificationResult(
            regime=regime,
            velocity_mm_h=char_vel,
            acceleration_mm_h2=char_accel,
            theta_vel=self.theta_vel,
            theta_accel=self.theta_accel,
            confidence=min(max(confidence, 0.0), 1.0),
            explanation=explanation,
        )
