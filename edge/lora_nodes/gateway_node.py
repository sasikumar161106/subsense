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
import queue
import sys
import threading
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

        # Asynchronous background dispatch queue to keep LoRa receiver 100% non-blocking (0ms latency)
        self.dispatch_queue: queue.Queue = queue.Queue(maxsize=500)
        self._dispatch_running = True
        self._dispatch_thread = threading.Thread(target=self._async_dispatch_worker, daemon=True, name="LoRaGatewayDispatcher")
        self._dispatch_thread.start()

        self._init_hardware()

    def _async_dispatch_worker(self):
        """Asynchronous HTTP dispatch worker so LoRa radio reception is never blocked."""
        while self._dispatch_running:
            try:
                canonical = self.dispatch_queue.get(timeout=1.0)
                if canonical is None:
                    break
                ok = self.bridge.forward_reading(canonical)
                if ok:
                    self.total_dispatched += 1
                self.dispatch_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.debug(f"Async dispatch error: {e}")

    def flush_dispatch(self, timeout: float = 2.0):
        """Block until all queued telemetry packets have been dispatched."""
        try:
            self.dispatch_queue.join()
        except Exception:
            pass

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
        if rssi is not None and -150 <= rssi <= -10:
            data["rssi_dbm"] = rssi

        # Map to Canonical SubSense SensorReading contract
        canonical = to_canonical(data)

        node_id = canonical.get("node_id", "UNKNOWN")
        tilt = canonical["readings"].get("tilt_deg")
        vib = canonical["readings"].get("vibration_rms_mm_s")
        hop = canonical["node_health"].get("hop_count", 0)
        siren = canonical.get("siren_triggered", False)

        # Immediate single-line UI output matching Sensor Node layout (instant 0ms response)
        status_color = Colors.RED if siren else Colors.GREEN
        alert_icon = "🚨 CRITICAL" if siren else "📡 NOMINAL"
        tilt_str = f"{tilt:.2f}" if tilt is not None else "0.00"
        vib_str = f"{vib:.2f}" if vib is not None else "0.00"
        rssi_str = f"{rssi} dBm" if (rssi is not None and -150 <= rssi <= -10) else "N/A"

        print(
            f"{status_color}{alert_icon} [Rx #{self.total_received}] "
            f"Node: {node_id} | "
            f"Tilt: {tilt_str}° | "
            f"Vib: {vib_str} mm/s | "
            f"RSSI: {rssi_str} | "
            f"Hops: {hop}{Colors.RESET}",
            flush=True,
        )

        # Enqueue for asynchronous background HTTP dispatch (zero blocking on LoRa reception)
        try:
            self.dispatch_queue.put_nowait(canonical)
        except queue.Full:
            pass

        return True

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
