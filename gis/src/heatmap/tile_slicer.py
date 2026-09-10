import math
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timezone
import numpy as np
from PIL import Image
from scipy.ndimage import zoom as nd_zoom

from src.normalizer.crs_normalizer import SpatialDataNormalizer
from src.heatmap.color_ramp import ColorRampEngine
from src.heatmap.variance_mask import VarianceConfidenceMaskEngine
from src.heatmap.staleness_decorator import StalenessDecorator
from src.schemas.heatmap_contracts import HeatmapMetadataHeader, TileCoordinates

class TileSlicer:
    """
    SubSense Slippy-Map Tile Slicer & Raster Generator (Section 5.1 & 5.5).
    Slices continuous Kriging risk grids into standard 256x256 Web Mercator XYZ tiles
    (zooms 12 to 18) with color ramp, variance mask, and staleness watermarking.
    """
    def __init__(self, normalizer: Optional[SpatialDataNormalizer] = None):
        self.normalizer = normalizer or SpatialDataNormalizer()

    def render_tile_image(
        self,
        risk_grid: np.ndarray,
        grid_bounds_wgs84: Tuple[float, float, float, float],  # (min_lon, min_lat, max_lon, max_lat)
        z: int, x: int, y: int,
        variance_grid: Optional[np.ndarray] = None,
        data_currency_seconds: float = 0.0,
        tile_size: int = 256
    ) -> Tuple[Image.Image, HeatmapMetadataHeader]:
        """
        Renders a single 256x256 PNG tile for slippy coordinates (z, x, y)
        from a site-level risk raster.
        """
        tile_min_lon, tile_min_lat, tile_max_lon, tile_max_lat = self.normalizer.tile_to_bounds_wgs84(z, x, y)
        site_min_lon, site_min_lat, site_max_lon, site_max_lat = grid_bounds_wgs84

        is_stale = (data_currency_seconds > 30.0)
        metadata = HeatmapMetadataHeader(
            site_id="PANEL7-JHARIA",
            layer="risk_deformation_heatmap",
            tile_coordinates=TileCoordinates(z=z, x=x, y=y),
            as_of=datetime.now(timezone.utc),
            data_currency_seconds=data_currency_seconds,
            is_stale=is_stale,
            kriging_variance_included=(variance_grid is not None)
        )

        # Check if tile intersects site bounds
        if (tile_max_lon < site_min_lon or tile_min_lon > site_max_lon or
            tile_max_lat < site_min_lat or tile_min_lat > site_max_lat):
            empty_img = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
            return empty_img, metadata

        H, W = risk_grid.shape
        lon_span = site_max_lon - site_min_lon
        lat_span = site_max_lat - site_min_lat

        t_lons = np.linspace(tile_min_lon, tile_max_lon, tile_size)
        t_lats = np.linspace(tile_max_lat, tile_min_lat, tile_size)

        t_lon_grid, t_lat_grid = np.meshgrid(t_lons, t_lats)

        gx = (t_lon_grid - site_min_lon) / lon_span * (W - 1)
        gy = (site_max_lat - t_lat_grid) / lat_span * (H - 1)

        inside = (gx >= 0) & (gx <= W - 1) & (gy >= 0) & (gy <= H - 1)

        gx_clamped = np.clip(np.round(gx).astype(int), 0, W - 1)
        gy_clamped = np.clip(np.round(gy).astype(int), 0, H - 1)

        tile_risk = np.zeros((tile_size, tile_size), dtype=np.float32)
        tile_risk[inside] = risk_grid[gy_clamped[inside], gx_clamped[inside]]

        # Apply DGMS Color Ramp
        rgba = ColorRampEngine.apply_color_ramp(tile_risk)
        rgba[~inside] = [0, 0, 0, 0]

        # Apply Variance Mask if provided
        if variance_grid is not None:
            tile_var = np.zeros((tile_size, tile_size), dtype=np.float32)
            tile_var[inside] = variance_grid[gy_clamped[inside], gx_clamped[inside]]
            rgba = VarianceConfidenceMaskEngine.apply_confidence_mask(rgba, tile_var)

        # Apply Staleness Stripes if outdated
        rgba = StalenessDecorator.apply_staleness_stripes(rgba, data_currency_seconds)

        img = Image.fromarray(rgba, mode="RGBA")
        return img, metadata

    def save_tile(self, img: Image.Image, output_dir: Path, tenant_id: str, site_id: str,
                  z: int, x: int, y: int) -> Path:
        tile_dir = output_dir / tenant_id / site_id / str(z) / str(x)
        tile_dir.mkdir(parents=True, exist_ok=True)
        out_path = tile_dir / f"{y}.png"
        img.save(out_path, format="PNG", optimize=True)
        return out_path
