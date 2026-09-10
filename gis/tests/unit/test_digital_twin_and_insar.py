import pytest
import numpy as np
from src.digital_twin.dem_draper import DEMTerrainDraper
from src.digital_twin.subsurface_mesh import SubsurfaceMeshBuilder
from src.digital_twin.vertical_exaggeration import VerticalExaggerationEngine
from src.insar.insar_overlay import InSAROverlayEngine
from src.insar.discrepancy_engine import InSARDiscrepancyEngine

def test_dem_draper_mesh():
    draper = DEMTerrainDraper()
    bounds = (442000.0, 2631000.0, 442500.0, 2631500.0)
    mesh = draper.generate_surface_dem_mesh(bounds, grid_resolution_m=50.0)
    
    assert mesh["vertex_count"] > 0
    assert mesh["triangle_count"] > 0
    assert len(mesh["vertices_utm"]) == mesh["vertex_count"]
    assert len(mesh["vertices_wgs84"]) == mesh["vertex_count"]
    assert mesh["elevation_max_m"] >= mesh["elevation_min_m"]

def test_vertical_exaggeration_engine():
    base_z = np.array([220.0, 220.0, 220.0])
    subs_mm = np.array([0.0, 50.0, 100.0])
    
    # Exaggeration 25x
    # 100 mm = 0.1 m -> 0.1 * 25 = 2.5 m display displacement
    z_disp = VerticalExaggerationEngine.apply_exaggeration(base_z, subs_mm, factor=25.0)
    assert np.isclose(z_disp[0], 220.0)
    assert np.isclose(z_disp[1], 220.0 - 1.25)
    assert np.isclose(z_disp[2], 220.0 - 2.50)
    
    ruler_spec = VerticalExaggerationEngine.generate_scale_ruler_spec(25.0)
    assert ruler_spec["factor"] == 25.0
    assert ruler_spec["is_standard_dgms"] is True

def test_insar_discrepancy_and_overlay():
    overlay_eng = InSAROverlayEngine()
    basins = [{
        "basin_id": "INSAR-BASIN-01",
        "los_velocity_mm_year": -34.5,
        "coordinates_wgs84": [[[86.434, 23.792], [86.436, 23.792], [86.436, 23.794], [86.434, 23.794], [86.434, 23.792]]]
    }]
    geojson = overlay_eng.generate_hatched_basin_geojson("PANEL7-JHARIA", "2026-08-28", basins)
    assert len(geojson["features"]) == 1
    assert geojson["features"][0]["properties"]["style"]["fill_pattern"] == "diagonal_hatch_45deg"
    
    # Ground mesh far away from the basin
    nodes = [{"id": "N001", "lon": 86.420, "lat": 23.780}]
    markers = InSARDiscrepancyEngine.detect_discrepancies("PANEL7-JHARIA", basins, nodes)
    assert len(markers) == 1
    m = markers[0]
    assert m.annotation_id.startswith("INSAR-DISC-")
    assert m.site_id == "PANEL7-JHARIA"
    assert m.discrepancy_type == "satellite_motion_unmonitored_by_ground_mesh"
