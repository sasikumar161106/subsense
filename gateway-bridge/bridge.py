"""
SubSense Gateway Bridge Service
===============================
Reads line-delimited and block JSON emitted by the ESP32 Gateway Node over
USB serial (115200 baud), maps firmware fields to the canonical SensorReading
contract, and POSTs the canonical payload to the AI/ML ingestion service.

Ground Rule Compliance:
- Never fabricate sensor data: Only gyro/accelerometer (MPU6050) is physically wired.
- displacement and crack are strictly carried as explicit null with
  sensor_availability flags set to false.
- Offline persistence: On failed POST, buffers into a local SQLite queue and
  retries via a background worker thread.
"""

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [GATEWAY-BRIDGE] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("gateway-bridge")

DEFAULT_PORT = "COM5"
DEFAULT_BAUD = 115200
DEFAULT_INGEST_URL = "http://localhost:8000/api/v1/ingest/telemetry"
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "offline_queue.db")
DEFAULT_RETRY_INTERVAL_SEC = 5.0


# ==============================================================================
# 1. Canonical Contract Adapter
# ==============================================================================

def format_timestamp(raw_ts: Any) -> str:
    """Ensure timestamp is formatted as an ISO 8601 UTC string."""
    if isinstance(raw_ts, str) and len(raw_ts) >= 19 and ("T" in raw_ts or "-" in raw_ts):
        if not raw_ts.endswith("Z") and not ("+" in raw_ts[-6:] or "-" in raw_ts[-6:]):
            return raw_ts + "Z"
        return raw_ts
    if isinstance(raw_ts, (int, float)):
        # Epoch seconds or milliseconds
        if raw_ts > 1e11:
            raw_ts /= 1000.0
        try:
            return datetime.fromtimestamp(raw_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_canonical(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map raw firmware/gateway fields to the canonical SubSense SensorReading contract.

    STRICT INVARIANT:
    - Only tilt and vibration may have numeric values.
    - displacement and crack are ALWAYS None with availability False.
    """
    # Extract node ID
    node_id = raw.get("node_id") or raw.get("node") or "SS-NODE-01"
    site_id = raw.get("site_id") or "SITE-DEMO-01"
    zone_id = raw.get("zone_id") or "PANEL-1-ZONE-01"

    # Extract timestamp from various possible firmware keys
    raw_ts = (
        raw.get("timestamp")
        or raw.get("window_end_ts")
        or raw.get("last_inference_ts")
        or raw.get("ts")
    )
    timestamp_iso = format_timestamp(raw_ts)

    # Extract tilt (firmware uses 'tilt_current', 'tilt', or 'readings.tilt_deg')
    tilt_val: Optional[float] = None
    if "tilt_current" in raw and raw["tilt_current"] is not None:
        try:
            tilt_val = round(float(raw["tilt_current"]), 4)
        except (ValueError, TypeError):
            tilt_val = None
    elif "tilt" in raw and raw["tilt"] is not None:
        try:
            tilt_val = round(float(raw["tilt"]), 4)
        except (ValueError, TypeError):
            tilt_val = None
    elif "readings" in raw and isinstance(raw["readings"], dict):
        sub = raw["readings"].get("tilt_deg") or raw["readings"].get("tilt")
        if sub is not None:
            try:
                tilt_val = round(float(sub), 4)
            except (ValueError, TypeError):
                tilt_val = None

    # Extract vibration (firmware uses 'vibration_rms', 'vib', or 'readings.vibration_rms_mm_s')
    vib_val: Optional[float] = None
    if "vibration_rms" in raw and raw["vibration_rms"] is not None:
        try:
            vib_val = round(float(raw["vibration_rms"]), 4)
        except (ValueError, TypeError):
            vib_val = None
    elif "vibration" in raw and raw["vibration"] is not None:
        try:
            vib_val = round(float(raw["vibration"]), 4)
        except (ValueError, TypeError):
            vib_val = None
    elif "readings" in raw and isinstance(raw["readings"], dict):
        sub = raw["readings"].get("vibration_rms_mm_s") or raw["readings"].get("vibration")
        if sub is not None:
            try:
                vib_val = round(float(sub), 4)
            except (ValueError, TypeError):
                vib_val = None

    # Node health metadata
    health_dict = raw.get("node_health") if isinstance(raw.get("node_health"), dict) else {}
    battery_pct = raw.get("battery_percent") or health_dict.get("battery_percent") or 94
    rssi_dbm = raw.get("rssi_dbm") or health_dict.get("rssi_dbm") or -68
    hop_count = raw.get("hop_count") or health_dict.get("hop_count") or 1

    try:
        battery_pct = int(battery_pct)
    except (ValueError, TypeError):
        battery_pct = 94

    try:
        rssi_dbm = int(rssi_dbm)
    except (ValueError, TypeError):
        rssi_dbm = -68

    try:
        hop_count = int(hop_count)
    except (ValueError, TypeError):
        hop_count = 1

    canonical: Dict[str, Any] = {
        "node_id": str(node_id),
        "site_id": str(site_id),
        "zone_id": str(zone_id),
        "timestamp": timestamp_iso,
        "readings": {
            "tilt_deg": tilt_val,
            "vibration_rms_mm_s": vib_val,
            "displacement_mm": None,
            "crack_index": None,
        },
        "sensor_availability": {
            "tilt": tilt_val is not None,
            "vibration": vib_val is not None,
            "displacement": False,
            "crack": False,
        },
        "node_health": {
            "battery_percent": battery_pct,
            "rssi_dbm": rssi_dbm,
            "hop_count": hop_count,
        },
    }

    return canonical


from contextlib import contextmanager

# ==============================================================================
# 2. Resilient Offline SQLite Queue
# ==============================================================================

class OfflineQueue:
    """Thread-safe SQLite-backed FIFO queue for telemetry packets."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS offline_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    retry_count INTEGER DEFAULT 0,
                    last_error TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_retry ON offline_telemetry (retry_count)")
            conn.commit()

    def enqueue(self, payload: Dict[str, Any], error_msg: str = "") -> int:
        payload_str = json.dumps(payload)
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO offline_telemetry (payload_json, last_error) VALUES (?, ?)",
                (payload_str, error_msg[:500]),
            )
            conn.commit()
            item_id = cur.lastrowid or 0
        logger.info(f"[OFFLINE QUEUE] Buffered payload to SQLite (ID: {item_id}, Queue size: {self.size()})")
        return item_id

    def fetch_batch(self, limit: int = 25) -> List[Tuple[int, Dict[str, Any], int]]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, payload_json, retry_count FROM offline_telemetry ORDER BY id ASC LIMIT ?",
                (limit,),
            ).fetchall()
            results = []
            for r in rows:
                try:
                    payload = json.loads(r["payload_json"])
                    results.append((r["id"], payload, r["retry_count"]))
                except Exception as e:
                    logger.error(f"[OFFLINE QUEUE] Corrupt record {r['id']}, deleting: {e}")
                    conn.execute("DELETE FROM offline_telemetry WHERE id = ?", (r["id"],))
                    conn.commit()
            return results

    def remove(self, item_id: int) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute("DELETE FROM offline_telemetry WHERE id = ?", (item_id,))
            conn.commit()

    def increment_retry(self, item_id: int, error_msg: str) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                "UPDATE offline_telemetry SET retry_count = retry_count + 1, last_error = ? WHERE id = ?",
                (error_msg[:500], item_id),
            )
            conn.commit()

    def size(self) -> int:
        with self._lock, self._get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM offline_telemetry").fetchone()
            return int(row["cnt"]) if row else 0


