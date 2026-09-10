import pytest
from src.normalizer.cad_parser import CADMineParser

def test_synthetic_bord_and_pillar_generation():
    parser = CADMineParser()
    layout = parser.generate_synthetic_bord_and_pillar_layout(
        center_utm=(442500.0, 2632000.0),
        num_pillars_x=4,
        num_pillars_y=4
    )
    assert len(layout["pillars"]) > 0
    assert len(layout["galleries"]) > 0
    
    first_pillar = layout["pillars"][0]
    assert "coordinates_utm" in first_pillar
    assert "coordinates_wgs84" in first_pillar
    assert len(first_pillar["coordinates_utm"]) == 5
    assert first_pillar["status"] in ("intact_pillar", "depleted_goaf")
