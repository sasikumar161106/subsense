"""
SubSense Gateway Bridge Root Module Facade
===========================================
Allows direct, clean importing (`import bridge` / `from bridge import ...`)
from any package or test within the SubSense workspace without requiring
dynamic sys.path hacking, while ensuring 100% static analysis resolution.
"""

import os
import sys
from typing import Any, Dict, Generator, List, Optional, Tuple

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_GW_DIR = os.path.join(_CURRENT_DIR, "gateway-bridge")
if _GW_DIR not in sys.path:
    sys.path.insert(0, _GW_DIR)

import importlib.util

_bridge_path = os.path.join(_GW_DIR, "bridge.py")
_spec = importlib.util.spec_from_file_location("gateway_bridge_module", _bridge_path)
if _spec and _spec.loader:
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    to_canonical = _mod.to_canonical
    format_timestamp = _mod.format_timestamp
    OfflineQueue = _mod.OfflineQueue
    SerialJSONExtractor = _mod.SerialJSONExtractor
    GatewayBridge = _mod.GatewayBridge

    DEFAULT_PORT = getattr(_mod, "DEFAULT_PORT", "COM5")
    DEFAULT_BAUD = getattr(_mod, "DEFAULT_BAUD", 115200)
    DEFAULT_INGEST_URL = getattr(_mod, "DEFAULT_INGEST_URL", "http://localhost:8000/api/v1/ingest/telemetry")
    DEFAULT_BFF_URL = getattr(_mod, "DEFAULT_BFF_URL", "http://localhost:3001/api/v1/telemetry/broadcast")
    DEFAULT_DB_PATH = getattr(_mod, "DEFAULT_DB_PATH", os.path.join(_GW_DIR, "offline_queue.db"))
else:
    raise ImportError(f"Could not load gateway bridge module from {_bridge_path}")
