from fastapi import APIRouter
from typing import List

from src.schemas.insar_contracts import InSARDiscrepancyMarker
from src.insar.insar_overlay import InSAROverlayEngine
from src.insar.discrepancy_engine import InSARDiscrepancyEngine

router = APIRouter(prefix="/api/v1/insar", tags=["Sentinel-1 InSAR Macro-Fusion (5.4)"])

overlay_engine = InSAROverlayEngine()

_sample_basins = [
    {
        "basin_id": "INSAR-BASIN-2026-088",
        "los_velocity_mm_year": -34.5,
        "coordinates_wgs84": [[[86.4338, 23.7918], [86.4355, 23.7919], [86.4352, 23.7932], [86.4335, 23.7930], [86.4338, 23.7918]]]
    }
]

@router.get("/{tenant_id}/{site_id}/discrepancies", response_model=List[InSARDiscrepancyMarker])
async def get_insar_discrepancies(tenant_id: str, site_id: str):
    """
    Returns Sentinel-1 geodetic discrepancy markers conforming to Section 6.3.
    """
    # Active ground sensor nodes in concession
    nodes = [
        {"id": f"SS-{site_id}-N001", "lat": 23.7880, "lon": 86.4300},
        {"id": f"SS-{site_id}-N002", "lat": 23.7890, "lon": 86.4310}
    ]
    markers = InSARDiscrepancyEngine.detect_discrepancies(
        site_id=site_id,
        insar_basins=_sample_basins,
        sensor_nodes=nodes,
        acquisition_date="2026-08-28"
    )
    return markers

@router.get("/{tenant_id}/{site_id}/overlay")
async def get_insar_overlay_geojson(tenant_id: str, site_id: str):
    """
    Returns hatched vector overlay GeoJSON for Sentinel-1 Line-of-Sight deformation.
    """
    return overlay_engine.generate_hatched_basin_geojson(
        site_id=site_id,
        acquisition_date="2026-08-28",
        basins=_sample_basins
    )

@router.get("/{tenant_id}/{site_id}/decomposition")
async def get_insar_decomposition(
    tenant_id: str,
    site_id: str,
    los_asc_mm_yr: float = -28.4,
    los_desc_mm_yr: float = -34.5,
    coherence: float = 0.72
):
    """
    Decomposes dual-pass Sentinel-1 ascending and descending Line-of-Sight (LOS)
    radar velocities into true vertical ground subsidence and east-west shear.
    """
    from src.insar.insar_decomposition import InSARDecompositionEngine
    return InSARDecompositionEngine.decompose_los_to_2d(
        los_vel_asc_mm_yr=los_asc_mm_yr,
        los_vel_desc_mm_yr=los_desc_mm_yr,
        coherence_asc=coherence,
        coherence_desc=coherence
    )

