import pytest
import numpy as np
from src.heatmap.color_ramp import ColorRampEngine

def test_color_ramp_boundaries():
    # Test values: 0.1 (low), 0.70 (advisory), 0.80 (warning), 0.92 (critical)
    grid = np.array([[0.1, 0.70], [0.80, 0.92]], dtype=np.float32)
    rgba = ColorRampEngine.apply_color_ramp(grid)
    
    assert rgba.shape == (2, 2, 4)
    assert rgba.dtype == np.uint8
    
    # 0.1 should be green dominant
    r, g, b, a = rgba[0, 0]
    assert g > r and g > b
    
    # 0.70 should have strong yellow component (high R, high G)
    r, g, b, a = rgba[0, 1]
    assert r > 180 and g > 140
    
    # 0.80 should be orange (high R, moderate G)
    r, g, b, a = rgba[1, 0]
    assert r > 200 and g < 180 and b < 80
    
    # 0.92 should be red dominant
    r, g, b, a = rgba[1, 1]
    assert r > 200 and g < 100 and b < 100
