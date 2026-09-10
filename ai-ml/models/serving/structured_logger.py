"""
DGMS Regulatory Audit Logger.
Structured, tamper-evident logging of every model inference call from day one.
Mandated by DGMS Mine Safety Circulars for life-safety evidentiary trails.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

logger = logging.getLogger("subsense.serving.dgms_audit")


class DGMSAuditLogger:
    """
    Appends structured JSON records of every scoring event to the regulatory audit trail.
    Ensures complete traceability from raw vector inputs to warning sirens.
    """

    def __init__(self, log_file_path: Optional[str] = None):
        self.log_file_path = Path(log_file_path) if log_file_path else (
            Path(__file__).resolve().parent.parent.parent / "logs" / "dgms_audit_trail.jsonl"
        )
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.total_records = 0

    def log_inference(
        self,
        node_id: str,
        timestamp: datetime,
        input_vector_12d: List[float],
        anomaly_score: float,
        reconstruction_error: float,
        contributing_sensors: List[str],
        confidence: float,
        inference_latency_ms: float,
        model_signature: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Logs an immutable inference audit entry."""
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        entry = {
            "timestamp_utc": timestamp.isoformat(),
            "node_id": node_id,
            "input_vector_12d": [round(float(v), 6) for v in input_vector_12d],
            "anomaly_score": round(float(anomaly_score), 4),
            "reconstruction_error": round(float(reconstruction_error), 6),
            "contributing_sensors": contributing_sensors,
            "confidence": round(float(confidence), 4),
            "inference_latency_ms": round(float(inference_latency_ms), 2),
            "model_signature": model_signature,
            "context": additional_context or {},
        }

        try:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            self.total_records += 1
        except Exception as e:
            logger.error(f"Failed writing to DGMS audit trail: {e}")

        return entry
