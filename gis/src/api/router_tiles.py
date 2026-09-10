import hashlib
from fastapi import APIRouter, Response, Request, HTTPException, Header
from typing import Optional
from io import BytesIO
import numpy as np
from PIL import Image

from config.settings import settings
from src.normalizer.crs_normalizer import SpatialDataNormalizer
from src.heatmap.tile_slicer import TileSlicer
from src.delivery.tile_cache import MultiTenantTileCache
from src.api.router_raster import raster_state

router = APIRouter(prefix="/api/v1/tiles", tags=["Raster Tile Server (5.1 & 5.5)"])

normalizer = SpatialDataNormalizer()
tile_slicer = TileSlicer(normalizer)
tile_cache = MultiTenantTileCache()

# Synthetic site risk grid for PANEL7-JHARIA
_synthetic_bounds_wgs84 = (86.425, 23.785, 86.445, 23.800)
_H, _W = 200, 200
_y, _x = np.ogrid[:_H, :_W]
_dist = np.sqrt((_x - 100)**2 + (_y - 100)**2)
_base_risk_grid = np.clip(0.92 * np.exp(-(_dist / 35.0)**2), 0.0, 1.0).astype(np.float32)
_base_var_grid = (0.15 + 0.35 * (_dist / 140.0)).astype(np.float32)

@router.get("/{tenant_id}/{site_id}/{z}/{x}/{y}.png")
async def get_tile(
    tenant_id: str,
    site_id: str,
    z: int,
    x: int,
    y: int,
    request: Request,
    data_age_seconds: float = 12.0
):
    """
    Delivers 256x256 PNG slippy raster tile adhering to Section 5.1 & 5.5.
    Attaches Section 6.1 metadata headers, HTTP ETags, and 304 conditional caching.
    """
    if z < settings.MIN_ZOOM or z > settings.MAX_ZOOM:
        raise HTTPException(status_code=400, detail=f"Zoom level {z} outside supported range (12-18).")

    # Generate deterministic ETag based on cycle generation window
    cycle_bucket = int(data_age_seconds // settings.INGESTION_SLA_SECONDS)
    etag = f'W/"{hashlib.md5(f"{tenant_id}:{site_id}:{z}:{x}:{y}:{cycle_bucket}".encode()).hexdigest()}"'

    # Check client conditional request (If-None-Match)
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and if_none_match == etag:
        return Response(status_code=304)

    # Check cache first
    cached_bytes = tile_cache.get_tile(tenant_id, site_id, z, x, y)
    
    if cached_bytes is not None:
        tile_bytes = cached_bytes
    else:
        active_grid = raster_state.get_grid(site_id)
        if active_grid is not None:
            risk_grid_to_use = active_grid["risk_grid"]
            bounds_to_use = active_grid["bounds_wgs84"]
            var_grid_to_use = active_grid["variance_grid"]
        else:
            risk_grid_to_use = _base_risk_grid
            bounds_to_use = _synthetic_bounds_wgs84
            var_grid_to_use = _base_var_grid

        img, meta = tile_slicer.render_tile_image(
            risk_grid=risk_grid_to_use,
            grid_bounds_wgs84=bounds_to_use,
            z=z, x=x, y=y,
            variance_grid=var_grid_to_use,
            data_currency_seconds=data_age_seconds
        )
        bio = BytesIO()
        img.save(bio, format="PNG", optimize=True)
        tile_bytes = bio.getvalue()
        tile_cache.put_tile(tenant_id, site_id, z, x, y, tile_bytes)

    is_stale = (data_age_seconds > settings.DATA_CURRENCY_STALENESS_SECONDS)
    headers = {
        "Content-Type": "image/png",
        "ETag": etag,
        "X-Site-ID": site_id,
        "X-Layer": "risk_deformation_heatmap",
        "X-Tile-Z": str(z),
        "X-Tile-X": str(x),
        "X-Tile-Y": str(y),
        "X-Data-Currency-Seconds": str(round(data_age_seconds, 1)),
        "X-Is-Stale": "true" if is_stale else "false",
        "X-Kriging-Variance-Included": "true",
        "Cache-Control": "public, max-age=30, must-revalidate"
    }

    return Response(content=tile_bytes, media_type="image/png", headers=headers)
