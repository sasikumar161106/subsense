import pytest
import numpy as np
from src.insar.insar_cross_validator import InSARCrossValidator
from data.synthetic_generator import SyntheticSubsidenceDataGenerator

def test_insar_cross_validation():
    validator = InSARCrossValidator(unmonitored_threshold_mm_year=-18.0)
    gen = SyntheticSubsidenceDataGenerator()

    bounds_utm = (442000.0, 2631200.0, 443000.0, 2632200.0)

    # InSAR grid with a significant subsidence basin at far edge
    insar_grid = gen.generate_synthetic_insar_grid(
        bounds_utm=bounds_utm,
        grid_shape=(20, 20),
        basin_center_utm=(442100.0, 2631300.0), # Outside ground mesh
        max_los_velocity=-32.0,                  # Strong subsidence
    )

    # Ground mesh is centered further north-east
    ground_coords = {
        "N-01": (442600.0, 2631800.0),
        "N-02": (442650.0, 2631850.0),
    }
    ground_risk = np.zeros((20, 20), dtype=np.float32)

    overlay = validator.cross_validate(
        site_id="SITE-JHARIA-04",
        insar_velocity_grid=insar_grid,
        bounds_utm=bounds_utm,
        ground_mesh_coords=ground_coords,
        ground_risk_grid=ground_risk,
        pass_date="2026-09-08",
    )

    assert overlay.site_id == "SITE-JHARIA-04"
    assert overlay.satellite_mission == "Sentinel-1A"
    assert len(overlay.markers) >= 1

    marker = overlay.markers[0]
    assert marker.discrepancy_type == "satellite_motion_unmonitored_by_ground_mesh"
    assert marker.los_velocity_mm_year < -18.0
    assert "outside active ground mesh" in marker.description
