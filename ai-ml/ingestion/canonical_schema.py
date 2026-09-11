"""
Canonical SensorReading schema and adapter for SubSense AI/ML Layer.
Adheres strictly to the SubSense canonical data contract.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from .schema import GPSData, NodeHealthData, RawSensorRecord, SensorData


class ReadingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    tilt_deg: Optional[float] = Field(default=None, description="Tilt angle in degrees from MPU6050")
    vibration_rms_mm_s: Optional[float] = Field(default=None, description="Vibration RMS velocity in mm/s from MPU6050")
    displacement_mm: Optional[float] = Field(default=None, description="Displacement in mm (null for gyro-only)")
    crack_index: Optional[float] = Field(default=None, description="Crack index [0-1] (null for gyro-only)")


class SensorAvailabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tilt: bool = True
    vibration: bool = True
    displacement: bool = False
    crack: bool = False


class NodeHealthModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    battery_percent: Optional[float] = 94.0
    rssi_dbm: Optional[float] = -68.0
    hop_count: Optional[int] = 1


class CanonicalSensorReading(BaseModel):
    """
    The canonical SubSense SensorReading contract emitted by gateway-bridge
    and ingested by AI/ML service.
    """
    model_config = ConfigDict(extra="ignore")

    node_id: str = Field(min_length=1, max_length=64, description="Node identifier e.g. SS-NODE-01")
    tenant_id: Optional[str] = Field(default="tenant-jharia-01", description="Multi-tenant identifier")
    site_id: str = Field(default="PANEL7-JHARIA", description="Mine site identifier")
    zone_id: str = Field(default="PANEL-1-ZONE-01", description="Mining panel/zone identifier")
    timestamp: datetime = Field(description="ISO-8601 UTC timestamp")
    readings: ReadingsModel
    sensor_availability: SensorAvailabilityModel = Field(default_factory=SensorAvailabilityModel)
    node_health: NodeHealthModel = Field(default_factory=NodeHealthModel)


def to_raw_sensor_record(canonical: CanonicalSensorReading) -> RawSensorRecord:
    """
    Adapts a CanonicalSensorReading into the internal RawSensorRecord expected
    by the IngestionPipeline and FeaturePipeline.
    """
    # Look up or assign default mining panel GPS (Jharia Panel 7 baseline)
    gps = GPSData(
        lat=23.791204,
        lon=86.433129,
        elevation_m=210.0,
    )

    # Carry sensor availability explicitly
    avail = {
        "tilt": canonical.sensor_availability.tilt,
        "vibration": canonical.sensor_availability.vibration,
        "displacement": canonical.sensor_availability.displacement,
        "crack": canonical.sensor_availability.crack,
    }

    sensors = SensorData(
        tilt_deg=canonical.readings.tilt_deg if canonical.readings.tilt_deg is not None else 0.0,
        vibration_rms_mm_s=canonical.readings.vibration_rms_mm_s if canonical.readings.vibration_rms_mm_s is not None else 0.0,
        displacement_mm=canonical.readings.displacement_mm,
        crack_index=canonical.readings.crack_index,
    )

    # Sanitize and clamp health parameters to valid physical bounds for NodeHealthData
    raw_rssi = canonical.node_health.rssi_dbm
    if raw_rssi is None or raw_rssi < -130.0 or raw_rssi > 0.0:
        clean_rssi = -68.0
    else:
        clean_rssi = float(raw_rssi)

    raw_bat = canonical.node_health.battery_percent
    if raw_bat is None or raw_bat < 0.0 or raw_bat > 100.0:
        clean_bat = 94.0
    else:
        clean_bat = float(raw_bat)

    raw_hop = canonical.node_health.hop_count
    if raw_hop is None or raw_hop < 0 or raw_hop > 15:
        clean_hop = 1
    else:
        clean_hop = int(raw_hop)

    health = NodeHealthData(
        battery_pct=clean_bat,
        rssi_dbm=clean_rssi,
        hop_count=clean_hop,
    )

    ts = canonical.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    return RawSensorRecord(
        node_id=canonical.node_id,
        timestamp=ts,
        gps=gps,
        sensors=sensors,
        node_health=health,
        sensor_availability=avail,
    )
