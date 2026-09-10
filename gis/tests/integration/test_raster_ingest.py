"""
Tests for GIS Universal Kriging Raster Ingestion Endpoint (POST /api/v1/raster/ingest).
Proves:
1. AI/ML Kriging outputs are successfully ingested into GIS memory state.
2. Invalid bounds or mismatched variance matrices are rejected with 400 Bad Request.
3. Ingested rasters immediately drive slippy map tile rendering.
"""

import pytest
from fastapi.testclient import TestClient
import numpy as np

from src.api.main import app

client = TestClient(app)


def test_raster_ingest_success():
    grid_50x50 = np.full((50, 50), 0.85).tolist()
    var_50x50 = np.full((50, 50), 0.12).tolist()

    payload = {
        "tenant_id": "tenant-jharia-01",
        "site_id": "PANEL7-JHARIA",
        "bounds_wgs84": [86.425, 23.785, 86.445, 23.800],
        "risk_grid": grid_50x50,
        "variance_grid": var_50x50,
    }

    response = client.post("/api/v1/raster/ingest", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "INGESTED"
    assert data["site_id"] == "PANEL7-JHARIA"
    assert data["grid_shape"] == [50, 50]
    assert data["has_variance"] is True


def test_raster_ingest_validation_errors():
    # Invalid bounds (min >= max)
    bad_bounds_payload = {
        "tenant_id": "tenant-jharia-01",
        "site_id": "PANEL7-JHARIA",
        "bounds_wgs84": [86.445, 23.800, 86.425, 23.785],
        "risk_grid": [[0.5, 0.5], [0.5, 0.5]],
    }
    res = client.post("/api/v1/raster/ingest", json=bad_bounds_payload)
    assert res.status_code == 400

    # Dimension mismatch between risk and variance
    mismatched_payload = {
        "tenant_id": "tenant-jharia-01",
        "site_id": "PANEL7-JHARIA",
        "bounds_wgs84": [86.425, 23.785, 86.445, 23.800],
        "risk_grid": [[0.5, 0.5], [0.5, 0.5]],
        "variance_grid": [[0.1]],
    }
    res = client.post("/api/v1/raster/ingest", json=mismatched_payload)
    assert res.status_code == 400


def test_raster_ingest_drives_tile_rendering():
    # Ingest a custom raster
    grid = np.linspace(0.1, 0.9, 2500).reshape(50, 50).tolist()
    payload = {
        "tenant_id": "tenant-jharia-01",
        "site_id": "PANEL7-JHARIA",
        "bounds_wgs84": [86.425, 23.785, 86.445, 23.800],
        "risk_grid": grid,
    }
    res_ingest = client.post("/api/v1/raster/ingest", json=payload)
    assert res_ingest.status_code == 201

    # Request tile intersecting PANEL7-JHARIA bounds
    tile_res = client.get("/api/v1/tiles/tenant-jharia-01/PANEL7-JHARIA/14/12124/7016.png")
    assert tile_res.status_code == 200
    assert tile_res.headers["content-type"] == "image/png"
    assert len(tile_res.content) > 100

    # Meta query
    meta_res = client.get("/api/v1/raster/latest/PANEL7-JHARIA")
    assert meta_res.status_code == 200
    assert meta_res.json()["grid_shape"] == [50, 50]
