"""
Data contract schema for raw sensor records transmitted via MQTT.
Adheres strictly to SUBSENSE-TDD-ML-004 Section 4.1.
"""

from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field, ConfigDict


class GPSData(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    lat: Annotated[float, Field(ge=-90.0, le=90.0, description="Latitude in decimal degrees")]
    lon: Annotated[float, Field(ge=-180.0, le=180.0, description="Longitude in decimal degrees")]
    elevation_m: Annotated[float, Field(ge=-500.0, le=5000.0, description="Elevation above mean sea level in meters")]


class SensorData(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    tilt_deg: Annotated[float, Field(description="Dual-axis MEMS inclinometer resultant angle in degrees")]
    vibration_rms_mm_s: Annotated[float, Field(ge=0.0, description="Triaxial high-frequency geophone velocity RMS (mm/s)")]
    displacement_mm: Annotated[float, Field(description="Extensometer / crack potentiometer movement (mm)")]
    crack_index: Annotated[float, Field(ge=0.0, le=1.0, description="Differential surface shear strain metric [0.0, 1.0]")]


class NodeHealthData(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    battery_pct: Annotated[float, Field(ge=0.0, le=100.0, description="LiFePO4 battery state-of-charge (0-100%)")]
    rssi_dbm: Annotated[float, Field(ge=-130.0, le=0.0, description="LoRa / 802.15.4 link margin in dBm")]
    hop_count: Annotated[int, Field(ge=0, le=15, description="Mesh path depth to gateway aggregator")]


class RawSensorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    node_id: Annotated[str, Field(min_length=3, max_length=64, description="Unique node identifier e.g. SS-PANEL7-N042")]
    timestamp: Annotated[datetime, Field(description="ISO-8601 UTC timestamp")]
    gps: GPSData
    sensors: SensorData
    node_health: NodeHealthData
