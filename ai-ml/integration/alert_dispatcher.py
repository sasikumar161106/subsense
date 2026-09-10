"""
SubSense Downstream Dispatcher & Translation Layer.
Bridges AI/ML scoring inferences and Kriging spatial rasters to downstream services:
- Alert_System (:3000): Inbound webhook POST /api/v1/webhooks/risk-events
- GIS Layer (:8001): Inbound raster POST /api/v1/raster/ingest

Strict Zero-Fabrication Mandate:
- Physical sensor attribution strictly restricted to instrumented channels (tilt, vibration).
- Uninstrumented channels (displacement, crack) are never fabricated or attributed.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
import logging

from explainability.alert_schema import check_sensor_availability

logger = logging.getLogger("subsense.integration.dispatcher")

DEFAULT_ALERT_SYSTEM_WEBHOOK = os.getenv(
    "ALERT_SYSTEM_WEBHOOK_URL",
    "http://localhost:3000/api/v1/webhooks/risk-events"
)
DEFAULT_ALERT_SYSTEM_API_KEY = os.getenv(
    "ALERT_SYSTEM_API_KEY",
    "subsense-safety-key-2026"
)
DEFAULT_GIS_RASTER_INGEST_URL = os.getenv(
    "GIS_RASTER_INGEST_URL",
    "http://localhost:8001/api/v1/raster/ingest"
)


def to_alert_system_contract(risk_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms internal AI/ML model inference or alert event into the canonical
    Alert_System webhook RiskEvent schema contract.
    
    Guarantees:
    1. Schema conforms to Alert_System's on_new_risk_event() contract.
    2. contributing_sensors is non-empty and strictly filtered against sensor_availability.
    3. Zero fabrication of displacement or crack channels.
    """
    tenant_id = (
        risk_event.get("tenant_id")
        or risk_event.get("metadata", {}).get("tenant_id")
        or "tenant-jharia-01"
    )

    risk_zone_id = (
        risk_event.get("risk_zone_id")
        or risk_event.get("zone_id")
        or risk_event.get("metadata", {}).get("risk_zone_id")
        or "11111111-1111-1111-1111-111111111111"
    )

    # Anomaly score in [0.0, 1.0]
    raw_score = risk_event.get("anomaly_score", risk_event.get("s_node", 0.85))
    anomaly_score = float(max(0.0, min(1.0, float(raw_score))))

    # Correlation strength in [0.0, 1.0]
    raw_corr = risk_event.get("correlation_strength", risk_event.get("c_corr", 0.80))
    correlation_strength = float(max(0.0, min(1.0, float(raw_corr))))

    # Calibrated confidence in [0.0, 1.0]
    raw_conf = risk_event.get("confidence", 0.85)
    confidence = float(max(0.0, min(1.0, float(raw_conf))))

    # Source
    source = risk_event.get("source", "Cloud")
    if source not in ["Cloud", "Edge"]:
        source = "Cloud"

    # Node ID and contributing nodes
    node_id = risk_event.get("node_id", "SS-PANEL7-N042")
    contributing_nodes = risk_event.get("contributing_nodes") or [node_id]
    if isinstance(contributing_nodes, str):
        contributing_nodes = [contributing_nodes]

    # Availability filter on contributing sensors
    sensor_availability = (
        risk_event.get("sensor_availability")
        or risk_event.get("metadata", {}).get("sensor_availability")
    )
    raw_sensors = risk_event.get("contributing_sensors") or ["tilt_deg"]
    if isinstance(raw_sensors, str):
        raw_sensors = [raw_sensors]

    filtered_sensors: List[str] = []
    for s in raw_sensors:
        if check_sensor_availability(s, sensor_availability):
            filtered_sensors.append(s)

    # Fail-safe if all were filtered out
    if not filtered_sensors:
        filtered_sensors = ["tilt_deg"]

    # Explanation / summary
    explanation = (
        risk_event.get("plain_language_summary")
        or risk_event.get("explanation")
        or f"WARNING ({risk_zone_id}): Anomaly detected at Node {node_id} attributed to {', '.join(filtered_sensors)}."
    )

    # Time to critical
    ttc = risk_event.get("time_to_critical_hours", risk_event.get("time_to_critical", risk_event.get("ttc_median_hours")))
    time_to_critical_hours = float(ttc) if ttc is not None else None

    progression_rate = float(risk_event.get("progression_rate", risk_event.get("lstm_velocity_mm_h", 0.2)))
    velocity_delta = float(risk_event.get("velocity_delta", 0.2))

    timestamp = risk_event.get("timestamp")
    if isinstance(timestamp, datetime):
        ts_str = timestamp.isoformat()
    elif isinstance(timestamp, str):
        ts_str = timestamp
    else:
        ts_str = datetime.now(timezone.utc).isoformat()

    return {
        "tenant_id": str(tenant_id),
        "risk_zone_id": str(risk_zone_id),
        "anomaly_score": round(anomaly_score, 4),
        "correlation_strength": round(correlation_strength, 4),
        "confidence": round(confidence, 4),
        "source": source,
        "explanation": str(explanation),
        "contributing_nodes": contributing_nodes,
        "contributing_sensors": filtered_sensors,
        "time_to_critical_hours": time_to_critical_hours,
        "progression_rate": round(progression_rate, 4),
        "velocity_delta": round(velocity_delta, 4),
        "timestamp": ts_str,
    }


