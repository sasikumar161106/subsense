"""
SubSense Telemetry Store
========================
High-performance time-series telemetry persistence engine.
Supports PostgreSQL / TimescaleDB with hypertable partitioning when DATABASE_URL
is configured, and transparently provides an embedded SQLite storage engine
for offline, development, and unit test environments.
"""

import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("subsense.telemetry.store")

DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "telemetry.db")


class TelemetryStore:
    """
    Thread-safe dual-backend telemetry repository (PostgreSQL/TimescaleDB + SQLite).
    """

    def __init__(self, database_url: Optional[str] = None, sqlite_path: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.sqlite_path = sqlite_path or DEFAULT_SQLITE_PATH
        self._is_postgres = bool(self.database_url and self.database_url.startswith("postgres"))
        self._lock = threading.RLock()
        self._pg_pool = None

        if self._is_postgres:
            try:
                import psycopg2
                from psycopg2 import pool
                self._pg_pool = pool.SimpleConnectionPool(1, 10, self.database_url)
                self._init_postgres()
                logger.info("[TELEMETRY STORE] Connected to PostgreSQL / TimescaleDB engine.")
            except Exception as e:
                logger.warning(f"[TELEMETRY STORE] Failed connecting to Postgres ({e}), falling back to SQLite.")
                self._is_postgres = False
                self._init_sqlite()
        else:
            self._init_sqlite()
            logger.info(f"[TELEMETRY STORE] Initialized SQLite telemetry engine at '{self.sqlite_path}'.")

    @contextmanager
    def _get_sqlite_conn(self):
        conn = sqlite3.connect(self.sqlite_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_sqlite(self) -> None:
        if self.sqlite_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.sqlite_path)), exist_ok=True)
        with self._lock, self._get_sqlite_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sensor_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    zone_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tilt_deg REAL,
                    vibration_rms_mm_s REAL,
                    displacement_mm REAL,
                    crack_index REAL,
                    sensor_availability TEXT NOT NULL,
                    node_health TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_node_ts ON sensor_telemetry (node_id, timestamp)")
            conn.commit()

    def _init_postgres(self) -> None:
        conn = self._pg_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sensor_telemetry (
                        id BIGSERIAL,
                        node_id VARCHAR(64) NOT NULL,
                        site_id VARCHAR(64) NOT NULL,
                        zone_id VARCHAR(64) NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL,
                        tilt_deg DOUBLE PRECISION,
                        vibration_rms_mm_s DOUBLE PRECISION,
                        displacement_mm DOUBLE PRECISION,
                        crack_index DOUBLE PRECISION,
                        sensor_availability JSONB NOT NULL,
                        node_health JSONB NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id, timestamp)
                    );
                    """
                )
                # Try creating TimescaleDB hypertable if extension exists
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
                    cur.execute("SELECT create_hypertable('sensor_telemetry', 'timestamp', if_not_exists => TRUE);")
                except Exception:
                    pass
                conn.commit()
        finally:
            self._pg_pool.putconn(conn)

    def insert_reading(self, reading_dict: Dict[str, Any]) -> int:
        """
        Persists a validated canonical reading into the telemetry store.
        """
        node_id = str(reading_dict.get("node_id", "UNKNOWN"))
        site_id = str(reading_dict.get("site_id", "SITE-DEMO-01"))
        zone_id = str(reading_dict.get("zone_id", "PANEL-1-ZONE-01"))
        ts = reading_dict.get("timestamp")
        if isinstance(ts, datetime):
            ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
            ts_dt = ts
        else:
            ts_str = str(ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
            ts_dt = ts_str

        readings = reading_dict.get("readings", {})
        tilt_deg = readings.get("tilt_deg")
        vib_rms = readings.get("vibration_rms_mm_s")
        disp_mm = readings.get("displacement_mm")
        crack_idx = readings.get("crack_index")

        avail_json = json.dumps(reading_dict.get("sensor_availability", {}))
        health_json = json.dumps(reading_dict.get("node_health", {}))

        if self._is_postgres and self._pg_pool:
            conn = self._pg_pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO sensor_telemetry (
                            node_id, site_id, zone_id, timestamp,
                            tilt_deg, vibration_rms_mm_s, displacement_mm, crack_index,
                            sensor_availability, node_health
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id;
                        """,
                        (node_id, site_id, zone_id, ts_dt, tilt_deg, vib_rms, disp_mm, crack_idx, avail_json, health_json),
                    )
                    row_id = cur.fetchone()[0]
                    conn.commit()
                    return int(row_id)
            finally:
                self._pg_pool.putconn(conn)
        else:
            with self._lock, self._get_sqlite_conn() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO sensor_telemetry (
                        node_id, site_id, zone_id, timestamp,
                        tilt_deg, vibration_rms_mm_s, displacement_mm, crack_index,
                        sensor_availability, node_health
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (node_id, site_id, zone_id, ts_str, tilt_deg, vib_rms, disp_mm, crack_idx, avail_json, health_json),
                )
                conn.commit()
                return int(cur.lastrowid or 0)

    def count_readings(self, node_id: Optional[str] = None) -> int:
        if self._is_postgres and self._pg_pool:
            conn = self._pg_pool.getconn()
            try:
                with conn.cursor() as cur:
                    if node_id:
                        cur.execute("SELECT COUNT(*) FROM sensor_telemetry WHERE node_id = %s", (node_id,))
                    else:
                        cur.execute("SELECT COUNT(*) FROM sensor_telemetry")
                    return int(cur.fetchone()[0])
            finally:
                self._pg_pool.putconn(conn)
        else:
            with self._lock, self._get_sqlite_conn() as conn:
                if node_id:
                    row = conn.execute("SELECT COUNT(*) AS cnt FROM sensor_telemetry WHERE node_id = ?", (node_id,)).fetchone()
                else:
                    row = conn.execute("SELECT COUNT(*) AS cnt FROM sensor_telemetry").fetchone()
                return int(row["cnt"]) if row else 0

    def get_latest_reading(self, node_id: str) -> Optional[Dict[str, Any]]:
        if self._is_postgres and self._pg_pool:
            conn = self._pg_pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, node_id, site_id, zone_id, timestamp, tilt_deg, vibration_rms_mm_s, displacement_mm, crack_index, sensor_availability, node_health "
                        "FROM sensor_telemetry WHERE node_id = %s ORDER BY timestamp DESC LIMIT 1",
                        (node_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    return {
                        "id": row[0], "node_id": row[1], "site_id": row[2], "zone_id": row[3],
                        "timestamp": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
                        "tilt_deg": row[5], "vibration_rms_mm_s": row[6],
                        "displacement_mm": row[7], "crack_index": row[8],
                        "sensor_availability": row[9] if isinstance(row[9], dict) else json.loads(row[9]),
                        "node_health": row[10] if isinstance(row[10], dict) else json.loads(row[10]),
                    }
            finally:
                self._pg_pool.putconn(conn)
        else:
            with self._lock, self._get_sqlite_conn() as conn:
                row = conn.execute(
                    "SELECT id, node_id, site_id, zone_id, timestamp, tilt_deg, vibration_rms_mm_s, displacement_mm, crack_index, sensor_availability, node_health "
                    "FROM sensor_telemetry WHERE node_id = ? ORDER BY id DESC LIMIT 1",
                    (node_id,),
                ).fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"], "node_id": row["node_id"], "site_id": row["site_id"], "zone_id": row["zone_id"],
                    "timestamp": row["timestamp"], "tilt_deg": row["tilt_deg"], "vibration_rms_mm_s": row["vibration_rms_mm_s"],
                    "displacement_mm": row["displacement_mm"], "crack_index": row["crack_index"],
                    "sensor_availability": json.loads(row["sensor_availability"]),
                    "node_health": json.loads(row["node_health"]),
                }