# ==============================================================================
# 3. Stream Parser: Extraction from Serial Feed
# ==============================================================================

class SerialJSONExtractor:
    """
    Extracts valid JSON objects from a stream of serial lines, safely handling
    debug header banners, multi-line JSON blocks, or standard line-delimited JSON.
    """

    def __init__(self):
        self._buffer = ""
        self._brace_depth = 0
        self._inside_json = False

    def feed_line(self, line: str) -> List[Dict[str, Any]]:
        extracted = []
        clean = line.strip()
        if not clean:
            return extracted

        # Fast path: entire line is a single JSON object
        if clean.startswith("{") and clean.endswith("}"):
            try:
                parsed = json.loads(clean)
                if isinstance(parsed, dict):
                    extracted.append(parsed)
                    return extracted
            except json.JSONDecodeError:
                pass

        # Multi-line / mixed banner parser
        for char in line:
            if char == "{":
                if self._brace_depth == 0:
                    self._buffer = "{"
                    self._inside_json = True
                else:
                    self._buffer += char
                self._brace_depth += 1
            elif char == "}":
                if self._inside_json:
                    self._buffer += char
                    self._brace_depth -= 1
                    if self._brace_depth == 0:
                        self._inside_json = False
                        try:
                            candidate = json.loads(self._buffer)
                            if isinstance(candidate, dict):
                                extracted.append(candidate)
                        except json.JSONDecodeError:
                            pass
                        self._buffer = ""
            elif self._inside_json:
                self._buffer += char

        return extracted


