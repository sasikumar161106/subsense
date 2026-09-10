from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from src.schemas.whatif_contracts import ProposedPanelGeometry, SubsidenceSimulationResult
from src.simulation.whatif_scenario import WhatIfSimulationEngine
from src.simulation.replay_manager import ReplayManager

router = APIRouter(prefix="/api/v1/simulation", tags=["Historical Replay & What-If Simulation (5.6)"])

whatif_engine = WhatIfSimulationEngine()
replay_manager = ReplayManager()

# Populate sample historical snapshots
for step in range(5):
    replay_manager.record_snapshot(
        tenant_id="tenant_alpha",
        site_id="PANEL7-JHARIA",
        state_payload={
            "step": step,
            "max_tilt_deg": round(0.12 + step * 0.04, 3),
            "critical_zone_active": (step >= 3)
        }
    )

@router.get("/replay/{tenant_id}/{site_id}/timeline")
async def get_timeline_index(tenant_id: str, site_id: str):
    """
    Returns timestamp-indexed historical state frames for VCR timeline scrubber.
    """
    return replay_manager.get_timeline_index(tenant_id, site_id)

@router.get("/replay/{tenant_id}/{site_id}/frame/{frame_idx}")
async def get_timeline_frame(tenant_id: str, site_id: str, frame_idx: int):
    """
    Retrieves specific past snapshot frame for post-incident audit.
    """
    frame = replay_manager.get_snapshot_at(tenant_id, site_id, frame_idx)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame index not found in historical timeline.")
    return frame

@router.post("/what-if", response_model=SubsidenceSimulationResult)
async def run_whatif_simulation(panel: ProposedPanelGeometry):
    """
    Predictive What-If extraction simulation.
    Calculates surface deformation trough via empirical NCB models and returns
    watermarked simulation scene with side-by-side risk deltas.
    """
    return whatif_engine.run_simulation(panel)
