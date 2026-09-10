from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Tuple, List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from src.schemas.gis_interop_contracts import IngestionRasterPayload
from src.geostats.ordinary_kriging import OrdinaryKrigingInterpolator

router = APIRouter(prefix="/api/v1/kriging", tags=["Geostatistical Surface Engine (Step 4 -> Step 5)"])

_kriging = OrdinaryKrigingInterpolator()

class KrigingRequest(BaseModel):
    site_id: str
    node_coords: Dict[str, Tuple[float, float]]
    node_values: Dict[str, float]
    bounds_utm: Tuple[float, float, float, float]
    utm_epsg: int = 32645
    grid_resolution_m: float = 20.0

@router.post("/surface", response_model=IngestionRasterPayload)
async def generate_kriging_surface(request: KrigingRequest):
    """
    Direct endpoint feeding GIS Layer 5 (heatmap_contracts.py).
    Produces 2D continuous subsidence risk surface and estimation variance confidence mask.
    """
    try:
        interpolator = OrdinaryKrigingInterpolator(grid_resolution_m=request.grid_resolution_m)
        payload = interpolator.interpolate_raster(
            site_id=request.site_id,
            node_coords=request.node_coords,
            node_values=request.node_values,
            bounds_utm=request.bounds_utm,
            utm_epsg=request.utm_epsg,
            timestamp=datetime.now(timezone.utc),
        )
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kriging interpolation failure: {str(e)}")
