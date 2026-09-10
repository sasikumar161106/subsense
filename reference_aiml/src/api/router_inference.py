from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

from src.schemas.sensor_contracts import SensorReading, NodeHealthMetadata
from src.schemas.risk_event_contracts import RiskEvent
from src.schemas.gis_interop_contracts import IngestionRasterPayload
from src.pipeline.inference_pipeline import InferencePipeline

router = APIRouter(prefix="/api/v1/inference", tags=["Data Inference Engine (Step 4)"])

# Shared pipeline instance
_pipeline = InferencePipeline()

class InferenceBatchRequest(BaseModel):
    site_id: str = Field(..., description="Target mine site identifier, e.g. SITE-JHARIA-04")
    node_readings_map: Dict[str, List[SensorReading]] = Field(..., description="Map of node_id to list of readings")
    node_health_map: Optional[Dict[str, NodeHealthMetadata]] = Field(default_factory=dict)
    node_coords_utm: Dict[str, Tuple[float, float]] = Field(..., description="Map of node_id to (utm_x, utm_y)")
    bounds_utm: Tuple[float, float, float, float] = Field(..., description="Site bounds [min_x, min_y, max_x, max_y]")
    utm_epsg: int = Field(default=32645, description="UTM EPSG coordinate reference code")

class InferenceCycleResponse(BaseModel):
    site_id: str
    status: str
    risk_events: List[RiskEvent]
    raster_payload: IngestionRasterPayload
    quarantined_nodes: Dict[str, str]
    node_count_analyzed: int
    execution_duration_sec: float
    sla_passed: bool

@router.post("/run", response_model=InferenceCycleResponse)
async def run_inference_cycle(payload: InferenceBatchRequest):
    """
    Executes live analytical inference over a multi-sensor telemetry batch.
    Produces formal Risk Events (Section 10) and continuous Kriging raster surfaces.
    """
    try:
        results = _pipeline.run_inference_cycle(
            site_id=payload.site_id,
            node_readings_map=payload.node_readings_map,
            node_health_map=payload.node_health_map or {},
            node_coords_utm=payload.node_coords_utm,
            bounds_utm=payload.bounds_utm,
            utm_epsg=payload.utm_epsg,
        )
        return InferenceCycleResponse(
            site_id=payload.site_id,
            status="success",
            risk_events=results["risk_events"],
            raster_payload=results["raster_payload"],
            quarantined_nodes=results["quarantined_nodes"],
            node_count_analyzed=results["node_count_analyzed"],
            execution_duration_sec=results["execution_duration_sec"],
            sla_passed=results["sla_passed"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference pipeline execution error: {str(e)}")

@router.get("/health")
async def get_inference_health():
    """Health status and active model versions."""
    active_versions = _pipeline.registry.get_active_versions()
    return {
        "status": "healthy",
        "service": "SubSense AI/ML Data Inference Layer (Layer 4)",
        "active_model_versions": active_versions,
        "sla_target_sec": 15.0,
    }

def get_shared_pipeline() -> InferencePipeline:
    return _pipeline
