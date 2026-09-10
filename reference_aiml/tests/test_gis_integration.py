import pytest
from datetime import datetime, timezone
from src.schemas.gis_interop_contracts import IngestionRasterPayload, RiskZoneFeature, RiskZoneProperties, CentroidGPS, PolygonGeometry
from src.geostats.ordinary_kriging import OrdinaryKrigingInterpolator

def test_kriging_payload_gis_compatibility():
    interpolator = OrdinaryKrigingInterpolator(grid_resolution_m=20.0)
    node_coords = {
        "N-014": (442420.0, 2631650.0),
        "N-015": (442480.0, 2631680.0),
        "N-021": (442450.0, 2631720.0),
    }
    node_values = {
        "N-014": 0.81,
        "N-015": 0.76,
        "N-021": 0.85,
    }
    bounds = (442400.0, 2631600.0, 442550.0, 2631750.0)

    payload = interpolator.interpolate_raster(
        site_id="SITE-JHARIA-04",
        node_coords=node_coords,
        node_values=node_values,
        bounds_utm=bounds,
        utm_epsg=32645,
    )

    # Validate JSON serialization matches Layer 5 expectation
    data = payload.model_dump()
    assert data["site_id"] == "SITE-JHARIA-04"
    assert data["utm_epsg"] == 32645
    assert len(data["bounds_utm"]) == 4
    assert len(data["risk_values"]) > 0
    assert len(data["variance_values"]) > 0

def test_risk_zone_feature_schema():
    feature = RiskZoneFeature(
        id="ZONE-PANEL7-C",
        properties=RiskZoneProperties(
            site_id="SITE-JHARIA-04",
            zone_name="Goaf Abutment Zone C",
            severity_tier="warning",
            time_to_critical_hours=(24.0, 48.0),
            model_confidence=0.87,
            affected_node_ids=["N-014", "N-015", "N-021"],
            primary_contributing_sensors=["tilt", "vibration", "crack"],
            explanation_summary="Correlated tilt and crack rise across 3 nodes.",
            area_sq_meters=450.0,
            centroid_gps=CentroidGPS(lat=23.7915, lon=86.4335),
            last_updated=datetime.now(timezone.utc),
        ),
        geometry=PolygonGeometry(
            coordinates=[[[86.433, 23.791], [86.434, 23.791], [86.434, 23.792], [86.433, 23.792], [86.433, 23.791]]]
        )
    )

    assert feature.properties.severity_tier == "warning"
    assert feature.properties.area_sq_meters >= 250.0
