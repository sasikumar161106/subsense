import pytest
import numpy as np
from shapely.geometry import Polygon
from src.risk_zones.contour_extractor import ContourExtractor
from src.risk_zones.polygon_smoother import PolygonSmoother
from src.risk_zones.zone_tracker import ZoneTracker

def test_contour_extraction_and_area_filter():
    # Create 100x100 grid with a high-risk bell curve in the center
    # spanning 500m x 500m in UTM
    y, x = np.ogrid[:100, :100]
    center_y, center_x = 50, 50
    dist_sq = (x - center_x) ** 2 + (y - center_y) ** 2
    # Risk peak at center = 0.95, decaying outward
    risk_grid = 0.95 * np.exp(-dist_sq / 300.0).astype(np.float32)
    
    bounds_utm = (442000.0, 2631000.0, 443000.0, 2632000.0)
    
    extracted = ContourExtractor.extract_isolines(risk_grid, bounds_utm)
    assert "critical" in extracted
    assert len(extracted["critical"]) > 0
    
    # Smooth & filter
    smoothed = PolygonSmoother.filter_and_smooth(extracted["critical"], min_area_sq_m=250.0)
    assert len(smoothed) > 0
    for p in smoothed:
        assert p.area >= 250.0
        assert p.is_valid

def test_zone_persistence_stability():
    # Test that consecutive cycles with slight shift keep the same zone ID (IoU >= 0.40)
    tracker = ZoneTracker(site_id="PANEL7-JHARIA")
    
    # Cycle 1: Zone at (1000, 1000) with size 100x100
    poly1 = Polygon([(1000, 1000), (1100, 1000), (1100, 1100), (1000, 1100), (1000, 1000)])
    cycle1_features = tracker.process_cycle({"warning": [poly1]})
    assert len(cycle1_features.features) == 1
    initial_id = cycle1_features.features[0].id
    
    # Cycle 2: Shifted by 15 meters (overlap IoU should be high ~0.74)
    poly2 = Polygon([(1015, 1010), (1115, 1010), (1115, 1110), (1015, 1110), (1015, 1010)])
    cycle2_features = tracker.process_cycle({"warning": [poly2]})
    assert len(cycle2_features.features) == 1
    retained_id = cycle2_features.features[0].id
    
    # ID MUST persist across cycles!
    assert retained_id == initial_id
