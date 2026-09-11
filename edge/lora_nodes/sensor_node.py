"""
SubSense LoRa Sensor Node (Board 1 / Wearable / Field Unit)
===========================================================
Runs on Raspberry Pi, Linux, or PC with SX126x module attached.
Samples geotechnical strata tilt & vibration, evaluates on-device safety thresholds,
and broadcasts canonical telemetry packets over LoRa at 865 MHz.

Adapted from loramain/src/nodes/tourist.py.
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from typing import Optional

# Include driver and config paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, "gateway-bridge"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from drivers.sx126x import sx126x
from config import (
    SERIAL_PORT,
    LORA_SETTINGS,
    DEFAULT_NODE_ID,
    DEFAULT_SITE_ID,
    DEFAULT_TENANT_ID,
    DEFAULT_ZONE_ID,
    PHYSICAL_TILT_CRITICAL_DEG,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SENSOR-NODE] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sensor-node")


class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


class LoRaSensorNode:
    def __init__(
        self,
        node_id: str = DEFAULT_NODE_ID,
        port: str = SERIAL_PORT,
        freq: int = LORA_SETTINGS["FREQUENCY"],
        interval: float = 2.0,
        simulate_anomaly: bool = False,
        esp32_port: Optional[str] = None,
    ):
        self.node_id = node_id
        self.port = port
        self.freq = freq
        self.interval = interval
        self.simulate_anomaly = simulate_anomaly
        self.esp32_port = esp32_port
        self.esp32_ser = None

        self.packet_count = 0
        self.battery_percent = 98
        self.lora: Optional[sx126x] = None

        self._init_hardware()
        if self.esp32_port:
            self._init_esp32_serial()

    def _init_esp32_serial(self):
        try:
            import serial
            logger.info(f"Connecting to ESP32 Sensor Node on {self.esp32_port} @ 115200 baud...")
            self.esp32_ser = serial.Serial(
                self.esp32_port,
                115200,
                timeout=1.0,
                rtscts=False,
                dsrdtr=False,
            )
            try:
                self.esp32_ser.dtr = False
                self.esp32_ser.rts = False
            except Exception:
                pass
            logger.info(f"Connected to ESP32 on {self.esp32_port}")
        except Exception as e:
            logger.error(f"Failed to connect to ESP32 on {self.esp32_port}: {e}")
            self.esp32_ser = None

    def _init_hardware(self):
        try:
            logger.info(f"Initializing LoRa SX126x on {self.port} @ {self.freq} MHz...")
            self.lora = sx126x(
                serial_num=self.port,
                freq=self.freq,
                addr=10,
                power=LORA_SETTINGS["TX_POWER"],
                rssi=False,
                air_speed=LORA_SETTINGS["AIR_SPEED"],
            )
            logger.info(f"LoRa SX126x initialized successfully on {self.port}")
        except Exception as e:
            logger.warning(f"Could not connect to LoRa module on {self.port}: {e}")
            logger.warning("Operating in test/emulation mode (packets logged to console).")

    def read_sensors(self) -> tuple[float, float, bool]:
        """
        Read tilt and vibration from physical sensor or calibrated simulation.
        Returns: (tilt_deg, vibration_rms_mm_s, is_critical)
        """
        if self.simulate_anomaly:
            # Simulate roof shear / pillar burst precursor
            tilt = round(4.25 + random.uniform(-0.2, 0.6), 3)
            vib = round(1.15 + random.uniform(-0.1, 0.4), 3)
        else:
            # Normal baseline mining strata
            tilt = round(0.45 + random.uniform(-0.05, 0.05), 3)
            vib = round(0.12 + random.uniform(-0.02, 0.03), 3)

        is_critical = tilt >= PHYSICAL_TILT_CRITICAL_DEG
        return tilt, vib, is_critical

    def build_telemetry_packet(self, tilt: float, vib: float, is_critical: bool) -> str:
        """
        Build SubSense canonical JSON telemetry payload matching edge firmware contract.
        """
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.battery_percent = max(15, self.battery_percent - (1 if self.packet_count % 100 == 0 else 0))

        payload = {
            "node_id": self.node_id,
            "site_id": DEFAULT_SITE_ID,
            "tenant_id": DEFAULT_TENANT_ID,
            "zone_id": DEFAULT_ZONE_ID,
            "tilt_current": tilt,
            "vibration_rms": vib,
            "battery_percent": self.battery_percent,
            "rssi_dbm": -55,
            "hop_count": 0,
            "siren_triggered": is_critical,
            "anomaly_score": round(0.95 if is_critical else 0.08, 3),
            "seq": self.packet_count,
            "timestamp": now_iso,
        }
        return json.dumps(payload, separators=(',', ':'))

    def send_packet(self, payload_str: str, is_critical: bool) -> bool:
        self.packet_count += 1

        if self.lora:
            try:
                self.lora.send(payload_str, target_addr=0xFFFF, channel=15)
                sent = True
            except Exception as e:
                logger.error(f"LoRa transmission failed: {e}")
                sent = False
        else:
            sent = False

        status_color = Colors.RED if is_critical else Colors.GREEN
        alert_icon = "🚨 CRITICAL" if is_critical else "📡 NOMINAL"
        try:
            tilt_val = payload_str.split('\"tilt_current\":')[1].split(',')[0]
        except Exception:
            tilt_val = "0.0"
        try:
            vib_val = payload_str.split('\"vibration_rms\":')[1].split(',')[0]
        except Exception:
            vib_val = "0.0"

        print(
            f"\r{status_color}{alert_icon} [Seq #{self.packet_count}] "
            f"Tilt: {tilt_val}° | "
            f"Vib: {vib_val} mm/s | "
            f"LoRa Tx: {'OK' if sent or not self.lora else 'FAIL'}{Colors.RESET}  ",
            flush=True,
        )
        return sent

    def run(self):
        import re
        print(f"\n{Colors.CYAN}{Colors.BOLD}")
        print("╔══════════════════════════════════════════════════════════╗")
        print("║      ⛏️   SUBSENSE LORA STRATA SENSOR NODE ACTIVE        ║")
        print("║           Running Direct LoRa SX126x @ 865 MHz           ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print(f"{Colors.RESET}")
        print(f"Node ID:       {Colors.GREEN}{self.node_id}{Colors.RESET}")
        print(f"Frequency:     {Colors.GREEN}{self.freq} MHz{Colors.RESET}")
        print(f"Serial Port:   {Colors.GREEN}{self.port}{Colors.RESET}")
        print(f"Interval:      {self.interval}s")
        print(f"Sim Anomaly:   {self.simulate_anomaly}")
        if self.esp32_port:
            print(f"ESP32 Source:  {Colors.GREEN}{self.esp32_port} @ 115200 baud{Colors.RESET}\n")
        else:
            print()

        try:
            if self.esp32_ser:
                print(f"{Colors.GREEN}Listening for real-time telemetry from ESP32 on {self.esp32_port}...{Colors.RESET}\n")
                while True:
                    line = self.esp32_ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue

                    # 1. Look for embedded JSON object in line
                    s_idx = line.find("{")
                    e_idx = line.rfind("}")
                    if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
                        json_str = line[s_idx:e_idx+1]
                        try:
                            data = json.loads(json_str)
                            tilt = float(data.get("tilt_current", data.get("tilt", 0.0)))
                            is_critical = bool(data.get("siren_triggered", False)) or (tilt >= PHYSICAL_TILT_CRITICAL_DEG)
                            self.send_packet(json_str, is_critical)
                            continue
                        except Exception:
                            pass

                    # 2. Look for human-readable "[SENSOR NODE] Tilt: ... deg | Vib: ... mm/s"
                    m = re.search(r"Tilt:\s*([0-9.-]+)\s*deg.*?Vib:\s*([0-9.-]+)", line, re.IGNORECASE)
                    if m:
                        try:
                            tilt = float(m.group(1))
                            vib = float(m.group(2))
                            is_critical = tilt >= PHYSICAL_TILT_CRITICAL_DEG
                            packet = self.build_telemetry_packet(tilt, vib, is_critical)
                            self.send_packet(packet, is_critical)
                            continue
                        except Exception:
                            pass

                    # 3. Print boot/tare logs from ESP32
                    print(f"{Colors.DIM}[ESP32 Serial] {line}{Colors.RESET}")
            else:
                while True:
                    tilt, vib, is_critical = self.read_sensors()
                    packet = self.build_telemetry_packet(tilt, vib, is_critical)
                    self.send_packet(packet, is_critical)
                    time.sleep(self.interval)
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Stopped after {self.packet_count} packets.{Colors.RESET}")
        finally:
            if self.esp32_ser:
                try:
                    self.esp32_ser.close()
                except Exception:
                    pass
            if self.lora:
                self.lora.close()


def run_sensor(
    node_id: Optional[str] = None,
    port: Optional[str] = None,
    anomaly: bool = False,
    esp32_port: Optional[str] = None,
):
    node = LoRaSensorNode(
        node_id=node_id or DEFAULT_NODE_ID,
        port=port or SERIAL_PORT,
        simulate_anomaly=anomaly,
        esp32_port=esp32_port,
    )
    node.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SubSense LoRa Sensor Node")
    parser.add_argument("--id", type=str, default=DEFAULT_NODE_ID, help="Node ID")
    parser.add_argument("--port", type=str, default=SERIAL_PORT, help="Serial port for LoRa SX126x module")
    parser.add_argument("--freq", type=int, default=LORA_SETTINGS["FREQUENCY"], help="Frequency in MHz")
    parser.add_argument("--interval", type=float, default=2.0, help="Transmission interval in seconds")
    parser.add_argument("--anomaly", action="store_true", help="Simulate physical tilt hazard (>4.0 deg)")
    parser.add_argument("--esp32-port", type=str, default=None, help="Serial port of attached ESP32 (e.g. /dev/ttyUSB0 or COM3)")

    args = parser.parse_args()
    node = LoRaSensorNode(
        node_id=args.id,
        port=args.port,
        freq=args.freq,
        interval=args.interval,
        simulate_anomaly=args.anomaly,
        esp32_port=args.esp32_port,
    )
    node.run()
