from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class SensorReading(BaseModel):
    """Raw telemetry packet arriving from sensor mesh node via gateway uplink."""
    node_id: str = Field(..., description="Unique node identifier e.g. N-014")
    timestamp: datetime = Field(..., description="ISO 8601 UTC timestamp of measurement")
    tilt_deg: float = Field(..., description="Tilt/inclination angle in degrees from normal")
    vibration_g: float = Field(..., description="Tri-axial combined vibration acceleration in g")
    displacement_mm: float = Field(..., description="Surface strain / displacement in millimeters")
    crack_sensor_active: bool = Field(default=False, description="Crack gauge open circuit indicator")

class NodeHealthMetadata(BaseModel):
    """Hardware diagnostic telemetry used for sensor-fault filtering (Section 3.3)."""
    node_id: str = Field(..., description="Unique node identifier")
    timestamp: datetime = Field(..., description="Last-seen timestamp")
    battery_voltage: float = Field(..., description="Battery voltage level in Volts (e.g. 3.3V)")
    rssi_dbm: float = Field(..., description="Received Signal Strength Indicator in dBm")
    packet_loss_pct: float = Field(default=0.0, description="Packet error/drop percentage")
    is_faulty: bool = Field(default=False, description="Whether node is quarantined for hardware fault")

class SlidingWindow(BaseModel):
    """Window buffer of historical samples for a single node."""
    node_id: str
    readings: List[SensorReading] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class EngineeredFeatureVector(BaseModel):
    """Engineered statistical and physical features over a sliding window (Section 3.2)."""
    node_id: str
    timestamp: datetime
    # Tilt features
    tilt_mean: float = Field(..., description="Mean tilt angle over window")
    tilt_rate: float = Field(..., description="Rate of change in tilt angle (deg/min or deg/step)")
    tilt_var_short: float = Field(..., description="Short-window variance of tilt")
    tilt_var_long: float = Field(..., description="Long-window variance of tilt")
    # Vibration features
    vibration_rms: float = Field(..., description="Root Mean Square vibration amplitude")
    vibration_peak_ratio: float = Field(..., description="Peak vibration divided by RMS baseline")
    # Displacement features
    displacement_delta: float = Field(..., description="Displacement change relative to baseline")
    displacement_cum_drift: float = Field(..., description="Cumulative displacement drift in mm")
    # Crack feature
    crack_active_ratio: float = Field(..., description="Fraction of window where crack sensor is active")

    def to_feature_list(self) -> List[float]:
        return [
            self.tilt_mean,
            self.tilt_rate,
            self.tilt_var_short,
            self.tilt_var_long,
            self.vibration_rms,
            self.vibration_peak_ratio,
            self.displacement_delta,
            self.displacement_cum_drift,
        ]
