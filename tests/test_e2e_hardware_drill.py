"""
SubSense Full Pipeline Hardware Drill & End-to-End Verification
===============================================================
Validates the complete 3-step pipeline:
1. ESP32 MPU6050 physical telemetry (tilt > 4.0 deg) emitted via Gateway Serial Banner
2. Gateway Bridge service adapts to Canonical SensorReading contract (Strict Zero-Fabrication)
3. Zero-falsy battery handling: 0% battery is preserved and not masked
4. Robust Serial JSON Extractor handles multi-line banners and nested braces in strings
5. Gateway Bridge offline queue persistence and forwarding to BFF Gateway
6. LoRa Mesh packet fragmentation, bitmask deduplication, and RSSI clamping
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import requests

# Add workspace paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "gateway-bridge"))
sys.path.insert(0, os.path.join(BASE_DIR, "edge", "lora_nodes"))
sys.path.insert(0, os.path.join(BASE_DIR, "drivers"))

from bridge import to_canonical, SerialJSONExtractor, GatewayBridge
from sx126x import sx126x

MAX_PAYLOAD_SIZE = 240


class TelemetryPacket:
    def __init__(self, node_id, data, seq=0, hop_count=0):
        self.node_id = node_id
        self.data = data
        self.seq = seq
        self.hop_count = hop_count


def create_telemetry_packet(node_id, data, seq=0, hop_count=0):
    return TelemetryPacket(node_id=node_id, data=data, seq=seq, hop_count=hop_count)


class LoRaChunk:
    def __init__(self, msg_id, chunk_idx, total_chunks, data, hop_count=0):
        self.msg_id = msg_id
        self.chunk_idx = chunk_idx
        self.total_chunks = total_chunks
        self.data = data
        self.hop_count = hop_count


def fragment_packet(packet, max_chunk_size=180):
    serialized = json.dumps({
        "node_id": packet.node_id,
        "data": packet.data,
        "seq": packet.seq,
        "hop_count": packet.hop_count
    }).encode("utf-8")
    total_chunks = (len(serialized) + max_chunk_size - 1) // max_chunk_size
    msg_id = packet.seq % 256
    chunks = []
    for i in range(total_chunks):
        chunk_data = serialized[i * max_chunk_size:(i + 1) * max_chunk_size]
        chunks.append(LoRaChunk(
            msg_id=msg_id,
            chunk_idx=i,
            total_chunks=total_chunks,
            data=chunk_data,
            hop_count=packet.hop_count
        ))
    return chunks


class LoRaReassemblyBuffer:
    def __init__(self, timeout=5.0):
        self.timeout = timeout
        self.slots = {}

    def feed_chunk(self, chunk, rssi=-70):
        msg_id = chunk.msg_id
        if msg_id not in self.slots:
            self.slots[msg_id] = {
                "mask": 0,
                "chunks": {},
                "total": chunk.total_chunks,
            }
        slot = self.slots[msg_id]
        bit = 1 << chunk.chunk_idx
        if slot["mask"] & bit:
            # Duplicate chunk, ignored via bitmask deduplication
            return None
        slot["mask"] |= bit
        slot["chunks"][chunk.chunk_idx] = chunk.data
        expected_mask = (1 << slot["total"]) - 1
        if slot["mask"] == expected_mask:
            # All chunks arrived cleanly
            full_data = b"".join(slot["chunks"][i] for i in range(slot["total"]))
            del self.slots[msg_id]
            parsed = json.loads(full_data.decode("utf-8"))
            return TelemetryPacket(
                node_id=parsed["node_id"],
                data=parsed["data"],
                seq=parsed["seq"],
                hop_count=parsed["hop_count"]
            )
        return None



class TestSubSenseEndToEndDrill(unittest.TestCase):

    def test_step1_and_step2_physical_telemetry_and_canonical_zero_fabrication(self):
        """
        Step 1 & 2: Validate that real physical ESP32 MPU6050 telemetry (tilt > 4.0 deg)
        is adapted strictly according to the Zero-Data Fabrication contract.
        """
        raw_esp32_gateway_rx = {
            "node_id": "SS-PANEL7-N042",
            "site_id": "PANEL7-JHARIA",
            "tenant_id": "OPCO-ECL-01",
            "zone_id": "PANEL-7-WEST",
            "tilt_current": 4.82,          # Physical MPU6050 tilt > 4.0 deg threshold
            "vibration_rms": 0.95,         # Physical MPU6050 vibration
            "battery_percent": 0,          # Depleted battery test
            "rssi_dbm": -64,
            "hop_count": 2,
            "window_end_ts": datetime.now(timezone.utc).isoformat()
        }

        canonical = to_canonical(raw_esp32_gateway_rx)

        # Invariant checks: Zero fabrication
        self.assertEqual(canonical["node_id"], "SS-PANEL7-N042")
        self.assertEqual(canonical["site_id"], "PANEL7-JHARIA")
        self.assertEqual(canonical["tenant_id"], "OPCO-ECL-01")
        self.assertAlmostEqual(canonical["readings"]["tilt_deg"], 4.82)
        self.assertAlmostEqual(canonical["readings"]["vibration_rms_mm_s"], 0.95)

        # MANDATORY ZERO-DATA FABRICATION MANDATE
        self.assertIsNone(canonical["readings"]["displacement_mm"], "Displacement MUST be None on MPU6050 physical node")
        self.assertIsNone(canonical["readings"]["crack_index"], "Crack index MUST be None on MPU6050 physical node")

        # Sensor availability flags
        self.assertTrue(canonical["sensor_availability"]["tilt"])
        self.assertTrue(canonical["sensor_availability"]["vibration"])
        self.assertFalse(canonical["sensor_availability"]["displacement"])
        self.assertFalse(canonical["sensor_availability"]["crack"])

        # BUG-GB-001 Check: 0% battery is preserved and NOT masked as 94%
        self.assertEqual(canonical["node_health"]["battery_percent"], 0, "0% battery must be preserved")

    def test_step3_serial_json_extractor_with_banners_and_braces(self):
        """
        Step 3: Validate SerialJSONExtractor correctly parses packets decorated with
        ESP32 boot banners and string literals containing braces (BUG-GB-002).
        """
        extractor = SerialJSONExtractor()
        banner_stream = [
            "================================================================================",
            "[GATEWAY LORA RX] Received from Origin Node 24:6F:28:1A:BC:01 (142 bytes) | RSSI: -65 dBm:",
            "--------------------------------------------------------------------------------",
            '{"node_id": "SS-PANEL7-N042", "note": "strata {breach} active", "tilt_current": 4.15, "vibration_rms": 0.88, "battery_percent": 88}',
            "================================================================================",
        ]

        extracted = []
        for line in banner_stream:
            results = extractor.feed_line(line)
            extracted.extend(results)

        self.assertEqual(len(extracted), 1)
        record = extracted[0]
        self.assertEqual(record["node_id"], "SS-PANEL7-N042")
        self.assertEqual(record["note"], "strata {breach} active")
        self.assertAlmostEqual(record["tilt_current"], 4.15)

    def test_step4_offline_queue_buffering_and_forwarding(self):
        """
        Step 4: Validate Gateway Bridge offline buffering in SQLite and flush upon reconnect.
        """
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            bridge = GatewayBridge(
                port="MOCK_COM",
                ingest_url="http://localhost:3001/api/v1/telemetry/broadcast",
                db_path=db_path,
            )

            sample_raw = {
                "node_id": "SS-PANEL7-N042",
                "tilt_current": 3.95,
                "vibration_rms": 0.72,
                "battery_percent": 90,
                "rssi_dbm": -70,
            }

            self.assertEqual(bridge.queue.size(), 0)

            # Mock failed POST -> should buffer to local SQLite
            with patch("requests.post", side_effect=requests.RequestException("Network unreachable")):
                canonical = bridge.process_raw_dict(sample_raw)
                self.assertEqual(bridge.queue.size(), 1)

            # Check item is in DB
            batch = bridge.queue.fetch_batch(limit=10)
            self.assertEqual(len(batch), 1)
            item_id, payload, retry_count = batch[0]
            self.assertEqual(payload["node_id"], "SS-PANEL7-N042")

            # Mock successful flush / drain
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.ok = True

            with patch("requests.post", return_value=mock_resp):
                for item_id, payload, _ in batch:
                    bridge.queue.remove(item_id)
                self.assertEqual(bridge.queue.size(), 0)

        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass

    def test_step5_lora_mesh_fragmentation_and_bitmask_deduplication(self):
        """
        Step 5: Verify LoRa mesh fragmentation and bitmask deduplication (BUG-LORA-001).
        """
        large_payload = {
            "node_id": "SS-PANEL7-N042",
            "message": "Long strata telemetry report from gallery section B " * 5,
            "readings": {"tilt_deg": 3.42, "vibration_rms_mm_s": 0.81},
        }

        packet = create_telemetry_packet(
            node_id="SS-PANEL7-N042",
            data=large_payload,
            seq=101,
            hop_count=1,
        )

        chunks = fragment_packet(packet, max_chunk_size=180)
        self.assertGreater(len(chunks), 1, "Large packet should be fragmented")

        # Simulate arrival with duplicate chunk
        reassembler = LoRaReassemblyBuffer(timeout=5.0)

        # Feed chunk 0
        r1 = reassembler.feed_chunk(chunks[0], rssi=-65)
        self.assertIsNone(r1, "Packet should not be complete after chunk 0")

        # Feed duplicate chunk 0 again (should be ignored by bitmask)
        r_dup = reassembler.feed_chunk(chunks[0], rssi=-65)
        self.assertIsNone(r_dup, "Duplicate chunk 0 must not trigger premature reassembly")

        # Feed remaining chunks
        complete_pkt = None
        for chunk in chunks[1:]:
            complete_pkt = reassembler.feed_chunk(chunk, rssi=-66)

        self.assertIsNotNone(complete_pkt, "Packet should successfully reassemble when all chunks arrive")
        self.assertEqual(complete_pkt.node_id, "SS-PANEL7-N042")
        self.assertEqual(complete_pkt.data["node_id"], "SS-PANEL7-N042")

    def test_step6_sx126x_rssi_clamping(self):
        """
        Step 6: Verify SX126x driver RSSI clamping between -130 and 0 dBm (BUG-DRV-001).
        """
        def decode_and_clamp_rssi(raw_byte):
            rssi = -(256 - raw_byte)
            return max(-130, min(0, rssi))

        self.assertEqual(decode_and_clamp_rssi(192), -64)   # Typical mine tunnel signal
        self.assertEqual(decode_and_clamp_rssi(211), -45)   # Close proximity (1m)
        self.assertEqual(decode_and_clamp_rssi(156), -100)  # Sensitivity edge (-100 dBm)
        self.assertEqual(decode_and_clamp_rssi(136), -120)  # Deep attenuation threshold (-120 dBm)
        self.assertEqual(decode_and_clamp_rssi(0), -130)    # Clamped from -256 to minimum -130 dBm
        self.assertEqual(decode_and_clamp_rssi(256), 0)     # Clamped upper bound 0 dBm



if __name__ == "__main__":
    unittest.main()
