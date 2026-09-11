"""
SubSense LoRa Gateway Node (Board 3 / Surface Master Receiver)
==============================================================
Runs on Raspberry Pi, Linux, or PC with SX126x module attached.
Listens for LoRa packets from underground Sensor Nodes (direct or via Relays),
extracts authentic physical RSSI, maps to the Canonical SensorReading contract,
and dispatches directly to the AI/ML ingestion service & BFF Gateway with offline SQLite resilience.

Adapted from loramain/src/nodes/master.py and gateway-bridge/bridge.py.
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Dict, Optional

# Include driver, bridge, and config paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, "gateway-bridge"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from drivers.sx126x import sx126x
from bridge import to_canonical, GatewayBridge
from config import (
    SERIAL_PORT,
    LORA_SETTINGS,
    AIML_INGEST_URL,
    BFF_BROADCAST_URL,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [GATEWAY-NODE] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gateway-node")


class Colors:
    HEADER = '\033[95m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


class LoRaGatewayNode:
    def __init__(
        self,
        port: str = SERIAL_PORT,
        freq: int = LORA_SETTINGS["FREQUENCY"],
        ingest_url: str = AIML_INGEST_URL,
        bff_url: str = BFF_BROADCAST_URL,
        db_path: Optional[str] = None,
    ):
        self.port = port
        self.freq = freq
        self.ingest_url = ingest_url
        self.bff_url = bff_url

        self.lora: Optional[sx126x] = None
        self.total_received = 0
        self.total_dispatched = 0
        self.rx_buffer = ""
        self.rx_buffer_last_time = time.time()

        # Initialize Gateway Bridge for resilient offline queue & HTTP dispatch
        default_db = os.path.join(BASE_DIR, "gateway-bridge", "offline_queue.db")
        self.bridge = GatewayBridge(
            port=self.port,
            baud=LORA_SETTINGS["UART_BAUD"],
            ingest_url=self.ingest_url,
            bff_url=self.bff_url,
            db_path=db_path or default_db,
        )
        self.bridge.start_worker()

        self._init_hardware()

    def _init_hardware(self):
        try:
            logger.info(f"Initializing LoRa SX126x Gateway on {self.port} @ {self.freq} MHz...")
            self.lora = sx126x(
                serial_num=self.port,
                freq=self.freq,
                addr=1,  # Master address 1
                power=LORA_SETTINGS["TX_POWER"],
                rssi=True,
                air_speed=LORA_SETTINGS["AIR_SPEED"],
            )
            logger.info("LoRa SX126x Gateway hardware initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not connect to LoRa module on {self.port}: {e}")
            logger.warning("Operating in listening mode (will retry on incoming data).")

    def handle_incoming_chunk(self, chunk: str, rssi: Optional[int]):
        """
        Reassemble streamed sub-packet chunks into complete, valid JSON packets.
        """
        now = time.time()
        # If buffer was idle for more than 4s, clear stale fragments
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
            # Scan backwards from the end for the closing '}' that forms a complete valid JSON object
            for pos in range(len(self.rx_buffer) - 1, 0, -1):
                if self.rx_buffer[pos] == "}":
                    candidate = self.rx_buffer[:pos + 1]
                    try:
                        data = json.loads(candidate)
                        self.process_incoming_packet(data, rssi)
                        self.rx_buffer = self.rx_buffer[pos + 1:]
                        found = True
                        break
                    except Exception:
                        continue
            if not found:
                if len(self.rx_buffer) > 1024:
                    self.rx_buffer = self.rx_buffer[-256:]
                break

    def process_incoming_packet(self, raw_input, rssi: Optional[int]) -> bool:
        self.total_received += 1

        if isinstance(raw_input, str):
            try:
                data = json.loads(raw_input)
            except Exception:
                logger.warning(f"Malformed packet received: {raw_input[:80]}")
                return False
        else:
            data = dict(raw_input)

        # Stamp authentic hardware RSSI if received
        if rssi is not None:
            data["rssi_dbm"] = rssi

        # Map to Canonical SubSense SensorReading contract
        canonical = to_canonical(data)

        node_id = canonical.get("node_id", "UNKNOWN")
        tilt = canonical["readings"].get("tilt_deg")
        vib = canonical["readings"].get("vibration_rms_mm_s")
        hop = canonical["node_health"].get("hop_count", 0)
        siren = canonical.get("siren_triggered", False)

        # Immediate real-time log
        logger.info(
            f"⚡ [RX PACKET #{self.total_received}] Node: {node_id} | "
            f"Tilt: {tilt if tilt is not None else 0.0:.3f}° | "
            f"Vib: {vib if vib is not None else 0.0:.3f} mm/s | "
            f"RSSI: {rssi if rssi is not None else 'N/A'} dBm | "
            f"Siren: {siren}"
        )

        # Dispatch to AI/ML & BFF
        ok = self.bridge.forward_reading(canonical)
        if ok:
            self.total_dispatched += 1

        # Visual Console Output
        status_color = Colors.RED if siren else Colors.GREEN
        icon = "🚨 CRITICAL HAZARD" if siren else "📡 TELEMETRY INGESTED"

        print(f"\n{status_color}{Colors.BOLD}")
        print("┌──────────────────────────────────────────────────────────┐")
        print(f"│  {icon:<54} │")
        print("├──────────────────────────────────────────────────────────┤")
        print(f"│  Node ID:     {node_id:<42} │")
        print(f"│  Pitch Tilt:  {f'{tilt:.3f} deg' if tilt is not None else 'null':<42} │")
        print(f"│  Vibration:   {f'{vib:.3f} mm/s' if vib is not None else 'null':<42} │")
        print(f"│  LoRa RSSI:   {f'{rssi} dBm' if rssi is not None else 'N/A':<42} │")
        print(f"│  Hops:        {hop:<42} │")
        print(f"│  Dispatched:  {'YES (AI/ML & BFF)' if ok else 'OFFLINE QUEUED':<42} │")
        print("└──────────────────────────────────────────────────────────┘")
        print(f"{Colors.RESET}")

        return ok

    def run(self):
        print(f"\n{Colors.CYAN}{Colors.BOLD}")
        print("╔══════════════════════════════════════════════════════════╗")
        print("║      🛰️   SUBSENSE LORA SURFACE GATEWAY ACTIVE           ║")
        print("║          Direct LoRa SX126x Surface Ingestion            ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print(f"{Colors.RESET}")
        print(f"Listening Port:  {Colors.GREEN}{self.port}{Colors.RESET}")
        print(f"Frequency:       {Colors.GREEN}{self.freq} MHz{Colors.RESET}")
        print(f"AI/ML Ingest:    {self.ingest_url}")
        print(f"BFF Broadcast:   {self.bff_url}\n")
        print(f"{Colors.DIM}Listening for incoming mine telemetry... Press Ctrl+C to stop{Colors.RESET}\n")

        try:
            while True:
                if self.lora:
                    msg, rssi = self.lora.receive()
                    if msg:
                        self.handle_incoming_chunk(msg, rssi)
                time.sleep(0.01)
        except KeyboardInterrupt:
            print(f"\n\n[GATEWAY] Shutting down. Total: {self.total_received}, Dispatched: {self.total_dispatched}")
        finally:
            self.bridge.stop()
            if self.lora:
                self.lora.close()


def run_gateway(port: Optional[str] = None):
    gw = LoRaGatewayNode(port=port or SERIAL_PORT)
    gw.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SubSense LoRa Gateway Node")
    parser.add_argument("--port", type=str, default=SERIAL_PORT, help="Serial port")
    parser.add_argument("--freq", type=int, default=LORA_SETTINGS["FREQUENCY"], help="Frequency in MHz")
    parser.add_argument("--ingest-url", type=str, default=AIML_INGEST_URL, help="AI/ML Ingestion endpoint")
    parser.add_argument("--bff-url", type=str, default=BFF_BROADCAST_URL, help="BFF Gateway endpoint")

    args = parser.parse_args()
    gw = LoRaGatewayNode(
        port=args.port,
        freq=args.freq,
        ingest_url=args.ingest_url,
        bff_url=args.bff_url,
    )
    gw.run()
