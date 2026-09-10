from fastapi import APIRouter, HTTPException
from typing import Dict, Tuple, List, Optional
from pydantic import BaseModel
import numpy as np

from src.schemas.insar_contracts import InSAROverlayPayload
from src.insar.insar_cross_validator import InSARCrossValidator

router = APIRouter(prefix="/api/v1/insar", tags=["InSAR Satellite Fusion Engine (Step 4 -> Step 5)"])

_validator = InSARCrossValidator()

class InSARValidationRequest(BaseModel):
    site_id: str
    insar_velocity_grid: List[List[float]]  # 2D grid in mm/year
    bounds_utm: Tuple[float, float, float, float]
    ground_mesh_coords: Dict[str, Tuple[float, float]]
    ground_risk_grid: List[List[float]]     # 2D grid in [0, 1]
    pass_date: str = "2026-09-08"

@router.post("/cross-validate", response_model=InSAROverlayPayload)
async def cross_validate_insar(request: InSARValidationRequest):
    """
    Cross-validates Sentinel-1 Line-of-Sight deformation grids against ground sensor mesh.
    Identifies unmonitored subsidence basins outside mesh perimeter and velocity mismatches.
    """
    try:
        vel_arr = np.array(request.insar_velocity_grid, dtype=np.float32)
        risk_arr = np.array(request.ground_risk_grid, dtype=np.float32)

        overlay = _validator.cross_validate(
            site_id=request.site_id,
            insar_velocity_grid=vel_arr,
            bounds_utm=request.bounds_utm,
            ground_mesh_coords=request.ground_mesh_coords,
            ground_risk_grid=risk_arr,
            pass_date=request.pass_date,
        )
        return overlay
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"InSAR validation failure: {str(e)}")
