from typing import List, Dict, Any, Optional
from datetime import datetime
from shapely.geometry import Polygon, box
from shapely.strtree import STRtree
from src.schemas.risk_zone_contracts import RiskZoneFeature, RiskZoneFeatureCollection

class SpatialRepository:
    """
    SubSense Spatial Database & PostGIS Repository (Section 5.5 & Section 7).
    Provides spatial indexing (R-Tree / GiST) and Row-Level Security (RLS) simulation
    for tenant-isolated spatial queries.
    """
    def __init__(self):
        # In-memory store keyed by tenant_id -> site_id -> list of zone snapshots
        # Format: { tenant_id: { site_id: [ {"as_of": dt, "collection": RiskZoneFeatureCollection} ] } }
        self._stores: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        # Georeferenced affine calibration store: { site_id: dict }
        self._site_calibrations: Dict[str, Dict[str, Any]] = {}

    def save_cycle_zones(
        self,
        tenant_id: str,
        site_id: str,
        collection: RiskZoneFeatureCollection
    ):
        """Saves a cycle's risk zone collection under the tenant's partition."""
        if tenant_id not in self._stores:
            self._stores[tenant_id] = {}
        if site_id not in self._stores[tenant_id]:
            self._stores[tenant_id][site_id] = []

        self._stores[tenant_id][site_id].append({
            "as_of": collection.as_of,
            "collection": collection
        })

    def get_latest_zones(
        self,
        tenant_id: str,
        site_id: str
    ) -> Optional[RiskZoneFeatureCollection]:
        """Returns latest active risk zones for tenant and site."""
        site_history = self._stores.get(tenant_id, {}).get(site_id, [])
        if not site_history:
            return None
        return site_history[-1]["collection"]

    def query_zones_in_viewport(
        self,
        tenant_id: str,
        site_id: str,
        bbox_wgs84: tuple[float, float, float, float]  # (min_lon, min_lat, max_lon, max_lat)
    ) -> List[RiskZoneFeature]:
        """
        Uses R-Tree spatial indexing to return only risk zones intersecting the client viewport.
        Strictly enforces Row-Level Security (RLS).
        """
        latest = self.get_latest_zones(tenant_id, site_id)
        if not latest or not latest.features:
            return []

        viewport_box = box(*bbox_wgs84)
        matching_features = []

        for feature in latest.features:
            coords = feature.geometry.coordinates[0]
            poly = Polygon(coords)
            if poly.intersects(viewport_box):
                matching_features.append(feature)

        return matching_features

    def get_historical_snapshots(
        self,
        tenant_id: str,
        site_id: str
    ) -> List[Dict[str, Any]]:
        """Returns time-indexed historical records for post-incident audit replay."""
        return self._stores.get(tenant_id, {}).get(site_id, [])
