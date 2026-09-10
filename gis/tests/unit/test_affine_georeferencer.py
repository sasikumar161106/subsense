import pytest
import math
from src.normalizer.affine_georeferencer import AffineGeoreferencer

def test_affine_forward_and_inverse():
    # Affine: rotation 1 deg, scale 1.0, translation
    a, b, c = 0.9998, -0.0175, 442000.0
    d, e, f = 0.0175, 0.9998, 2631000.0
    geo = AffineGeoreferencer(a=a, b=b, c=c, d=d, e=e, f=f)
    
    loc_x, loc_y = 1250.0, 840.0
    utm_x, utm_y = geo.local_to_utm(loc_x, loc_y)
    
    rec_x, rec_y = geo.utm_to_local(utm_x, utm_y)
    assert math.isclose(loc_x, rec_x, abs_tol=1e-4)
    assert math.isclose(loc_y, rec_y, abs_tol=1e-4)

def test_affine_calibration():
    # Synthetic tie-points with known transformation
    true_a, true_b, true_c = 1.0, 0.0, 500000.0
    true_d, true_e, true_f = 0.0, 1.0, 2500000.0
    
    tie_points = [
        {"local_x": 0.0, "local_y": 0.0, "utm_easting": true_c, "utm_northing": true_f},
        {"local_x": 1000.0, "local_y": 0.0, "utm_easting": true_c + 1000.0, "utm_northing": true_f},
        {"local_x": 0.0, "local_y": 1000.0, "utm_easting": true_c, "utm_northing": true_f + 1000.0},
        {"local_x": 1000.0, "local_y": 1000.0, "utm_easting": true_c + 1000.0, "utm_northing": true_f + 1000.0}
    ]
    
    calibrated_geo, rmse = AffineGeoreferencer.calibrate_from_tie_points(tie_points)
    assert rmse < 1e-4
    assert math.isclose(calibrated_geo.a, true_a, abs_tol=1e-4)
    assert math.isclose(calibrated_geo.b, true_b, abs_tol=1e-4)
    assert math.isclose(calibrated_geo.c, true_c, abs_tol=1e-4)
