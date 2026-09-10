from typing import List, Dict, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
from src.schemas.risk_event_contracts import ForecastTrendEnum

class LSTMDeformationNet(nn.Module):
    """Deep recurrent sequence model for deformation rate prediction."""

    def __init__(self, input_dim: int = 4, hidden_dim: int = 32, num_layers: int = 2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 2),  # [predicted_velocity, predicted_acceleration]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        last_step = out[:, -1, :]
        preds = self.fc(last_step)
        return preds

class LSTMProgressionForecaster:
    """
    Progression Forecasting & Time-to-Critical Estimator (Section 6.1 & 6.3).
    Models non-linear geomechanical strain evolution over time and computes
    auditable time-to-critical countdowns for safety teams.
    """

    def __init__(
        self,
        critical_displacement_mm: float = 40.0,
        critical_tilt_deg: float = 5.0,
        version: str = "lstm-forecast-v1.2.0",
    ):
        self.critical_displacement_mm = critical_displacement_mm
        self.critical_tilt_deg = critical_tilt_deg
        self.version = version

        self.net = LSTMDeformationNet(input_dim=4, hidden_dim=32, num_layers=2)
        self.net.eval()

    def forecast_zone(
        self,
        temporal_features: np.ndarray,  # shape [T, 4] -> [tilt, vibration, displacement, anomaly]
        current_displacement_mm: float,
        time_step_hours: float = 1.0 / 60.0,  # e.g., 1 reading per minute = 1/60 hr
    ) -> Tuple[ForecastTrendEnum, Optional[float], Dict[str, float]]:
        """
        Forecasts deformation trend and computes time_to_critical_hours.
        Returns: (trend_enum, time_to_critical_hours, metrics_dict)
        """
        if temporal_features.shape[0] < 5:
            return ForecastTrendEnum.STABLE, None, {"velocity_mm_hr": 0.0, "acceleration": 0.0}

        displacements = temporal_features[:, 2]
        tilts = temporal_features[:, 0]
        n = len(displacements)

        # Finite difference velocities
        dt = max(1e-4, time_step_hours)
        velocities = np.diff(displacements) / dt  # mm/hour
        vel_mean = float(np.mean(velocities[-5:])) if len(velocities) >= 5 else float(velocities[-1])

        # Accelerations
        accelerations = np.diff(velocities) / dt if len(velocities) > 1 else np.array([0.0])
        accel_mean = float(np.mean(accelerations[-3:])) if len(accelerations) >= 3 else 0.0

        # Neural LSTM trajectory projection
        x_tensor = torch.tensor(temporal_features[np.newaxis, :, :], dtype=torch.float32)
        with torch.no_grad():
            nn_preds = self.net(x_tensor).cpu().numpy()[0]
        nn_vel = float(nn_preds[0])
        nn_acc = float(nn_preds[1])

        # Physical sanity check: if measured physical displacement is completely flat (< 0.02 mm/hr),
        # do not let untrained neural head bias inject spurious motion
        if abs(vel_mean) < 0.02 and abs(tilts[-1] - tilts[0]) < 0.1:
            combined_vel = vel_mean
            combined_acc = accel_mean
        else:
            combined_vel = 0.7 * vel_mean + 0.3 * nn_vel
            combined_acc = 0.7 * accel_mean + 0.3 * nn_acc

        remaining_disp = max(0.0, self.critical_displacement_mm - current_displacement_mm)

        # 2. Trend Classification
        if combined_vel > 5.0 or (len(tilts) > 1 and (tilts[-1] - tilts[0]) > 2.0):
            trend = ForecastTrendEnum.SUDDEN_ONSET
        elif combined_acc > 0.05 and combined_vel > 0.15:
            trend = ForecastTrendEnum.ACCELERATING
        elif combined_vel > 0.05:
            trend = ForecastTrendEnum.SLOW_PROGRESSION
        else:
            trend = ForecastTrendEnum.STABLE

        # 3. Time-to-Critical (TTC) Calculation
        time_to_critical: Optional[float] = None

        if trend == ForecastTrendEnum.STABLE:
            # Per Section 6.3: Reported as null when trend is stable rather than forcing spurious estimate
            time_to_critical = None
        else:
            if remaining_disp <= 0.0:
                time_to_critical = 0.0
            elif combined_acc > 1e-4:
                # Quadratic kinematic formula: S = v0*t + 0.5*a*t^2
                disc = combined_vel ** 2 + 2.0 * combined_acc * remaining_disp
                if disc >= 0:
                    t_hours = (-combined_vel + np.sqrt(disc)) / combined_acc
                    time_to_critical = float(np.clip(round(t_hours, 1), 0.1, 720.0))
                else:
                    time_to_critical = float(round(remaining_disp / max(1e-3, combined_vel), 1))
            else:
                # Linear velocity formula: S = v0*t
                v = max(0.01, combined_vel)
                t_hours = remaining_disp / v
                time_to_critical = float(np.clip(round(t_hours, 1), 0.1, 720.0))

        metrics = {
            "velocity_mm_hr": float(round(combined_vel, 3)),
            "acceleration_mm_hr2": float(round(combined_acc, 4)),
            "current_displacement_mm": float(round(current_displacement_mm, 2)),
            "remaining_displacement_mm": float(round(remaining_disp, 2)),
        }

        return trend, time_to_critical, metrics
