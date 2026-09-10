from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

class ReplayManager:
    """
    SubSense Historical Replay Manager (Section 5.6).
    Indexes and serves historical chronological state snapshots for post-incident
    geotechnical audit and VCR scrubber playback.
    """
    def __init__(self):
        # Store of snapshots: { "tenant:site": [ {"timestamp": dt, "state": dict} ] }
        self._history: Dict[str, List[Dict[str, Any]]] = {}

    def record_snapshot(self, tenant_id: str, site_id: str, state_payload: Dict[str, Any],
                        timestamp: Optional[datetime] = None):
        key = f"{tenant_id}:{site_id}"
        if key not in self._history:
            self._history[key] = []
        
        ts = timestamp or datetime.now(timezone.utc)
        self._history[key].append({
            "timestamp": ts,
            "timestamp_iso": ts.isoformat(),
            "state": state_payload
        })

    def get_timeline_index(self, tenant_id: str, site_id: str) -> Dict[str, Any]:
        """Returns list of available timestamps for the scrubber."""
        key = f"{tenant_id}:{site_id}"
        records = self._history.get(key, [])
        return {
            "site_id": site_id,
            "snapshot_count": len(records),
            "start_time": records[0]["timestamp_iso"] if records else None,
            "end_time": records[-1]["timestamp_iso"] if records else None,
            "timestamps": [r["timestamp_iso"] for r in records]
        }

    def get_snapshot_at(self, tenant_id: str, site_id: str, index: int) -> Optional[Dict[str, Any]]:
        key = f"{tenant_id}:{site_id}"
        records = self._history.get(key, [])
        if 0 <= index < len(records):
            return records[index]
        return None
