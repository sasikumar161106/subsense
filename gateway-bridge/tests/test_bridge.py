"""
Unit & Integration Tests for SubSense Gateway Bridge Service
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add gateway-bridge to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bridge import GatewayBridge, OfflineQueue, SerialJSONExtractor, to_canonical


class TestGatewayBridge(unittest.TestCase):

    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_file.close()
        self.db_path = self.temp_db_file.name

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_canonical_adapter_shape_and_invariants(self):
        """Verify firmware payload adapts to the exact canonical SensorReading contract."""
        raw_firmware_payload = {
            "node_id": "SS-NODE-01",
            "tilt_current": 1.825,
            "vibration_rms": 0.419,
            "battery_percent": 94,
            "rssi_dbm": -68,
            "hop_count": 1,
            "window_end_ts": "2026-09-10T11:15:00Z"
        }

        canonical = to_canonical(raw_firmware_payload)

        # 1. Structure validation
        self.assertEqual(canonical["node_id"], "SS-NODE-01")
        self.assertEqual(canonical["site_id"], "PANEL7-JHARIA")
        self.assertEqual(canonical["tenant_id"], "tenant-jharia-01")
        self.assertEqual(canonical["zone_id"], "PANEL-1-ZONE-01")
        self.assertEqual(canonical["timestamp"], "2026-09-10T11:15:00Z")

        # 2. Readings validation (physical MPU6050 channels)
        self.assertAlmostEqual(canonical["readings"]["tilt_deg"], 1.825)
        self.assertAlmostEqual(canonical["readings"]["vibration_rms_mm_s"], 0.419)

        # 3. CRITICAL INVARIANT: Zero fabrication of missing sensors
        self.assertIsNone(canonical["readings"]["displacement_mm"])
        self.assertIsNone(canonical["readings"]["crack_index"])
        self.assertTrue(canonical["sensor_availability"]["tilt"])
        self.assertTrue(canonical["sensor_availability"]["vibration"])
        self.assertFalse(canonical["sensor_availability"]["displacement"])
        self.assertFalse(canonical["sensor_availability"]["crack"])

        # 4. Node health metadata
        self.assertEqual(canonical["node_health"]["battery_percent"], 94)
        self.assertEqual(canonical["node_health"]["rssi_dbm"], -68)
        self.assertEqual(canonical["node_health"]["hop_count"], 1)

    def test_serial_json_extractor_handles_gateway_banners(self):
        """Verify stream parser extracts JSON from messy serial output with banner headers."""
        extractor = SerialJSONExtractor()

        raw_serial_stream = [
            "================================================================================",
            "[GATEWAY MESH RX] Received from Origin Node 24:6F:28:1A:BC:01 (142 bytes):",
            "--------------------------------------------------------------------------------",
            "{",
            '  "node_id": "SS-NODE-01",',
            '  "tilt_current": 2.15,',
            '  "vibration_rms": 0.55',
            "}",
            "================================================================================",
        ]

        results = []
        for line in raw_serial_stream:
            extracted = extractor.feed_line(line)
            if extracted:
                results.extend(extracted)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["node_id"], "SS-NODE-01")
        self.assertAlmostEqual(results[0]["tilt_current"], 2.15)
        self.assertAlmostEqual(results[0]["vibration_rms"], 0.55)

    @patch("requests.post")
    def test_offline_queue_persists_on_failed_post(self, mock_post):
        """Verify that when the ingestion endpoint is down, readings are queued to SQLite."""
        import requests
        mock_post.side_effect = requests.RequestException("Connection refused")

        bridge = GatewayBridge(
            ingest_url="http://localhost:8000/api/v1/ingest/telemetry",
            db_path=self.db_path,
        )

        sample_raw = {
            "node_id": "SS-NODE-02",
            "tilt_current": 3.4,
            "vibration_rms": 0.72
        }

        # Queue should be empty initially
        self.assertEqual(bridge.queue.size(), 0)

        # Process reading (will fail HTTP POST and buffer to SQLite)
        canonical = bridge.process_raw_dict(sample_raw)

        # Queue size must be 1
        self.assertEqual(bridge.queue.size(), 1)

        # Verify queued item content
        batch = bridge.queue.fetch_batch(limit=5)
        self.assertEqual(len(batch), 1)
        item_id, payload, retry_count = batch[0]
        self.assertEqual(payload["node_id"], "SS-NODE-02")
        self.assertAlmostEqual(payload["readings"]["tilt_deg"], 3.4)
        self.assertIsNone(payload["readings"]["displacement_mm"])
        self.assertFalse(payload["sensor_availability"]["displacement"])

    def test_offline_queue_drain_on_recovery(self):
        """Verify queued items are replayed and drained when ingestion endpoint recovers."""
        queue = OfflineQueue(db_path=self.db_path)

        # Enqueue 3 items
        for i in range(3):
            queue.enqueue(
                {"node_id": f"NODE-{i}", "readings": {"tilt_deg": 1.0 * i}},
                error_msg="Connection refused"
            )

        self.assertEqual(queue.size(), 3)

        # Simulate replay worker draining items with mock success
        batch = queue.fetch_batch(limit=10)
        self.assertEqual(len(batch), 3)

        for item_id, payload, retries in batch:
            queue.remove(item_id)

        self.assertEqual(queue.size(), 0)


if __name__ == "__main__":
    unittest.main()