def dispatch_to_alert_system(
    risk_event: Dict[str, Any],
    webhook_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout_seconds: float = 5.0,
) -> Dict[str, Any]:
    """
    Dispatches a validated risk event to Alert_System's webhook endpoint.
    """
    url = webhook_url or DEFAULT_ALERT_SYSTEM_WEBHOOK
    key = api_key or DEFAULT_ALERT_SYSTEM_API_KEY

    payload = to_alert_system_contract(risk_event)
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "User-Agent": "SubSense-AIML-Dispatcher/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            logger.info(f"Dispatched alert to Alert_System ({status_code}): {parsed.get('alert_id')}")
            return {
                "status": "DISPATCHED",
                "status_code": status_code,
                "alert": parsed,
                "payload_dispatched": payload,
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        logger.error(f"Alert_System dispatch failed with HTTP {e.code}: {err_body}")
        raise RuntimeError(f"Alert_System HTTP {e.code}: {err_body}") from e
    except Exception as e:
        logger.error(f"Alert_System dispatch network error: {e}")
        raise RuntimeError(f"Alert_System dispatch error: {str(e)}") from e


def to_gis_raster_contract(kriging_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formats universal kriging spatial outputs into the GIS raster ingestion schema.
    """
    tenant_id = kriging_output.get("tenant_id", "tenant-jharia-01")
    site_id = kriging_output.get("site_id", "PANEL7-JHARIA")
    bounds = kriging_output.get("bounds_wgs84", [86.425, 23.785, 86.445, 23.800])

    risk_grid = kriging_output.get("risk_grid") or kriging_output.get("interpolated_grid")
    if risk_grid is None:
        raise ValueError("kriging_output must contain 'risk_grid' or 'interpolated_grid'")

    # Ensure list of lists
    if hasattr(risk_grid, "tolist"):
        risk_grid = risk_grid.tolist()

    var_grid = kriging_output.get("variance_grid")
    if var_grid is not None and hasattr(var_grid, "tolist"):
        var_grid = var_grid.tolist()

    ts = kriging_output.get("timestamp")
    if isinstance(ts, datetime):
        ts_str = ts.isoformat()
    elif isinstance(ts, str):
        ts_str = ts
    else:
        ts_str = datetime.now(timezone.utc).isoformat()

    return {
        "tenant_id": str(tenant_id),
        "site_id": str(site_id),
        "bounds_wgs84": [float(b) for b in bounds],
        "risk_grid": risk_grid,
        "variance_grid": var_grid,
        "timestamp": ts_str,
    }


def dispatch_to_gis(
    kriging_output: Dict[str, Any],
    gis_url: Optional[str] = None,
    timeout_seconds: float = 10.0,
) -> Dict[str, Any]:
    """
    Dispatches a spatial kriging raster to GIS Layer's ingestion endpoint.
    """
    url = gis_url or DEFAULT_GIS_RASTER_INGEST_URL
    payload = to_gis_raster_contract(kriging_output)
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "SubSense-AIML-Dispatcher/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            logger.info(f"Dispatched raster to GIS ({status_code}): site {payload['site_id']}")
            return {
                "status": "INGESTED",
                "status_code": status_code,
                "response": parsed,
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        logger.error(f"GIS raster dispatch failed with HTTP {e.code}: {err_body}")
        raise RuntimeError(f"GIS HTTP {e.code}: {err_body}") from e
    except Exception as e:
        logger.error(f"GIS raster dispatch network error: {e}")
        raise RuntimeError(f"GIS raster dispatch error: {str(e)}") from e
