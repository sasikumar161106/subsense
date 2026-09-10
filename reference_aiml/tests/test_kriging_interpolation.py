import pytest
import numpy as np
from src.geostats.variogram import SemivariogramModel
from src.geostats.ordinary_kriging import OrdinaryKrigingInterpolator

def test_semivariogram_model():
    model = SemivariogramModel(model_type="exponential", nugget=0.05, sill=1.0, range_m=200.0)
    # Zero lag
    assert model.evaluate(np.array([0.0]))[0] == 0.0
    # Lag at range
    g_range = model.evaluate(np.array([200.0]))[0]
    assert g_range > 0.5
    # Asymptotic sill at very large distance
    g_inf = model.evaluate(np.array([10000.0]))[0]
    assert np.isclose(g_inf, 1.0, atol=0.01)

def test_ordinary_kriging_interpolation():
    interpolator = OrdinaryKrigingInterpolator(grid_resolution_m=25.0)

    node_coords = {
        "N-01": (442400.0, 2631600.0),
        "N-02": (442500.0, 2631600.0),
        "N-03": (442450.0, 2631700.0),
        "N-04": (442600.0, 2631800.0),
    }

    node_values = {
        "N-01": 0.85,
        "N-02": 0.75,
        "N-03": 0.80,
        "N-04": 0.10,
    }

    bounds_utm = (442300.0, 2631500.0, 442700.0, 2631900.0)
    payload = interpolator.interpolate_raster(
        site_id="SITE-JHARIA-04",
        node_coords=node_coords,
        node_values=node_values,
        bounds_utm=bounds_utm,
    )

    assert payload.site_id == "SITE-JHARIA-04"
    assert payload.grid_width > 0
    assert payload.grid_height > 0
    assert len(payload.risk_values) == payload.grid_height
    assert len(payload.risk_values[0]) == payload.grid_width
    assert payload.variance_values is not None
    assert len(payload.variance_values) == payload.grid_height

    # Risk values should be bounded in [0.0, 1.0]
    risk_arr = np.array(payload.risk_values)
    assert np.all(risk_arr >= 0.0)
    assert np.all(risk_arr <= 1.0)
