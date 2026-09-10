import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.delivery.tile_cache import MultiTenantTileCache

client = TestClient(app)

def test_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "DGMS" in data["compliance"]

def test_tile_endpoint_and_headers():
    # Fetch tile for Jharia at zoom 16
    response = client.get("/api/v1/tiles/tenant_corp/PANEL7-JHARIA/16/46962/30468.png?data_age_seconds=18")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-site-id"] == "PANEL7-JHARIA"
    assert response.headers["x-layer"] == "risk_deformation_heatmap"
    assert response.headers["x-tile-z"] == "16"
    assert response.headers["x-is-stale"] == "false"
    assert response.headers["x-kriging-variance-included"] == "true"
    assert "etag" in response.headers
    assert len(response.content) > 100

    # Test conditional request 304 Not Modified
    etag = response.headers["etag"]
    cond_response = client.get(
        "/api/v1/tiles/tenant_corp/PANEL7-JHARIA/16/46962/30468.png?data_age_seconds=18",
        headers={"if-none-match": etag}
    )
    assert cond_response.status_code == 304


def test_tile_staleness_header_and_watermark():
    # Fetch outdated tile (> 30s)
    response = client.get("/api/v1/tiles/tenant_corp/PANEL7-JHARIA/16/46962/30468.png?data_age_seconds=45")
    assert response.status_code == 200
    assert response.headers["x-is-stale"] == "true"

def test_live_risk_zones_geojson():
    response = client.get("/api/v1/zones/tenant_corp/PANEL7-JHARIA/live")
    assert response.status_code == 200
    geojson = response.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) > 0
    
    first_feat = geojson["features"][0]
    assert first_feat["type"] == "Feature"
    assert first_feat["id"].startswith("ZONE-")
    props = first_feat["properties"]
    assert props["site_id"] == "PANEL7-JHARIA"
    assert props["severity_tier"] in ("critical", "warning", "advisory")
    assert "centroid_gps" in props
    assert props["area_sq_meters"] >= 250.0

def test_insar_discrepancies_schema():
    response = client.get("/api/v1/insar/tenant_corp/PANEL7-JHARIA/discrepancies")
    assert response.status_code == 200
    markers = response.json()
    assert isinstance(markers, list)
    if markers:
        m = markers[0]
        assert "annotation_id" in m
        assert m["site_id"] == "PANEL7-JHARIA"
        assert "location" in m
        assert "recommended_action" in m

def test_digital_twin_scene_and_scale_ruler():
    response = client.get("/api/v1/twin/tenant_corp/PANEL7-JHARIA/scene?vertical_exaggeration=25.0")
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["site_id"] == "PANEL7-JHARIA"
    assert manifest["vertical_exaggeration"] == 25.0
    assert "dem_mesh" in manifest
    assert "scale_ruler_spec" in manifest
    assert manifest["scale_ruler_spec"]["is_standard_dgms"] is True

def test_whatif_subsidence_simulation():
    payload = {
        "panel_id": "PANEL-PROP-08",
        "site_id": "PANEL7-JHARIA",
        "extraction_method": "longwall_caving",
        "polygon_coordinates_utm": [
            [442200.0, 2631600.0],
            [442400.0, 2631600.0],
            [442400.0, 2632200.0],
            [442200.0, 2632200.0],
            [442200.0, 2631600.0]
        ],
        "seam_depth_m": 180.0,
        "seam_thickness_m": 4.5,
        "panel_width_m": 200.0,
        "panel_length_m": 600.0,
        "goaf_treatment": "caving"
    }
    response = client.post("/api/v1/simulation/what-if", json=payload)
    assert response.status_code == 200
    sim = response.json()
    assert sim["is_simulation"] is True
    assert "NON-LIVE PREDICTIVE SIMULATION" in sim["watermark_banner"]
    assert sim["max_subsidence_mm"] > 500.0
    assert "risk_delta_comparison" in sim

def test_multi_tenant_isolation():
    cache = MultiTenantTileCache()
    tile_data = b"DUMMY_TILEDATA_A"
    
    # Store under tenant_A
    cache.put_tile("tenant_A", "SITE_1", 16, 100, 200, tile_data)
    
    # tenant_A can read
    assert cache.get_tile("tenant_A", "SITE_1", 16, 100, 200) == tile_data
    
    # tenant_B CANNOT read tenant_A's tile (returns None)
    assert cache.get_tile("tenant_B", "SITE_1", 16, 100, 200) is None
