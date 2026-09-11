#!/usr/bin/env python3
"""
SubSense LoRa SX126x Diagnostic & Test Tool
===========================================
Adapted from the loramain project.
Tests serial port accessibility, SX126x module configuration, and verifies
LoRa transmission & reception with live RSSI measurement.

Usage:
  python diagnose_lora.py                   # Run automated self-test
  python diagnose_lora.py --listen          # Enter continuous LoRa packet listener
  python diagnose_lora.py --send "PING"     # Send test packet
  python diagnose_lora.py --port COM5       # Specify serial port (or /dev/ttyUSB0)
"""

import argparse
import os
import sys
import time

# Ensure gateway-bridge is in sys.path for the sx126x driver
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, "gateway-bridge"))

try:
    from drivers.sx126x import sx126x
except ImportError:
    import importlib
    sys.path.insert(0, os.path.join(BASE_DIR, "gateway-bridge", "drivers"))
    sx126x = importlib.import_module("sx126x").sx126x


def detect_serial_ports():
    """Detect available serial COM ports or /dev/tty* devices."""
    ports = []
    try:
        import serial.tools.list_ports
        for p in serial.tools.list_ports.comports():
            ports.append(p.device)
    except Exception:
        pass

    # Common Unix fallbacks
    for dev in ['/dev/ttyS0', '/dev/ttyAMA0', '/dev/serial0', '/dev/ttyUSB0', '/dev/ttyACM0']:
        if os.path.exists(dev) and dev not in ports:
            ports.append(dev)

    return ports


def test_lora_send(port: str, freq: int = 865):
    """Test sending a diagnostic LoRa packet."""
    print(f"[TEST] Initializing LoRa on {port}, freq={freq} MHz...")
    try:
        node = sx126x(serial_num=port, freq=freq, addr=99, power=22, rssi=True)
        print("[TEST] Sending diagnostic packet...")
        test_payload = '{"test": "SUBSENSE_LORA_DIAGNOSTIC", "ts": ' + str(int(time.time())) + '}'
        node.send(test_payload)
        node.close()
        print(f"[TEST] Sent: {test_payload}")
        return True, "LoRa send test passed"
    except Exception as e:
        return False, str(e)


def run_listener(port: str, freq: int = 865, duration: int = 300):
    """Listen for incoming LoRa packets and print payloads with RSSI values."""
    print("=" * 65)
    print(f"  SubSense LoRa SX126x Packet Listener ({port} @ {freq} MHz)")
    print("  Press Ctrl+C to stop")
    print("=" * 65)

    try:
        node = sx126x(serial_num=port, freq=freq, addr=0, power=22, rssi=True)
        packets_count = 0
        start_time = time.time()

        while time.time() - start_time < duration:
            msg, rssi = node.receive()
            if msg:
                packets_count += 1
                print(f"[{time.strftime('%H:%M:%S')}] [RX #{packets_count}] RSSI: {rssi} dBm | Payload: {msg}")
            time.sleep(0.05)

        node.close()
        print(f"\n[LISTENER] Finished: Received {packets_count} packets in {duration}s.")
    except KeyboardInterrupt:
        print(f"\n[LISTENER] Stopped by user.")
    except Exception as e:
        print(f"\n[LISTENER] Error: {e}")


def run_diagnostics(port: str, freq: int = 865):
    print("=" * 65)
    print("  SubSense LoRa SX126x Hardware Diagnostic Suite")
    print(f"  Target Frequency: {freq} MHz (India ISM Band 865-867 MHz)")
    print("=" * 65)

    # 1. Check Serial Ports
    print("\n[1/3] Scanning Available Serial Ports...")
    available_ports = detect_serial_ports()
    if available_ports:
        print(f"    Available: {', '.join(available_ports)}")
    else:
        print("    WARNING: No serial ports detected! Connect USB-UART dongle or ESP32.")

    # 2. Test Port Connection
    target_port = port or (available_ports[0] if available_ports else "COM5")
    print(f"\n[2/3] Testing Serial Port Connection on '{target_port}'...")
    try:
        import serial
        s = serial.Serial(target_port, 9600, timeout=0.5)
        s.close()
        print(f"    Serial Port '{target_port}' opened successfully at 9600 baud.")
    except Exception as e:
        print(f"    Port Error: {e}")

    # 3. Test LoRa Transmission
    print(f"\n[3/3] Testing LoRa SX126x Transmission...")
    ok, msg = test_lora_send(target_port, freq)
    if ok:
        print(f"    LoRa Module Transmission: OK ({msg})")
    else:
        print(f"    LoRa Module Transmission Failed: {msg}")

    print("\n" + "=" * 65)
    print("  DIAGNOSTICS COMPLETE")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SubSense LoRa SX126x Diagnostics")
    parser.add_argument("--port", type=str, default=None, help="Serial port (e.g. COM5 or /dev/ttyUSB0)")
    parser.add_argument("--freq", type=int, default=865, help="LoRa frequency in MHz (default: 865)")
    parser.add_argument("--listen", action="store_true", help="Start packet listener")
    parser.add_argument("--duration", type=int, default=300, help="Listen duration in seconds (default: 300)")
    parser.add_argument("--send", type=str, default=None, help="Send a custom packet string")

    args = parser.parse_args()

    port = args.port
    if not port:
        detected = detect_serial_ports()
        port = detected[0] if detected else ("COM5" if os.name == 'nt' else "/dev/ttyUSB0")

    if args.listen:
        run_listener(port, args.freq, args.duration)
    elif args.send:
        node = sx126x(serial_num=port, freq=args.freq, addr=99, power=22, rssi=True)
        node.send(args.send)
        node.close()
        print(f"Sent: {args.send}")
    else:
        run_diagnostics(port, args.freq)
