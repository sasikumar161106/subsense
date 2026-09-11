"""
SubSense LoRa Node Configuration
================================
LoRa radio settings, serial ports, and environment detection
matching loramain config/settings.py.
"""

import os
import sys

# Detect default serial port based on OS
def get_default_serial_port() -> str:
    env_port = os.environ.get("LORA_PORT") or os.environ.get("SERIAL_PORT")
    if env_port:
        return env_port

    if os.name == "nt":
        return "COM5"

    # Linux / Raspberry Pi common ports
    for dev in ["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyS0", "/dev/ttyAMA0", "/dev/serial0"]:
        if os.path.exists(dev):
            return dev
    return "/dev/ttyS0"


SERIAL_PORT = get_default_serial_port()

# LoRa Radio Settings (Matching loramain settings.py for SX126x / E22-900T22S)
LORA_SETTINGS = {
    "FREQUENCY": int(os.environ.get("LORA_FREQ", "865")),  # 865 MHz India ISM band
    "TX_POWER": 22,                                       # Max power (dBm)
    "BANDWIDTH": 125.0,                                   # kHz
    "SPREADING_FACTOR": 9,                                # Higher = More Range
    "CODING_RATE": 5,                                     # 4/5 error correction
    "AIR_SPEED": 2400,                                    # 2400 bps over the air
    "UART_BAUD": 9600,                                    # 9600 baud module UART interface
}

# SubSense Platform Backend Endpoints
AIML_INGEST_URL = os.environ.get("AIML_INGEST_URL", "http://localhost:8000/api/v1/ingest/telemetry")
BFF_BROADCAST_URL = os.environ.get("BFF_BROADCAST_URL", "http://localhost:3001/api/v1/telemetry/broadcast")

# Default Metadata
DEFAULT_NODE_ID = os.environ.get("NODE_ID", "SS-PANEL7-N042")
DEFAULT_SITE_ID = os.environ.get("SITE_ID", "PANEL7-JHARIA")
DEFAULT_TENANT_ID = os.environ.get("TENANT_ID", "tenant-jharia-01")
DEFAULT_ZONE_ID = os.environ.get("ZONE_ID", "PANEL-7-WEST")

# Mining Safety Thresholds
PHYSICAL_TILT_CRITICAL_DEG = 4.0
PHYSICAL_VIB_CRITICAL_MM_S = 2.5
