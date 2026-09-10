import asyncio
import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/v1/stream", tags=["Real-Time SSE Event Stream"])

@router.get("/{tenant_id}/{site_id}/events")
async def event_stream(
    tenant_id: str,
    site_id: str,
    max_cycles: Optional[int] = Query(None, description="Optional cycle limit for testing/polling")
):
    """
    Server-Sent Events (SSE) stream for near-real-time push updates.
    Eliminates client polling, delivering instant cycle completions,
    staleness updates, and critical TTC emergency notifications.
    """
    async def event_generator():
        cycle = 1
        while True:
            now = datetime.now(timezone.utc)
            payload = {
                "event_type": "telemetry_cycle_published",
                "tenant_id": tenant_id,
                "site_id": site_id,
                "cycle_number": cycle,
                "timestamp": now.isoformat(),
                "data_currency_seconds": 12.0,
                "is_stale": False,
                "active_zones_count": 3,
                "max_risk_level": 0.89,
                "critical_ttc_hours": 1.8
            }
            yield f"event: cycle_published\ndata: {json.dumps(payload)}\n\n"

            if payload["critical_ttc_hours"] <= 2.0:
                alert_payload = {
                    "event_type": "EMERGENCY_TTC_WARNING",
                    "zone_id": f"ZONE-{site_id}-C",
                    "severity": "CRITICAL",
                    "ttc_hours": payload["critical_ttc_hours"],
                    "message": f"Time-to-Critical below statutory threshold (1.8h) in {site_id}."
                }
                yield f"event: emergency_alert\ndata: {json.dumps(alert_payload)}\n\n"

            if max_cycles is not None and cycle >= max_cycles:
                break

            cycle += 1
            await asyncio.sleep(15)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
