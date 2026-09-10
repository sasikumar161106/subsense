"""
Unit and Integration Tests for Canonical Ingestion Endpoint & Telemetry Store
"""

import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from models.serving.app import app, telemetry_store


class TestCanonicalIngestion(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_canonical_ingestion_endpoint_success(self):
        """Test POST /api/v1/ingest/telemetry with canonical gyro-only SensorReading payload."""
        payload = {
            "node_id": "SS-CANON-01",
            "site_id": "SITE-DEMO-01",
            "zone_id": "PANEL-1-ZONE-01",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "readings": {
                "tilt_deg": 1.45,
                "vibration_rms_mm_s": 0.38,
                "displacement_mm": None,
                "crack_index": None
            },
            "sensor_availability": {
                "tilt": True,
                "vibration": True,
                "displacement": False,
                "crack": False
            },
            "node_health": {
                "battery_percent": 96,
                "rssi_dbm": -64,
                "hop_count": 1
            }
        }

        response = self.client.post("/api/v1/ingest/telemetry", json=payload)
        self.assertEqual(response.status_code, 201, f"Ingestion failed: {response.text}")
        data = response.json()
        self.assertEqual(data["status"], "INGESTED")
        self.assertEqual(data["node_id"], "SS-CANON-01")
        self.assertIn("row_id", data)

        # Verify row persisted in telemetry store
        persisted = telemetry_store.get_latest_reading("SS-CANON-01")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["node_id"], "SS-CANON-01")
        self.assertAlmostEqual(persisted["tilt_deg"], 1.45)
        self.assertAlmostEqual(persisted["vibration_rms_mm_s"], 0.38)
        self.assertIsNone(persisted["displacement_mm"])
        self.assertIsNone(persisted["crack_index"])
        self.assertTrue(persisted["sensor_availability"]["tilt"])
        self.assertFalse(persisted["sensor_availability"]["displacement"])
        self.assertFalse(persisted["sensor_availability"]["crack"])

        # Verify GET /api/v1/ingest/telemetry/{node_id}/latest
        get_res = self.client.get("/api/v1/ingest/telemetry/SS-CANON-01/latest")
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.json()
        self.assertEqual(get_data["node_id"], "SS-CANON-01")
        self.assertAlmostEqual(get_data["tilt_deg"], 1.45)

    def test_canonical_ingestion_rejects_malformed_data(self):
        """Test rejection when tilt is physically impossible (> 45 deg)."""
        payload = {
            "node_id": "SS-CANON-02",
            "site_id": "SITE-DEMO-01",
            "zone_id": "PANEL-1-ZONE-01",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "readings": {
                "tilt_deg": 89.9,  # Exceeds max physical limit of 45.0 deg
                "vibration_rms_mm_s": 0.1,
                "displacement_mm": None,
                "crack_index": None
            },
            "sensor_availability": {
                "tilt": True,
                "vibration": True,
                "displacement": False,
                "crack": False
            },
            "node_health": {
                "battery_percent": 90,
                "rssi_dbm": -70,
                "hop_count": 1
            }
        }

        response = self.client.post("/api/v1/ingest/telemetry", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("PHYSICAL_BOUND_VIOLATION", response.text)


if __name__ == "__main__":
    unittest.main()
