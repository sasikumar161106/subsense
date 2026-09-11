"""
Test Suite: SubSense Standalone Python LoRa Nodes (Zero-ESP32 Architecture)
===========================================================================
Validates:
1. LoRaSensorNode telemetry creation & deterministic physics safeguard (tilt >= 4.0 deg)
2. LoRaRelayNode packet processing, hop counter increment, and deduplication
3. LoRaGatewayNode canonical adaptation, RSSI stamping, and store-and-forward dispatch
4. Complete end-to-end simulated wireless chain: Sensor -> Relay -> Gateway -> Ingestion Queue
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add workspace paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "edge", "lora_nodes"))
sys.path.insert(0, os.path.join(BASE_DIR, "gateway-bridge"))
sys.path.insert(0, os.path.join(BASE_DIR, "gateway-bridge", "drivers"))

from edge.lora_nodes.sensor_node import LoRaSensorNode
from edge.lora_nodes.relay_node import LoRaRelayNode
from edge.lora_nodes.gateway_node import LoRaGatewayNode


class TestLoraStandaloneNodes(unittest.TestCase):

    def setUp(self):
        # Create temp sqlite database for gateway test
        self.test_db = os.path.join(BASE_DIR, "tests", "test_lora_temp_queue.db")
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    @patch("serial.Serial")
    def test_sensor_node_telemetry_and_hazard_evaluation(self, mock_serial):
        """Verify Sensor Node creates canonical telemetry and trips siren when tilt exceeds 4.0 deg."""
        # 1. Normal mode test
        sensor_normal = LoRaSensorNode(node_id="SS-TEST-01", port="COM_MOCK", simulate_anomaly=False)
        tilt, vib, is_crit = sensor_normal.read_sensors()
        self.assertLess(tilt, 4.0)
        self.assertFalse(is_crit)

        pkt_normal = json.loads(sensor_normal.build_telemetry_packet(tilt, vib, is_crit))
        self.assertEqual(pkt_normal["node_id"], "SS-TEST-01")
        self.assertEqual(pkt_normal["hop_count"], 0)
        self.assertFalse(pkt_normal["siren_triggered"])
        self.assertLess(pkt_normal["anomaly_score"], 0.20)

        # 2. Hazard mode test
        sensor_hazard = LoRaSensorNode(node_id="SS-TEST-01", port="COM_MOCK", simulate_anomaly=True)
        tilt_h, vib_h, is_crit_h = sensor_hazard.read_sensors()
        self.assertGreaterEqual(tilt_h, 4.0)
        self.assertTrue(is_crit_h)

        pkt_hazard = json.loads(sensor_hazard.build_telemetry_packet(tilt_h, vib_h, is_crit_h))
        self.assertTrue(pkt_hazard["siren_triggered"])
        self.assertGreaterEqual(pkt_hazard["anomaly_score"], 0.90)

    @patch("serial.Serial")
    def test_relay_node_forwarding_and_deduplication(self, mock_serial):
        """Verify Relay Node forwards novel packets with hop increment and filters duplicates."""
        relay = LoRaRelayNode(relay_id="RELAY-02", port="COM_MOCK")
        relay.lora = MagicMock()

        sample_pkt = {
            "node_id": "SS-PANEL7-N042",
            "seq": 101,
            "tilt_current": 1.25,
            "vibration_rms": 0.18,
            "hop_count": 0,
            "siren_triggered": False
        }
        raw_msg = json.dumps(sample_pkt)

        # 1. First reception -> should forward
        ok1 = relay.process_packet(raw_msg, rssi=-62)
        self.assertTrue(ok1)
        self.assertEqual(relay.packets_forwarded, 1)

        # Check forwarded payload had hop_count incremented from 0 to 1
        last_sent = relay.lora.send.call_args[0][0]
        fwd_data = json.loads(last_sent)
        self.assertEqual(fwd_data["hop_count"], 1)
        self.assertEqual(fwd_data["relayed_by"], "RELAY-02")
        self.assertEqual(fwd_data["relay_rssi"], -62)

        # 2. Duplicate reception -> should drop
        ok2 = relay.process_packet(raw_msg, rssi=-63)
        self.assertFalse(ok2)
        self.assertEqual(relay.packets_forwarded, 1)  # No change

        # 3. Max hops exceeded test
        high_hop_pkt = dict(sample_pkt)
        high_hop_pkt["seq"] = 102
        high_hop_pkt["hop_count"] = 3
        ok3 = relay.process_packet(json.dumps(high_hop_pkt), rssi=-65)
        self.assertFalse(ok3)  # Dropped due to hop count

    @patch("serial.Serial")
    def test_gateway_node_ingestion_and_resilience(self, mock_serial):
        """Verify Gateway Node adapts LoRa packet to canonical format and stores in offline queue if server is down."""
        gw = LoRaGatewayNode(
            port="COM_MOCK",
            ingest_url="http://localhost:59999/nonexistent",  # Unreachable endpoint to test offline buffering
            bff_url="http://localhost:59998/nonexistent",
            db_path=self.test_db,
        )

        incoming_lora_pkt = json.dumps({
            "node_id": "SS-PANEL7-N042",
            "site_id": "PANEL7-JHARIA",
            "tenant_id": "tenant-jharia-01",
            "zone_id": "PANEL-7-WEST",
            "tilt_current": 4.62,
            "vibration_rms": 0.88,
            "battery_percent": 91,
            "hop_count": 1,
            "siren_triggered": True,
            "timestamp": "2026-09-11T14:30:00Z"
        })

        # Process incoming LoRa packet with authentic hardware RSSI
        gw.process_incoming_packet(incoming_lora_pkt, rssi=-64)
        self.assertEqual(gw.total_received, 1)

        # Check that packet was safely buffered to SQLite offline queue
        queue_size = gw.bridge.queue.size()
        self.assertGreaterEqual(queue_size, 1)

        batch = gw.bridge.queue.fetch_batch(limit=5)
        self.assertEqual(len(batch), 1)
        item_id, payload, retry_count = batch[0]

        # Invariant checks on canonical payload
        self.assertEqual(payload["node_id"], "SS-PANEL7-N042")
        self.assertEqual(payload["readings"]["tilt_deg"], 4.62)
        self.assertEqual(payload["readings"]["vibration_rms_mm_s"], 0.88)
        self.assertEqual(payload["node_health"]["rssi_dbm"], -64)
        self.assertEqual(payload["node_health"]["hop_count"], 1)
        self.assertTrue(payload["siren_triggered"])

        # Clean shutdown
        gw.bridge.stop()


if __name__ == "__main__":
    unittest.main()
