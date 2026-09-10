"""
SubSense GIS Layer: Ingestion Endpoint for Universal Kriging Rasters (ADR-006).
Receives continuous geostatistical subsidence grids produced by Layer 4 (AI/ML)
and activates them for 2D tile rendering and digital twin overlays.
"""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status
import numpy as np

from src.delivery.tile_cache import MultiTenantTileCache

router = APIRouter(prefix="/api/v1/raster", tags=["Raster Ingestion"])


class RasterIngestRequest(BaseModel):
    tenant_id: str = Field(default="tenant-jharia-01", description="Mine operator tenant ID")
    site_id: str = Field(default="PANEL7-JHARIA", description="Mine extraction panel/site ID")
    bounds_wgs84: List[float] = Field(
        default_factory=lambda: [86.425, 23.785, 86.445, 23.800],
        description="Bounding box [min_lon, min_lat, max_lon, max_lat] in EPSG:4326"
    )
    risk_grid: List[List[float]] = Field(description="2D float matrix of interpolated deformation/risk in [0.0, 1.0]")
    variance_grid: Optional[List[List[float]]] = Field(default=None, description="Optional 2D float matrix of kriging estimation variance")
    timestamp: Optional[datetime] = Field(default=None, description="Generation timestamp UTC")


class SiteRasterState:
    """In-memory singleton holding the active site raster grids for tile rendering."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SiteRasterState, cls).__new__(cls)
            cls._instance._grids = {}
        return cls._instance

    def set_grid(
        self,
        site_id: str,
        risk_grid: np.ndarray,
        bounds_wgs84: Tuple[float, float, float, float],
        variance_grid: Optional[np.ndarray] = None,
    ):
        self._grids[site_id] = {
            "risk_grid": risk_grid,
            "bounds_wgs84": bounds_wgs84,
            "variance_grid": variance_grid,
            "updated_at": datetime.now(timezone.utc),
        }

    def get_grid(self, site_id: str) -> Optional[Dict[str, Any]]:
        return self._grids.get(site_id)


raster_state = SiteRasterState()
tile_cache = MultiTenantTileCache()


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_raster(req: RasterIngestRequest):
    if len(req.bounds_wgs84) != 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bounds_wgs84 must be a 4-element list [min_lon, min_lat, max_lon, max_lat]",
        )

    min_lon, min_lat, max_lon, max_lat = req.bounds_wgs84
    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bounding box: min coordinates must be strictly less than max coordinates",
        )

    if not req.risk_grid or not req.risk_grid[0]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="risk_grid must be a non-empty 2D array",
        )

    risk_arr = np.array(req.risk_grid, dtype=np.float32)
    var_arr = np.array(req.variance_grid, dtype=np.float32) if req.variance_grid else None

    if var_arr is not None and var_arr.shape != risk_arr.shape:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"variance_grid shape {var_arr.shape} does not match risk_grid shape {risk_arr.shape}",
        )

    # Store in singleton site state
    bounds_tuple = (float(min_lon), float(min_lat), float(max_lon), float(max_lat))
    raster_state.set_grid(
        site_id=req.site_id,
        risk_grid=risk_arr,
        bounds_wgs84=bounds_tuple,
        variance_grid=var_arr,
    )

    # Invalidate cached tiles for this site
    tile_cache.invalidate_site_cache(req.tenant_id, req.site_id)

    return {
        "status": "INGESTED",
        "site_id": req.site_id,
        "tenant_id": req.tenant_id,
        "grid_shape": list(risk_arr.shape),
        "bounds_wgs84": list(bounds_tuple),
        "has_variance": var_arr is not None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/latest/{site_id}")
async def get_latest_raster_meta(site_id: str):
    grid_data = raster_state.get_grid(site_id)
    if not grid_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No ingested raster found for site '{site_id}'",
        )
    return {
        "site_id": site_id,
        "grid_shape": list(grid_data["risk_grid"].shape),
        "bounds_wgs84": list(grid_data["bounds_wgs84"]),
        "has_variance": grid_data["variance_grid"] is not None,
        "updated_at": grid_data["updated_at"].isoformat(),
    }
