#!/usr/bin/env python3
"""
SubSense LoRa Node Platform Launcher
====================================
Unified CLI for launching Sensor, Relay, or Gateway nodes on Raspberry Pi / PC
using direct LoRa SX126x hardware.

Adapted from loramain/lora-node/main.py.

Usage:
  python main.py --mode sensor   --id SS-PANEL7-N042 --port COM5
  python main.py --mode relay    --id RELAY-02       --port COM6
  python main.py --mode gateway                      --port COM7
"""

import argparse
import sys

from sensor_node import run_sensor
from relay_node import run_relay
from gateway_node import run_gateway
from config import SERIAL_PORT, DEFAULT_NODE_ID


def main():
    parser = argparse.ArgumentParser(
        description="SubSense LoRa SX126x Platform (Zero-ESP32 / Direct LoRa Mode)"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["sensor", "relay", "gateway"],
        help="Role of this device in the mine network: sensor, relay, or gateway",
    )
    parser.add_argument(
        "--id",
        default=DEFAULT_NODE_ID,
        help="Identifier for Sensor Node or Relay (e.g. SS-NODE-01 or RELAY-02)",
    )
    parser.add_argument(
        "--port",
        default=SERIAL_PORT,
        help="Serial port for SX126x module (e.g. COM5 or /dev/ttyUSB0)",
    )
    parser.add_argument(
        "--anomaly",
        action="store_true",
        help="(Sensor mode only) Simulate strata tilt breach (>4.0 deg)",
    )
    parser.add_argument(
        "--esp32-port",
        default=None,
        help="(Sensor mode only) Serial port of attached ESP32 (e.g. /dev/ttyUSB0 or COM3)",
    )

    args = parser.parse_args()

    import logging
    log_tag = f"[{args.mode.upper()}-NODE]"
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [%(levelname)s] {log_tag} %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )

    try:
        if args.mode == "sensor":
            run_sensor(
                node_id=args.id,
                port=args.port,
                anomaly=args.anomaly,
                esp32_port=args.esp32_port,
            )
        elif args.mode == "relay":
            run_relay(relay_id=args.id, port=args.port)
        elif args.mode == "gateway":
            run_gateway(port=args.port)
    except KeyboardInterrupt:
        print("\n[System] Shutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()
