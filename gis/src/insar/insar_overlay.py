from typing import Dict, Any, List, Optional
from shapely.geometry import Polygon, mapping
from src.normalizer.crs_normalizer import SpatialDataNormalizer

class InSAROverlayEngine:
    """
    SubSense Sentinel-1 InSAR Hatched Vector Overlay Engine (Section 5.4 & Section 9).
    Renders macro-scale Line-of-Sight (LOS) satellite displacement basins using
    distinct hatched styling to prevent visual confusion with real-time ground sensor heatmaps.
    """
    def __init__(self, normalizer: Optional[SpatialDataNormalizer] = None):
        self.normalizer = normalizer or SpatialDataNormalizer()

    def generate_hatched_basin_geojson(
        self,
        site_id: str,
        acquisition_date: str,
        basins: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generates GeoJSON FeatureCollection with hatched styling properties
        and temporal warning badges for InSAR satellite passes.
        """
        features = []

        for b in basins:
            coords_wgs84 = b["coordinates_wgs84"]
            poly = Polygon(coords_wgs84[0])
            los_velocity = b.get("los_velocity_mm_year", -28.0)
            basin_id = b.get("basin_id", f"INSAR-BASIN-{acquisition_date}")

            features.append({
                "type": "Feature",
                "id": basin_id,
                "properties": {
                    "site_id": site_id,
                    "layer_type": "sentinel1_insar_macro",
                    "acquisition_date": acquisition_date,
                    "los_velocity_mm_year": los_velocity,
                    "satellite_pass": "Sentinel-1A IW Descending",
                    "temporal_cadence": "12-day historical interferogram",
                    "style": {
                        "fill_pattern": "diagonal_hatch_45deg",
                        "hatch_color": "#38bdf8",  # Sky blue hatching
                        "hatch_spacing_px": 8,
                        "stroke_color": "#0284c7",
                        "stroke_width": 2,
                        "dash_array": [4, 4]
                    },
                    "temporal_warning_tag": "NOTICE: 12-Day Historical InSAR Data — Not Real-Time Kinematic Sensor Stream"
                },
                "geometry": mapping(poly)
            })

        return {
            "type": "FeatureCollection",
            "properties": {
                "site_id": site_id,
                "layer": "sentinel1_insar_hatched_vector",
                "acquisition_date": acquisition_date
            },
            "features": features
        }
