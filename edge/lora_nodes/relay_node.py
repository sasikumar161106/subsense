"""
SubSense LoRa Relay Node (Board 2 / Multi-Hop Repeater)
=======================================================
Runs on Raspberry Pi, Linux, or PC with SX126x module attached.
Listens for underground sensor telemetry, filters duplicates via circular cache,
increments hop count, and forwards over LoRa to extend coverage through mine galleries.

Adapted from loramain/src/nodes/relay.py.
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Dict, Optional, Union

# Include driver and config paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, "gateway-bridge"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from drivers.sx126x import sx126x
from config import SERIAL_PORT, LORA_SETTINGS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [RELAY-NODE] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("relay-node")

DEFAULT_RELAY_ID = "RELAY-GALLERY-02"
MAX_HOPS = 3
DEDUP_CACHE_TTL_SEC = 8.0


class LoRaRelayNode:
    def __init__(
        self,
        relay_id: str = DEFAULT_RELAY_ID,
        port: str = SERIAL_PORT,
        freq: int = LORA_SETTINGS["FREQUENCY"],
    ):
        self.relay_id = relay_id
        self.port = port
        self.freq = freq

        self.lora: Optional[sx126x] = None
        self.pings_received = 0
        self.packets_forwarded = 0
        self.dedup_cache: Dict[str, float] = {}
        self.rx_buffer = ""
        self.rx_buffer_last_time = time.time()

        self._init_hardware()

    def _init_hardware(self):
        try:
            logger.info(f"Initializing LoRa Relay on {self.port} @ {self.freq} MHz (RSSI enabled)...")
            self.lora = sx126x(
                serial_num=self.port,
                freq=self.freq,
                addr=0,  # Address 0 to receive broadcasts
                power=LORA_SETTINGS["TX_POWER"],
                rssi=True,
                air_speed=LORA_SETTINGS["AIR_SPEED"],
            )
            logger.info("LoRa SX126x Relay hardware initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not connect to LoRa module on {self.port}: {e}")

    def _clean_dedup_cache(self, now: float):
        expired = [k for k, t in self.dedup_cache.items() if (now - t) > DEDUP_CACHE_TTL_SEC]
        for k in expired:
            del self.dedup_cache[k]

    def handle_incoming_chunk(self, chunk: str, rssi: int):
        now = time.time()
        if now - self.rx_buffer_last_time > 4.0:
            self.rx_buffer = ""
        self.rx_buffer_last_time = now

        self.rx_buffer += chunk

        while "{" in self.rx_buffer:
            s_idx = self.rx_buffer.find("{")
            if s_idx > 0:
                self.rx_buffer = self.rx_buffer[s_idx:]
                s_idx = 0

            found = False
            for pos in range(len(self.rx_buffer) - 1, 0, -1):
                if self.rx_buffer[pos] == "}":
                    candidate = self.rx_buffer[:pos + 1]
                    try:
                        data = json.loads(candidate)
                        self.process_packet(data, rssi)
                        self.rx_buffer = self.rx_buffer[pos + 1:]
                        found = True
                        break
                    except Exception:
                        continue
            if not found:
                if len(self.rx_buffer) > 1024:
                    self.rx_buffer = self.rx_buffer[-256:]
                break

    def process_packet(self, message: Union[str, dict], rssi: int) -> bool:
        self.pings_received += 1
        now = time.time()
        self._clean_dedup_cache(now)

        # Parse payload
        if isinstance(message, dict):
            data = dict(message)
        else:
            try:
                data = json.loads(message)
            except Exception:
                # Fallback for plain text format
                data = {"raw": message, "node_id": "UNKNOWN", "seq": self.pings_received}

        node_id = data.get("node_id") or data.get("node") or "UNKNOWN"
        seq = data.get("seq", self.pings_received)
        hop_count = int(data.get("hop_count", data.get("hops", 0)))

        # Check loop / hop threshold
        if hop_count >= MAX_HOPS:
            logger.debug(f"Dropped packet from {node_id} (max hops {MAX_HOPS} exceeded).")
            return False

        # Dedup check
        dedup_key = f"{node_id}:{seq}"
        if dedup_key in self.dedup_cache:
            logger.debug(f"Dropped duplicate packet {dedup_key}")
            return False

        self.dedup_cache[dedup_key] = now

        # Increment hop count & update RSSI
        fwd_data = dict(data)
        fwd_data["hop_count"] = hop_count + 1
        fwd_data["relayed_by"] = self.relay_id
        fwd_data["relay_rssi"] = rssi

        fwd_payload = json.dumps(fwd_data, separators=(',', ':'))

        # Retransmit over LoRa
        time.sleep(0.02)  # Fast turnaround
        if self.lora:
            self.lora.send(fwd_payload, target_addr=0xFFFF, channel=15)

        self.packets_forwarded += 1
        logger.info(
            f"Forwarded: Node={node_id} (Seq #{seq}) | Hop {hop_count} -> {fwd_data['hop_count']} | RSSI: {rssi} dBm"
        )
        return True

    def run(self):
        print(f"\n=======================================================")
        print(f"  ⛏️  SUBSENSE LORA RELAY REPEATER: {self.relay_id}")
        print(f"  Frequency: {self.freq} MHz | Serial Port: {self.port}")
        print(f"=======================================================\n")
        logger.info("Listening for underground sensor LoRa packets...")

        try:
            while True:
                if self.lora:
                    msg, rssi = self.lora.receive()
                    if msg:
                        self.handle_incoming_chunk(msg, rssi)
                time.sleep(0.01)
        except KeyboardInterrupt:
            print(f"\n[RELAY] Shutting down. Received: {self.pings_received}, Forwarded: {self.packets_forwarded}")
        finally:
            if self.lora:
                self.lora.close()


def run_relay(relay_id: Optional[str] = None, port: Optional[str] = None):
    node = LoRaRelayNode(
        relay_id=relay_id or DEFAULT_RELAY_ID,
        port=port or SERIAL_PORT,
    )
    node.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SubSense LoRa Relay Node")
    parser.add_argument("--id", type=str, default=DEFAULT_RELAY_ID, help="Relay ID")
    parser.add_argument("--port", type=str, default=SERIAL_PORT, help="Serial port")
    parser.add_argument("--freq", type=int, default=LORA_SETTINGS["FREQUENCY"], help="Frequency in MHz")

    args = parser.parse_args()
    node = LoRaRelayNode(
        relay_id=args.id,
        port=args.port,
        freq=args.freq,
    )
    node.run()
