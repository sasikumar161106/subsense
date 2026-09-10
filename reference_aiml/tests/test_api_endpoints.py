import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
import numpy as np

from src.api.main import app
from data.synthetic_generator import SyntheticSubsidenceDataGenerator

client = TestClient(app)

def test_api_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "SubSense AI/ML Data Inference Layer" in data["service"]

def test_api_health():
    response = client.get("/api/v1/inference/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "active_model_versions" in data

def test_api_kriging_surface():
    payload = {
        "site_id": "SITE-JHARIA-04",
        "node_coords": {
            "N-01": [442420.0, 2631650.0],
            "N-02": [442480.0, 2631680.0],
            "N-03": [442450.0, 2631720.0],
        },
        "node_values": {
            "N-01": 0.85,
            "N-02": 0.78,
            "N-03": 0.81,
        },
        "bounds_utm": [442400.0, 2631600.0, 442550.0, 2631750.0],
        "utm_epsg": 32645,
        "grid_resolution_m": 25.0
    }
    response = client.post("/api/v1/kriging/surface", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["site_id"] == "SITE-JHARIA-04"
    assert len(data["risk_values"]) > 0
    assert len(data["variance_values"]) > 0

def test_api_insar_cross_validate():
    payload = {
        "site_id": "SITE-JHARIA-04",
        "insar_velocity_grid": [
            [-25.0, -22.0, -10.0],
            [-28.0, -30.0, -15.0],
            [-5.0, -2.0, 0.0]
        ],
        "bounds_utm": [442000.0, 2631200.0, 443000.0, 2632200.0],
        "ground_mesh_coords": {
            "N-01": [442500.0, 2631700.0]
        },
        "ground_risk_grid": [
            [0.1, 0.1, 0.1],
            [0.1, 0.1, 0.1],
            [0.1, 0.1, 0.1]
        ],
        "pass_date": "2026-09-08"
    }
    response = client.post("/api/v1/insar/cross-validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["site_id"] == "SITE-JHARIA-04"
    assert "markers" in data
    assert data["satellite_mission"] == "Sentinel-1A"

def test_api_feedback_lifecycle():
    fb_payload = {
        "feedback_id": "FB-TEST-001",
        "alert_id": "ALT-001",
        "site_id": "SITE-JHARIA-04",
        "zone_id": "PANEL-7-NE",
        "operator_id": "SAFETY-OFFICER-01",
        "feedback_type": "false_positive",
        "geotechnical_notes": "Blasting vibration caused momentary tilt trip.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    res = client.post("/api/v1/feedback/submit", json=fb_payload)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "processed"
    assert res_data["updated_effective_threshold"] > 0.60

    # Registry history
    res_reg = client.get("/api/v1/feedback/models/registry")
    assert res_reg.status_code == 200
    assert len(res_reg.json()) >= 3

    # Manual retrain trigger
    res_retrain = client.post("/api/v1/feedback/retrain/trigger")
    assert res_retrain.status_code == 200
    assert res_retrain.json()["status"] == "completed"

    # Rollback to baseline
    rb_payload = {
        "model_family": "anomaly",
        "target_version": "cloud-ensemble-v2.1.0"
    }
    res_rb = client.post("/api/v1/feedback/models/rollback", json=rb_payload)
    assert res_rb.status_code == 200
    assert res_rb.json()["status"] == "success"
