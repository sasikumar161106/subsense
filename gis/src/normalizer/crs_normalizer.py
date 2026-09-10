import math
from typing import Tuple, List, Optional
import pyproj
from pyproj import Transformer

class SpatialDataNormalizer:
    """
    SubSense Spatial Data Normalizer (Section 4 & Section 3).
    Ensures unified spatial reference across GPS sensor nodes, CAD mine workings, 
    satellite InSAR rasters, and Web Mercator tile pyramids.
    """
    def __init__(self, target_utm_epsg: int = 32645):
        self.target_utm_epsg = target_utm_epsg
        # Transformer: WGS84 (EPSG:4326) -> UTM
        # always_xy=True ensures (lon, lat) order
        self._to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{target_utm_epsg}", always_xy=True)
        # Transformer: UTM -> WGS84
        self._to_wgs84 = Transformer.from_crs(f"EPSG:{target_utm_epsg}", "EPSG:4326", always_xy=True)
        # Transformer: WGS84 -> Web Mercator (EPSG:3857)
        self._to_web_mercator = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        # Transformer: Web Mercator -> WGS84
        self._from_web_mercator = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    def wgs84_to_utm(self, lon: float, lat: float) -> Tuple[float, float]:
        """Convert WGS84 (lon, lat) to planar UTM Easting, Northing in meters."""
        easting, northing = self._to_utm.transform(lon, lat)
        return float(easting), float(northing)

    def utm_to_wgs84(self, easting: float, northing: float) -> Tuple[float, float]:
        """Convert planar UTM Easting, Northing to WGS84 (lon, lat)."""
        lon, lat = self._to_wgs84.transform(easting, northing)
        return float(lon), float(lat)

    def wgs84_to_web_mercator(self, lon: float, lat: float) -> Tuple[float, float]:
        """Convert WGS84 (lon, lat) to Web Mercator EPSG:3857 (x, y) meters."""
        x, y = self._to_web_mercator.transform(lon, lat)
        return float(x), float(y)

    def web_mercator_to_wgs84(self, x: float, y: float) -> Tuple[float, float]:
        """Convert Web Mercator EPSG:3857 (x, y) to WGS84 (lon, lat)."""
        lon, lat = self._from_web_mercator.transform(x, y)
        return float(lon), float(lat)

    @staticmethod
    def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
        """Convert WGS84 (lat, lon) to Slippy Map XYZ tile coordinates at given zoom level."""
        lat_rad = math.radians(lat)
        n = 2.0 ** zoom
        xtile = int((lon + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return xtile, ytile

    @staticmethod
    def tile_to_bounds_wgs84(z: int, x: int, y: int) -> Tuple[float, float, float, float]:
        """
        Calculate bounding box of slippy tile (z, x, y) in WGS84.
        Returns: (min_lon, min_lat, max_lon, max_lat)
        """
        n = 2.0 ** z
        min_lon = x / n * 360.0 - 180.0
        max_lon = (x + 1) / n * 360.0 - 180.0
        
        lat_rad_top = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / n)))
        lat_rad_bottom = math.atan(math.sinh(math.pi * (1.0 - 2.0 * (y + 1) / n)))
        
        max_lat = math.degrees(lat_rad_top)
        min_lat = math.degrees(lat_rad_bottom)
        
        return min_lon, min_lat, max_lon, max_lat

    def transform_geojson_geometry(self, geometry: dict, target: str = "utm") -> dict:
        """
        Recursively transform GeoJSON geometry coordinates between WGS84 and UTM.
        """
        geom_type = geometry.get("type")
        coords = geometry.get("coordinates")
        
        if geom_type == "Point":
            new_coords = list(self.wgs84_to_utm(*coords) if target == "utm" else self.utm_to_wgs84(*coords))
        elif geom_type == "LineString":
            new_coords = [list(self.wgs84_to_utm(pt[0], pt[1]) if target == "utm" else self.utm_to_wgs84(pt[0], pt[1])) for pt in coords]
        elif geom_type == "Polygon":
            new_coords = [
                [list(self.wgs84_to_utm(pt[0], pt[1]) if target == "utm" else self.utm_to_wgs84(pt[0], pt[1])) for pt in ring]
                for ring in coords
            ]
        elif geom_type == "MultiPolygon":
            new_coords = [
                [
                    [list(self.wgs84_to_utm(pt[0], pt[1]) if target == "utm" else self.utm_to_wgs84(pt[0], pt[1])) for pt in ring]
                    for ring in poly
                ]
                for poly in coords
            ]
        else:
            new_coords = coords

        return {"type": geom_type, "coordinates": new_coords}