# ==============================================================================
# 4. Gateway Bridge Pipeline & Background Queue Worker
# ==============================================================================

class GatewayBridge:
    def __init__(
        self,
        port: str = DEFAULT_PORT,
        baud: int = DEFAULT_BAUD,
        ingest_url: str = DEFAULT_INGEST_URL,
        db_path: str = DEFAULT_DB_PATH,
        retry_interval: float = DEFAULT_RETRY_INTERVAL_SEC,
    ):
        self.port = port
        self.baud = baud
        self.ingest_url = ingest_url
        self.queue = OfflineQueue(db_path)
        self.retry_interval = retry_interval
        self.extractor = SerialJSONExtractor()

        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

    def start_worker(self) -> None:
        self._running = True
        self._worker_thread = threading.Thread(target=self._retry_worker, daemon=True, name="BridgeRetryWorker")
        self._worker_thread.start()
        logger.info(f"Background retry worker thread started (polling every {self.retry_interval}s)")

    def stop(self) -> None:
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)
        logger.info("Gateway bridge stopped.")

    def forward_reading(self, payload: Dict[str, Any]) -> bool:
        """Attempt to POST canonical reading to AI/ML ingestion service."""
        try:
            resp = requests.post(self.ingest_url, json=payload, timeout=3.0)
            if resp.status_code in (200, 201, 202):
                logger.info(
                    f"[FORWARDED -> INGESTION] Node: {payload['node_id']} | "
                    f"Tilt: {payload['readings']['tilt_deg']}° | "
                    f"Vib: {payload['readings']['vibration_rms_mm_s']} mm/s | "
                    f"HTTP {resp.status_code}"
                )
                return True
            else:
                err_msg = f"HTTP {resp.status_code}: {resp.text[:100]}"
                logger.warning(f"[INGESTION ERROR] {err_msg} -> buffering to offline queue")
                self.queue.enqueue(payload, err_msg)
                return False
        except requests.RequestException as exc:
            err_msg = f"Connection failed: {str(exc)}"
            logger.warning(f"[INGESTION OFFLINE] {err_msg} -> buffering to offline queue")
            self.queue.enqueue(payload, err_msg)
            return False

    def process_raw_dict(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw dict to canonical format and forward to ingestion."""
        canonical = to_canonical(raw_data)
        self.forward_reading(canonical)
        return canonical

    def process_serial_line(self, line: str) -> List[Dict[str, Any]]:
        """Feed a serial string line, parse any JSON objects, and forward each."""
        parsed_items = self.extractor.feed_line(line)
        results = []
        for raw in parsed_items:
            canonical = self.process_raw_dict(raw)
            results.append(canonical)
        return results

    def _retry_worker(self) -> None:
        """Background thread that continuously retries draining the SQLite offline queue."""
        while self._running:
            try:
                queue_size = self.queue.size()
                if queue_size > 0:
                    batch = self.queue.fetch_batch(limit=10)
                    for item_id, payload, retry_count in batch:
                        if not self._running:
                            break
                        try:
                            resp = requests.post(self.ingest_url, json=payload, timeout=3.0)
                            if resp.status_code in (200, 201, 202):
                                self.queue.remove(item_id)
                                logger.info(f"[OFFLINE REPLAY SUCCESS] Dispatched queued packet ID {item_id} (Node: {payload.get('node_id')})")
                            else:
                                self.queue.increment_retry(item_id, f"HTTP {resp.status_code}")
                                break  # Stop batch on failure to maintain FIFO order
                        except requests.RequestException as e:
                            self.queue.increment_retry(item_id, str(e))
                            break  # Backend still down; back off
            except Exception as e:
                logger.error(f"[RETRY WORKER ERROR] {e}")

            time.sleep(self.retry_interval)

    def run_serial_loop(self) -> None:
        """Connect to hardware serial port and stream data."""
        import serial
        logger.info(f"Opening Gateway Serial Port '{self.port}' at {self.baud} baud...")
        try:
            ser = serial.Serial(self.port, self.baud, timeout=1.0)
            logger.info(f"Serial port {self.port} successfully connected. Listening for Gateway packets...")
            self.start_worker()
            while self._running:
                raw_bytes = ser.readline()
                if not raw_bytes:
                    continue
                line = raw_bytes.decode(errors="ignore")
                self.process_serial_line(line)
        except serial.SerialException as e:
            logger.error(f"Failed to connect to serial port {self.port}: {e}")
            raise


# ==============================================================================
# 5. CLI & Entry Point
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="SubSense Gateway Serial-to-Cloud Bridge")
    parser.add_argument("--port", default=os.getenv("SER_PORT", DEFAULT_PORT), help="Serial port (e.g. COM5, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=int(os.getenv("SER_BAUD", str(DEFAULT_BAUD))), help="Serial baud rate (default: 115200)")
    parser.add_argument("--ingest-url", default=os.getenv("INGEST_URL", DEFAULT_INGEST_URL), help="AI/ML Ingestion URL")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Path to offline SQLite database")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode generating sample Gateway packets")
    args = parser.parse_args()

    bridge = GatewayBridge(
        port=args.port,
        baud=args.baud,
        ingest_url=args.ingest_url,
        db_path=args.db_path,
    )

    if args.mock:
        logger.info("Starting Gateway Bridge in --mock mode...")
        bridge.start_worker()
        sample_scenarios = [
            {"node_id": "SS-NODE-01", "tilt_current": 0.45, "vibration_rms": 0.08, "battery_percent": 95, "rssi_dbm": -62, "hop_count": 1},
            {"node_id": "SS-NODE-01", "tilt_current": 1.25, "vibration_rms": 0.22, "battery_percent": 94, "rssi_dbm": -65, "hop_count": 1},
            {"node_id": "SS-NODE-01", "tilt_current": 4.15, "vibration_rms": 0.88, "battery_percent": 93, "rssi_dbm": -67, "hop_count": 1},
        ]
        try:
            for i, scenario in enumerate(sample_scenarios):
                logger.info(f"[MOCK PACKET {i+1}/{len(sample_scenarios)}] Simulating gateway arrival...")
                # Format exactly as gateway serial output with banner
                mock_stream = (
                    "\n================================================================================\n"
                    f"[GATEWAY MESH RX] Received from Origin Node 24:6F:28:1A:BC:01 (142 bytes):\n"
                    "--------------------------------------------------------------------------------\n"
                    + json.dumps(scenario, indent=2) + "\n"
                    "================================================================================\n"
                )
                for line in mock_stream.splitlines():
                    bridge.process_serial_line(line)
                time.sleep(1.0)
            logger.info("Mock demonstration complete.")
        finally:
            bridge.stop()
    else:
        try:
            bridge.run_serial_loop()
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        finally:
            bridge.stop()


if __name__ == "__main__":
    main()
