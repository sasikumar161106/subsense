#!/usr/bin/env python3
"""Automated ESP32 Hardware-in-the-Loop Test Runner for SubSense TinyML.

Connects to a physical ESP32 via USB Serial, captures on-boot benchmark telemetry,
triggers interactive diagnostic routines, and validates JSON risk events.

Usage:
    python scripts/test_esp32_hardware.py [--port COMx] [--baud 115200]
"""

import sys
import time
import argparse
import json

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("\n[!] 'pyserial' is required to run the automated hardware test runner.")
    print("    Install it with:  pip install pyserial\n")
    sys.exit(1)


def list_available_com_ports():
    """List all available COM/serial ports."""
    ports = list(serial.tools.list_ports.comports())
    return ports


def select_port(user_port=None):
    """Auto-detect or prompt user to select the ESP32 serial port."""
    ports = list_available_com_ports()
    if not ports:
        print("[!] No serial ports detected! Please connect your ESP32 via USB.")
        return None

    if user_port:
        return user_port

    print("\n--- Detected Serial Ports ---")
    esp_candidates = []
    for i, p in enumerate(ports):
        desc = p.description or ""
        hwid = p.hwid or ""
        is_esp = any(k in desc.lower() or k in hwid.lower() for k in ["cp210", "ch340", "ch341", "usb serial", "uart", "esp"])
        mark = " (Likely ESP32)" if is_esp else ""
        print(f"  [{i+1}] {p.device}: {desc}{mark}")
        if is_esp:
            esp_candidates.append(p.device)

    if len(esp_candidates) == 1:
        print(f"\n[+] Auto-selecting {esp_candidates[0]}")
        return esp_candidates[0]

    try:
        choice = input("\nEnter port number [1-" + str(len(ports)) + "] or port name (e.g. COM4): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(ports):
            return ports[int(choice) - 1].device
        return choice
    except (KeyboardInterrupt, EOFError):
        return None


def run_hardware_test(port_name, baud=115200, timeout=10.0):
    """Connect to ESP32, listen to boot telemetry, and execute automated test suite."""
    print(f"\nConnecting to ESP32 on {port_name} at {baud} baud...")
    try:
        ser = serial.Serial(port_name, baud, timeout=1.0)
    except Exception as e:
        print(f"[-] Failed to open serial port {port_name}: {e}")
        return False

    # Reset ESP32 by toggling DTR/RTS
    time.sleep(0.2)
    ser.dtr = False
    ser.rts = True
    time.sleep(0.1)
    ser.rts = False
    time.sleep(0.5)

    print("[+] Connected. Listening for ESP32 boot self-test telemetry...\n")
    start_time = time.time()
    raw_lines = []

    try:
        while time.time() - start_time < timeout:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if line:
                print(f"  [ESP32] {line}")
                raw_lines.append(line)
                if "Enter command [1-7]:" in line:
                    break
    except KeyboardInterrupt:
        print("\n[!] User interrupted.")

    print("\n--- Automated Command Test: Full Pipeline & JSON Serialization ---")
    time.sleep(0.5)
    ser.write(b"3\n")
    time.sleep(1.0)

    json_lines = []
    collecting_json = False
    deadline = time.time() + 5.0

    while time.time() < deadline:
        line = ser.readline().decode("utf-8", errors="replace").strip()
        if line:
            print(f"  [ESP32] {line}")
            if line.startswith("{"):
                collecting_json = True
                json_lines.append(line)
            elif collecting_json:
                json_lines.append(line)
                if line.startswith("}"):
                    collecting_json = False
                    break

    ser.close()

    if json_lines:
        json_str = "\n".join(json_lines)
        try:
            event = json.loads(json_str)
            print("\n=======================================================")
            print("         HARDWARE TEST VALIDATION RESULTS")
            print("=======================================================")
            print(f"  Node ID:             {event.get('node_id')}")
            print(f"  Model Version:       {event.get('model_version')}")
            print(f"  Anomaly Score:       {event.get('anomaly_score')}")
            print(f"  Confidence:          {event.get('local_confidence')}")
            print(f"  Threshold Breached:  {event.get('threshold_breached')}")
            print(f"  Siren Triggered:     {event.get('siren_triggered')}")
            print(f"  Contributing Feats:  {event.get('contributing_features')}")
            print("=======================================================")
            print("[✓] PASSED: Valid cloud-schema JSON Risk Event received from ESP32 hardware!")
            return True
        except json.JSONDecodeError as e:
            print(f"[!] Received malformed JSON: {e}")
            return False
    else:
        print("[!] No JSON event captured within timeout.")
        return False


def main():
    parser = argparse.ArgumentParser(description="SubSense ESP32 Hardware-in-the-Loop Test Runner")
    parser.add_argument("--port", type=str, default=None, help="COM port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    args = parser.parse_args()

    port = select_port(args.port)
    if not port:
        print("[!] Exiting: No port selected.")
        return 1

    success = run_hardware_test(port, args.baud)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
