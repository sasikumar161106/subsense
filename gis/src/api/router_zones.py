from fastapi import APIRouter, Query
from typing import Optional
from shapely.geometry import Polygon

from src.risk_zones.zone_tracker import ZoneTracker
from src.risk_zones.polygon_smoother import PolygonSmoother
from src.schemas.risk_zone_contracts import RiskZoneFeatureCollection
from src.delivery.postgis_repository import SpatialRepository

router = APIRouter(prefix="/api/v1/zones", tags=["Risk-Zone Boundary Engine (5.2)"])

# State tracking per site
_trackers: dict[str, ZoneTracker] = {}
spatial_repo = SpatialRepository()

def _get_tracker(site_id: str) -> ZoneTracker:
    if site_id not in _trackers:
        _trackers[site_id] = ZoneTracker(site_id=site_id)
    return _trackers[site_id]

@router.get("/{tenant_id}/{site_id}/live", response_model=RiskZoneFeatureCollection)
async def get_live_risk_zones(tenant_id: str, site_id: str):
    """
    Returns active risk-zone boundaries as a GeoJSON FeatureCollection (Section 6.2).
    Applies Jaccard IoU tracking to ensure stable zone identifiers.
    """
    tracker = _get_tracker(site_id)

    # Synthetic candidate isoline polygons in UTM for demonstration
    # In production, these come from ContourExtractor
    poly_crit = Polygon([(442400, 2631600), (442550, 2631620), (442520, 2631750), (442380, 2631720), (442400, 2631600)])
    poly_warn = Polygon([(442300, 2631500), (442650, 2631530), (442620, 2631850), (442270, 2631810), (442300, 2631500)])
    poly_advi = Polygon([(442200, 2631400), (442750, 2631450), (442720, 2631950), (442170, 2631900), (442200, 2631400)])

    smoothed_crit = PolygonSmoother.filter_and_smooth([poly_crit], min_area_sq_m=250.0)
    smoothed_warn = PolygonSmoother.filter_and_smooth([poly_warn], min_area_sq_m=250.0)
    smoothed_advi = PolygonSmoother.filter_and_smooth([poly_advi], min_area_sq_m=250.0)

    extracted = {
        "critical": smoothed_crit,
        "warning": smoothed_warn,
        "advisory": smoothed_advi
    }

    sensor_nodes = [
        {"id": f"SS-{site_id}-N042", "lat": 23.7915, "lon": 86.4335},
        {"id": f"SS-{site_id}-N043", "lat": 23.7920, "lon": 86.4340},
        {"id": f"SS-{site_id}-N051", "lat": 23.7910, "lon": 86.4330}
    ]

    collection = tracker.process_cycle(extracted, sensor_nodes=sensor_nodes)
    collection.tenant_id = tenant_id
    collection.site_id = site_id

    # Persist in spatial repository
    spatial_repo.save_cycle_zones(tenant_id, site_id, collection)

    return collection
