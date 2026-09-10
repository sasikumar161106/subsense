import pytest
import math
from src.normalizer.crs_normalizer import SpatialDataNormalizer

def test_wgs84_utm_roundtrip():
    # Jharia Coalfield coordinates: 86.4335 E, 23.7915 N
    normalizer = SpatialDataNormalizer(target_utm_epsg=32645)
    orig_lon, orig_lat = 86.4335, 23.7915
    
    easting, northing = normalizer.wgs84_to_utm(orig_lon, orig_lat)
    assert easting > 400000.0
    assert northing > 2600000.0
    
    ret_lon, ret_lat = normalizer.utm_to_wgs84(easting, northing)
    assert math.isclose(orig_lon, ret_lon, abs_tol=1e-6)
    assert math.isclose(orig_lat, ret_lat, abs_tol=1e-6)

def test_slippy_tile_math():
    lat, lon = 23.7915, 86.4335
    z = 16
    x, y = SpatialDataNormalizer.lat_lon_to_tile(lat, lon, z)
    assert x > 0
    assert y > 0
    
    # Bounding box must contain the original point
    min_lon, min_lat, max_lon, max_lat = SpatialDataNormalizer.tile_to_bounds_wgs84(z, x, y)
    assert min_lon <= lon <= max_lon
    assert min_lat <= lat <= max_lat

def test_geojson_transform():
    normalizer = SpatialDataNormalizer(target_utm_epsg=32645)
    geojson_poly = {
        "type": "Polygon",
        "coordinates": [[[86.43, 23.79], [86.44, 23.79], [86.44, 23.80], [86.43, 23.80], [86.43, 23.79]]]
    }
    utm_poly = normalizer.transform_geojson_geometry(geojson_poly, target="utm")
    assert utm_poly["type"] == "Polygon"
    first_coord = utm_poly["coordinates"][0][0]
    assert first_coord[0] > 400000.0
