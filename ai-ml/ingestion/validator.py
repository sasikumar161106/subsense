"""
Physical plausibility and schema validation engine.
Enforces zero silent drops by recording every rejected payload to an audit trail.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import ValidationError

from .schema import RawSensorRecord

logger = logging.getLogger("subsense.ingestion.validator")


@dataclass
class RejectionRecord:
    timestamp_utc: str
    node_id: Optional[str]
    category: str
    reason: str
    raw_payload: Any


@dataclass
class ValidationResult:
    is_valid: bool
    record: Optional[RawSensorRecord] = None
    rejection: Optional[RejectionRecord] = None


class PayloadValidator:
    """
    Validates incoming sensor payloads against physical bounds and schema contracts.
    Maintains a rate-of-change history per node to catch physically implausible sensor spikes.
    """

    def __init__(
        self,
        bounds_config_path: Optional[str] = None,
        audit_log_path: Optional[str] = None,
    ):
        self.bounds = self._load_bounds(bounds_config_path)
        self.audit_log_path = Path(audit_log_path) if audit_log_path else None
        self.rejections: List[RejectionRecord] = []
        self._last_readings: Dict[str, RawSensorRecord] = {}

        if self.audit_log_path:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_bounds(self, config_path: Optional[str]) -> Dict[str, Any]:
        default_bounds = {
            "sensors": {
                "tilt_deg": {"min": -45.0, "max": 45.0, "max_rate_deg_per_sec": 5.0},
                "vibration_rms_mm_s": {"min": 0.0, "max": 200.0, "max_rate_mm_s_per_sec": 150.0},
                "displacement_mm": {"min": 0.0, "max": 1000.0, "max_rate_mm_per_sec": 50.0},
                "crack_index": {"min": 0.0, "max": 1.0, "max_rate_per_sec": 0.5},
            },
            "gps": {
                "lat": {"min": -90.0, "max": 90.0},
                "lon": {"min": -180.0, "max": 180.0},
                "elevation_m": {"min": -500.0, "max": 5000.0},
            },
            "node_health": {
                "battery_pct": {"min": 0.0, "max": 100.0},
                "rssi_dbm": {"min": -130.0, "max": 0.0},
                "hop_count": {"min": 0, "max": 15},
            },
            "timestamp": {
                "max_future_skew_sec": 120.0,
                "max_past_skew_sec": 86400.0,
            },
        }

        if not config_path:
            # Check default path
            potential_path = Path(__file__).resolve().parent.parent / "config" / "physical_bounds.yaml"
            if potential_path.exists():
                config_path = str(potential_path)

        if config_path and Path(config_path).exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        return loaded
            except Exception as e:
                logger.warning(f"Failed to load bounds config from {config_path}: {e}. Using defaults.")

        return default_bounds

    def validate(self, raw_input: Any, current_time: Optional[datetime] = None) -> ValidationResult:
        """
        Validates raw dictionary or JSON string payload.
        Ensures strict contract enforcement and zero silent drops.
        """
        now = current_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # 1. Parse JSON if string
        payload = raw_input
        if isinstance(raw_input, (str, bytes)):
            try:
                payload = json.loads(raw_input)
            except Exception as e:
                return self._reject(
                    node_id=None,
                    category="MALFORMED_JSON",
                    reason=f"Payload is not valid JSON: {str(e)}",
                    raw_payload=raw_input,
                )

        if not isinstance(payload, dict):
            return self._reject(
                node_id=None,
                category="SCHEMA_INVALID",
                reason=f"Payload root must be an object/dict, got {type(payload).__name__}",
                raw_payload=raw_input,
            )

        node_id = str(payload.get("node_id", "")) or None

        # 2. Schema Validation via Pydantic
        try:
            record = RawSensorRecord.model_validate(payload)
        except ValidationError as e:
            errors = e.errors()
            err_msg = "; ".join([f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in errors])
            return self._reject(
                node_id=node_id,
                category="SCHEMA_VALIDATION_ERROR",
                reason=err_msg,
                raw_payload=raw_input,
            )

        # 3. Timestamp Skew Checks
        rec_time = record.timestamp
        if rec_time.tzinfo is None:
            rec_time = rec_time.replace(tzinfo=timezone.utc)

        skew_future = (rec_time - now).total_seconds()
        skew_past = (now - rec_time).total_seconds()
        max_future = self.bounds["timestamp"]["max_future_skew_sec"]
        max_past = self.bounds["timestamp"]["max_past_skew_sec"]

        if skew_future > max_future:
            return self._reject(
                node_id=record.node_id,
                category="TIMESTAMP_FUTURE_SKEW",
                reason=f"Timestamp {rec_time.isoformat()} is {skew_future:.1f}s in future (max allowed {max_future}s)",
                raw_payload=raw_input,
            )
        if skew_past > max_past:
            return self._reject(
                node_id=record.node_id,
                category="TIMESTAMP_EXPIRED",
                reason=f"Timestamp {rec_time.isoformat()} is {skew_past:.1f}s stale (max allowed {max_past}s)",
                raw_payload=raw_input,
            )

        # 4. Physical Range Checks
        import math
        sensor_bounds = self.bounds["sensors"]
        s = record.sensors
        for field_name, val in [
            ("tilt_deg", s.tilt_deg),
            ("vibration_rms_mm_s", s.vibration_rms_mm_s),
            ("displacement_mm", s.displacement_mm),
            ("crack_index", s.crack_index),
        ]:
            if math.isnan(val) or math.isinf(val):
                return self._reject(
                    node_id=record.node_id,
                    category="PHYSICAL_BOUND_VIOLATION",
                    reason=f"{field_name} is non-finite (NaN or Inf)",
                    raw_payload=raw_input,
                )
            if field_name in sensor_bounds:
                b = sensor_bounds[field_name]
                if "min" in b and val < b["min"]:
                    return self._reject(
                        node_id=record.node_id,
                        category="PHYSICAL_BOUND_VIOLATION",
                        reason=f"{field_name}={val} below minimum bound {b['min']}",
                        raw_payload=raw_input,
                    )
                if "max" in b and val > b["max"]:
                    return self._reject(
                        node_id=record.node_id,
                        category="PHYSICAL_BOUND_VIOLATION",
                        reason=f"{field_name}={val} exceeds maximum bound {b['max']}",
                        raw_payload=raw_input,
                    )

        # Health bounds
        h_bounds = self.bounds["node_health"]
        h = record.node_health
        if h.battery_pct < h_bounds["battery_pct"]["min"] or h.battery_pct > h_bounds["battery_pct"]["max"]:
            return self._reject(
                node_id=record.node_id,
                category="HEALTH_BOUND_VIOLATION",
                reason=f"battery_pct={h.battery_pct} out of [0, 100]",
                raw_payload=raw_input,
            )

        # 5. Rate-of-Change Checks (against previous valid sample)
        if record.node_id in self._last_readings:
            prev = self._last_readings[record.node_id]
            prev_time = prev.timestamp if prev.timestamp.tzinfo else prev.timestamp.replace(tzinfo=timezone.utc)
            dt = (rec_time - prev_time).total_seconds()
            if dt > 0.05:  # At least 50ms interval to compute derivative reliably
                delta_tilt = abs(record.sensors.tilt_deg - prev.sensors.tilt_deg)
                rate_tilt = delta_tilt / dt
                max_rate_tilt = sensor_bounds["tilt_deg"].get("max_rate_deg_per_sec", 5.0)
                if rate_tilt > max_rate_tilt:
                    return self._reject(
                        node_id=record.node_id,
                        category="RATE_OF_CHANGE_EXCEEDED",
                        reason=f"tilt_deg change rate {rate_tilt:.2f} deg/s exceeds physical limit {max_rate_tilt} deg/s (dt={dt:.2f}s)",
                        raw_payload=raw_input,
                    )

                delta_disp = abs(record.sensors.displacement_mm - prev.sensors.displacement_mm)
                rate_disp = delta_disp / dt
                max_rate_disp = sensor_bounds["displacement_mm"].get("max_rate_mm_per_sec", 50.0)
                if rate_disp > max_rate_disp:
                    return self._reject(
                        node_id=record.node_id,
                        category="RATE_OF_CHANGE_EXCEEDED",
                        reason=f"displacement_mm change rate {rate_disp:.2f} mm/s exceeds physical limit {max_rate_disp} mm/s (dt={dt:.2f}s)",
                        raw_payload=raw_input,
                    )

        # Validated successfully! Update state
        self._last_readings[record.node_id] = record
        return ValidationResult(is_valid=True, record=record, rejection=None)

    def _reject(
        self,
        node_id: Optional[str],
        category: str,
        reason: str,
        raw_payload: Any,
    ) -> ValidationResult:
        rec = RejectionRecord(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            node_id=node_id,
            category=category,
            reason=reason,
            raw_payload=raw_payload,
        )
        self.rejections.append(rec)
        logger.warning(f"REJECTED [{category}] for node '{node_id}': {reason}")

        if self.audit_log_path:
            try:
                with open(self.audit_log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": rec.timestamp_utc,
                        "node_id": rec.node_id,
                        "category": rec.category,
                        "reason": rec.reason,
                        "raw_payload": str(rec.raw_payload)[:1000],
                    }) + "\n")
            except Exception as e:
                logger.error(f"Failed to write to audit log: {e}")

        return ValidationResult(is_valid=False, record=None, rejection=rec)
