import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.insar.insar_decomposition import InSARDecompositionEngine
from src.digital_twin.cross_section import StratigraphicCrossSectionEngine

client = TestClient(app)

def test_insar_dual_pass_decomposition():
    # Synthetic ascending and descending LOS rates
    # When ground subsides, both ascending and descending LOS show negative velocities (moving away from satellite)
    asc_vel = -28.0
    desc_vel = -32.0
    
    decomp = InSARDecompositionEngine.decompose_los_to_2d(
        los_vel_asc_mm_yr=asc_vel,
        los_vel_desc_mm_yr=desc_vel,
        coherence_asc=0.75,
        coherence_desc=0.70
    )
    assert decomp["is_valid"] is True
    assert decomp["is_subsiding"] is True
    assert decomp["vertical_velocity_mm_year"] < 0.0
    assert "shear_direction" in decomp

    # Test decorrelated filtering (< 0.35 coherence)
    decorr = InSARDecompositionEngine.decompose_los_to_2d(
        los_vel_asc_mm_yr=asc_vel,
        los_vel_desc_mm_yr=desc_vel,
        coherence_asc=0.20,
        coherence_desc=0.70
    )
    assert decorr["is_valid"] is False
    assert decorr["status"] == "DECORRELATED_FILTERED"

def test_insar_decomposition_api():
    response = client.get(
        "/api/v1/insar/tenant_alpha/PANEL7-JHARIA/decomposition?los_asc_mm_yr=-25.0&los_desc_mm_yr=-30.0&coherence=0.8"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert "vertical_velocity_mm_year" in data

def test_stratigraphic_cross_section_api():
    response = client.get(
        "/api/v1/twin/tenant_alpha/PANEL7-JHARIA/cross-section?x1=442000&y1=2631500&x2=442800&y2=2631500&vertical_exaggeration=25.0"
    )
    assert response.status_code == 200
    data = response.json()
    assert "profile_points" in data
    assert len(data["profile_points"]) > 10
    first_pt = data["profile_points"][0]
    assert "surface_baseline_m" in first_pt
    assert "surface_deformed_m" in first_pt
    assert "seam_roof_m" in first_pt
    assert len(data["lithology_units"]) == 4

def test_sse_event_stream_endpoint():
    # Verify stream connects and returns text/event-stream content type
    with client.stream("GET", "/api/v1/stream/tenant_alpha/PANEL7-JHARIA/events?max_cycles=1") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        for chunk in response.iter_lines():
            if chunk.startswith("event:"):
                assert "cycle_published" in chunk
                break

