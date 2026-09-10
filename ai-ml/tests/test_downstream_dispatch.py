"""
Tests for AI/ML Downstream Dispatch & Contract Translation (Phase 2b).
Verifies:
1. to_alert_system_contract translates AI/ML inferences to Alert_System webhook contract.
2. Sensor attribution respects zero-fabrication (displacement/crack filtered out).
3. to_gis_raster_contract translates Kriging interpolations to GIS raster ingestion schema.
4. HTTP dispatchers properly handle request construction, headers, and responses.
5. FastAPI serving endpoints /api/v1/alerts/dispatch and /api/v1/raster/dispatch work as expected.
"""

from unittest.mock import patch, MagicMock
from io import BytesIO
import json
import pytest
from fastapi.testclient import TestClient

from integration.alert_dispatcher import (
    to_alert_system_contract,
    dispatch_to_alert_system,
    to_gis_raster_contract,
    dispatch_to_gis,
)
from models.serving.app import app

client = TestClient(app)


def test_to_alert_system_contract_gyro_only():
    ai_event = {
        "node_id": "SS-PANEL7-N042",
        "anomaly_score": 0.88,
        "c_corr": 0.82,
        "confidence": 0.90,
        "contributing_sensors": ["tilt_deg", "displacement_mm", "vibration_rms_mm_s"],
        "plain_language_summary": "WARNING (Zone 3B): Tilt surge (+4.20°) and high RMS vibration detected.",
        "sensor_availability": {
            "tilt": True,
            "vibration": True,
            "displacement": False,
            "crack": False,
        },
    }

    contract = to_alert_system_contract(ai_event)

    assert contract["tenant_id"] == "tenant-jharia-01"
    assert contract["anomaly_score"] == 0.88
    assert contract["correlation_strength"] == 0.82
    assert contract["confidence"] == 0.90
    assert contract["source"] == "Cloud"
    assert contract["contributing_nodes"] == ["SS-PANEL7-N042"]
    # Zero-fabrication check: displacement_mm MUST have been stripped
    assert "displacement_mm" not in contract["contributing_sensors"]
    assert "tilt_deg" in contract["contributing_sensors"]
    assert "vibration_rms_mm_s" in contract["contributing_sensors"]
    assert len(contract["explanation"]) > 10


def test_dispatch_to_alert_system_mock():
    mock_alert_response = {
        "alert_id": "ALERT-2026-TEST-001",
        "severity": "Warning",
        "status": "Active",
    }

    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 201
    mock_resp.read.return_value = json.dumps(mock_alert_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        result = dispatch_to_alert_system({
            "node_id": "SS-PANEL7-N042",
            "anomaly_score": 0.85,
            "plain_language_summary": "Warning: High vibration and tilt detected.",
        })

        assert result["status"] == "DISPATCHED"
        assert result["status_code"] == 201
        assert result["alert"]["alert_id"] == "ALERT-2026-TEST-001"
        mock_urlopen.assert_called_once()


def test_to_gis_raster_contract():
    kriging_output = {
        "tenant_id": "tenant-jharia-01",
        "site_id": "PANEL7-JHARIA",
        "bounds_wgs84": [86.425, 23.785, 86.445, 23.800],
        "risk_grid": [[0.1, 0.2], [0.3, 0.4]],
        "variance_grid": [[0.01, 0.02], [0.03, 0.04]],
    }

    raster_payload = to_gis_raster_contract(kriging_output)

    assert raster_payload["tenant_id"] == "tenant-jharia-01"
    assert raster_payload["site_id"] == "PANEL7-JHARIA"
    assert raster_payload["bounds_wgs84"] == [86.425, 23.785, 86.445, 23.800]
    assert raster_payload["risk_grid"] == [[0.1, 0.2], [0.3, 0.4]]
    assert raster_payload["variance_grid"] == [[0.01, 0.02], [0.03, 0.04]]


def test_dispatch_to_gis_mock():
    mock_gis_response = {
        "status": "INGESTED",
        "site_id": "PANEL7-JHARIA",
        "grid_shape": [2, 2],
    }

    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 201
    mock_resp.read.return_value = json.dumps(mock_gis_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        result = dispatch_to_gis({
            "site_id": "PANEL7-JHARIA",
            "risk_grid": [[0.5, 0.5], [0.5, 0.5]],
        })

        assert result["status"] == "INGESTED"
        assert result["status_code"] == 201
        mock_urlopen.assert_called_once()


def test_fastapi_dispatch_endpoints():
    with patch("models.serving.app.dispatch_to_alert_system") as mock_alert_disp:
        mock_alert_disp.return_value = {"status": "DISPATCHED", "alert_id": "ALT-123"}
        res = client.post("/api/v1/alerts/dispatch", json={"node_id": "SS-PANEL7-N042", "anomaly_score": 0.85})
        assert res.status_code == 200
        assert res.json()["status"] == "DISPATCHED"

    with patch("models.serving.app.dispatch_to_gis") as mock_gis_disp:
        mock_gis_disp.return_value = {"status": "INGESTED", "site_id": "PANEL7-JHARIA"}
        res = client.post("/api/v1/raster/dispatch", json={"site_id": "PANEL7-JHARIA", "risk_grid": [[0.5]]})
        assert res.status_code == 200
        assert res.json()["status"] == "INGESTED"
