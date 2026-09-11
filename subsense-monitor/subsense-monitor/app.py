#!/usr/bin/env python3
"""
SubSense Standalone Sensor Monitoring Server (Ultra-Lightweight)
================================================================
A 100% pure Python HTTP and WebSocket server.
Zero heavy frameworks: No FastAPI, No Pydantic, No Uvicorn.
Requires ONLY 'pyserial' (installs in 1-2 seconds, zero compilation).
"""

import base64
import hashlib
import http.server
import json
import logging
import mimetypes
import os
import re
import socket
import socketserver
import struct
import subprocess
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SUBSENSE-MONITOR] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("subsense-monitor")

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Locate frontend dist directory
CANDIDATE_DIRS = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "dist")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend", "dist")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dist")),
]
DIST_DIR = next((d for d in CANDIDATE_DIRS if os.path.exists(d) and os.path.isfile(os.path.join(d, "index.html"))), None)
if DIST_DIR:
    logger.info(f"Mounted frontend dashboard from {DIST_DIR}")
else:
    logger.warning("Frontend dist/index.html not found! Ensure dist/ is present.")

# ------------------------------------------------------------------------------
# 1. State Store
# ------------------------------------------------------------------------------
class MonitorState:
    def __init__(self):
        self.port: str = "AUTO"
        self.baud: int = 115200
        self.is_connected: bool = False
        self.packets_count: int = 0
        self.last_seen_ts: float = 0
        
        # Real sensor readings
        self.tilt_deg: float = 0.0
        self.vib_rms: float = 0.0
        self.ml_score: float = 0.05
        self.health_status: str = "NOMINAL"
        self.siren_active: bool = False
        
        # Calibration
        self.tilt_tare: float = 0.0
        self.last_critical_sms_ts: float = 0
        
        # Contacts & SMS
        self.contacts: List[Dict[str, Any]] = [
            {"id": "c1", "name": "Mine Safety Officer (Primary)", "phone": "+917358160485", "role": "Shift Lead", "active": True},
            {"id": "c2", "name": "Emergency Rescue Station", "phone": "+917010336893", "role": "Rescue Squad", "active": True},
        ]
        self.sms_logs: List[Dict[str, Any]] = []

state = MonitorState()

def get_current_packet(event: str = "telemetry") -> Dict[str, Any]:
    return {
        "event": event,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "node_id": "SS-SENSOR-01",
        "port": state.port,
        "tilt": round(state.tilt_deg - state.tilt_tare, 2),
        "vib": round(state.vib_rms, 2),
        "ml_score": round(state.ml_score, 2),
        "health": state.health_status,
        "packets_count": state.packets_count,
        "siren_active": state.siren_active,
        "is_connected": state.is_connected,
        "mesh": {
            "hop_count": 0,
            "tx_status": "OK" if state.is_connected else "RECONNECTING",
            "rssi_dbm": -68 if state.is_connected else 0,
            "battery": 94,
            "relay_id": "SS-RELAY-01",
            "gateway_id": "SS-GATEWAY-01"
        }
    }

# ------------------------------------------------------------------------------
# 2. Port Auto-Detection
# ------------------------------------------------------------------------------
def detect_esp32_port() -> Optional[str]:
    # Check Linux physical nodes first
    linux_priority_devices = [
        "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2",
        "/dev/ttyACM0", "/dev/ttyACM1",
        "/dev/serial0", "/dev/ttyAMA0"
    ]
    for dev_path in linux_priority_devices:
        if os.path.exists(dev_path):
            return dev_path

    if not SERIAL_AVAILABLE:
        return None

    try:
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            desc = (p.description or "").lower()
            hwid = (p.hwid or "").lower()
            dev = (p.device or "").lower()
            if any(k in desc or k in hwid or k in dev for k in ["1a86:7523", "ch340", "ch341", "cp210", "ftdi", "esp32", "usb-serial", "ttyusb", "ttyacm"]):
                return p.device

        for p in ports:
            if "com" in p.device.lower():
                return p.device
    except Exception:
        pass

    return None

# ------------------------------------------------------------------------------
# 3. SMS Dispatch Engine (Auto USB Device Detection)
# ------------------------------------------------------------------------------
def ensure_adb_usb_forward() -> bool:
    """Auto-detects any USB-connected Android phone and sets up ADB port forwarding."""
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=3)
        if "device" in res.stdout:
            lines = [l for l in res.stdout.strip().splitlines() if "\tdevice" in l]
            if lines:
                subprocess.run(["adb", "forward", "tcp:8022", "tcp:8022"], capture_output=True, timeout=2)
                return True
    except Exception:
        pass
    return False

def try_send_usb_at_sms(phone: str, message: str) -> Optional[str]:
    """Scans for any connected USB GSM/LTE modem (excluding the ESP32 port) and sends SMS via AT commands."""
    if not SERIAL_AVAILABLE:
        return None
    try:
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            # Skip the port currently connected to the ESP32
            if p.device == state.port:
                continue
            desc = (p.description or "").lower()
            dev = (p.device or "").lower()
            if any(k in desc or k in dev for k in ["modem", "gsm", "sim", "lte", "ttyusb", "ttyacm"]):
                try:
                    ser = serial.Serial(p.device, 9600, timeout=3)
                    ser.write(b"AT\r\n")
                    time.sleep(0.3)
                    resp = ser.read(ser.in_waiting or 100).decode(errors="ignore")
                    if "OK" in resp:
                        # AT modem verified! Send SMS
                        ser.write(b"AT+CMGF=1\r\n")
                        time.sleep(0.3)
                        ser.write(f'AT+CMGS="{phone}"\r\n'.encode())
                        time.sleep(0.5)
                        ser.write(message.encode() + b"\x1a")
                        time.sleep(2.0)
                        final_resp = ser.read(ser.in_waiting or 100).decode(errors="ignore")
                        ser.close()
                        if "OK" in final_resp or "+CMGS:" in final_resp:
                            return f"Sent via USB AT Modem on {p.device}"
                    ser.close()
                except Exception:
                    pass
    except Exception:
        pass
    return None

def dispatch_termux_sms(phone: str, message: str) -> Dict[str, Any]:
    sanitized_phone = re.sub(r"[^\d+]", "", phone)
    escaped_msg = message.replace("'", "'\\''")
    start_t = time.time()

    # 1. First, check if a USB GSM/LTE modem is plugged into any USB port
    usb_modem_result = try_send_usb_at_sms(sanitized_phone, message)
    if usb_modem_result:
        duration = round(time.time() - start_t, 2)
        log_entry = {
            "id": f"sms-{int(time.time()*1000)}",
            "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
            "phone": sanitized_phone,
            "message": message,
            "success": True,
            "duration": f"{duration}s",
            "output": usb_modem_result
        }
        state.sms_logs.insert(0, log_entry)
        logger.info(f"[SMS] {usb_modem_result} to {sanitized_phone}")
        return log_entry

    # 2. Auto-forward whichever Android phone is plugged into USB via ADB
    ensure_adb_usb_forward()

    # 3. Determine Termux candidate hosts (env var -> Wi-Fi IP 192.168.219.12 -> USB 127.0.0.1)
    env_host = os.getenv("TERMUX_HOST")
    termux_user = os.getenv("TERMUX_USER", "u0_a382")
    termux_port = os.getenv("TERMUX_PORT", "8022")

    candidate_hosts = [h for h in [env_host, "192.168.219.12", "127.0.0.1"] if h]
    success = False
    output = ""

    for thost in candidate_hosts:
        target_dest = f"{termux_user}@{thost}" if thost != "127.0.0.1" else thost
        cmd = f'ssh -p {termux_port} -o StrictHostKeyChecking=no -o ConnectTimeout=4 {target_dest} "termux-sms-send -n {sanitized_phone} \'{escaped_msg}\'"'
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=8)
            if res.returncode == 0:
                success = True
                output = f"Dispatched via Termux SSH ({thost})"
                break
            else:
                output = res.stderr.strip() or res.stdout.strip()
        except Exception as e:
            output = str(e)

    # Fallback: If SSH failed, attempt direct ADB broadcast if a USB phone is plugged in
    if not success:
        try:
            adb_cmd = f"adb shell am broadcast -a com.termux.api.action.SEND_SMS --es recipient '{sanitized_phone}' --es text-message '{escaped_msg}'"
            adb_res = subprocess.run(adb_cmd, shell=True, capture_output=True, text=True, timeout=5)
            if adb_res.returncode == 0 and "result=-1" in (adb_res.stdout or ""):
                success = True
                output = "Dispatched via direct USB ADB Termux broadcast"
        except Exception:
            pass

    duration = round(time.time() - start_t, 2)
    log_entry = {
        "id": f"sms-{int(time.time()*1000)}",
        "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
        "phone": sanitized_phone,
        "message": message,
        "success": success,
        "duration": f"{duration}s",
        "output": output or ("SMS sent to Android modem" if success else "Error: phone unreachable on Wi-Fi/USB")
    }
    state.sms_logs.insert(0, log_entry)
    logger.info(f"[SMS] Dispatched to {sanitized_phone}: success={log_entry['success']}")
    return log_entry

def broadcast_critical_sms(tilt: float, vib: float):
    now = time.time()
    if now - state.last_critical_sms_ts < 60.0:
        return
    state.last_critical_sms_ts = now
    msg = f"CRITICAL SUBSIDENCE ALERT! Panel 7 Pitch: {tilt:.2f} deg, Vib: {vib:.2f} mm/s. Evacuate immediately!"
    for c in state.contacts:
        if c.get("active", True):
            threading.Thread(target=dispatch_termux_sms, args=(c["phone"], msg), daemon=True).start()

# ------------------------------------------------------------------------------
# 4. WebSocket Client Manager
# ------------------------------------------------------------------------------
class WSClient:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.lock = threading.Lock()
        
    def send_text(self, text: str) -> bool:
        payload = text.encode("utf-8")
        l = len(payload)
        if l <= 125:
            header = struct.pack("!BB", 0x81, l)
        elif l <= 65535:
            header = struct.pack("!BBH", 0x81, 126, l)
        else:
            header = struct.pack("!BBQ", 0x81, 127, l)
        with self.lock:
            try:
                self.sock.sendall(header + payload)
                return True
            except Exception:
                return False

ws_clients: List[WSClient] = []
ws_lock = threading.Lock()

def broadcast_ws(packet: Dict[str, Any]):
    msg = json.dumps(packet)
    with ws_lock:
        dead = []
        for client in ws_clients:
            if not client.send_text(msg):
                dead.append(client)
        for d in dead:
            if d in ws_clients:
                ws_clients.remove(d)

# ------------------------------------------------------------------------------
# 5. Background Serial Reader
# ------------------------------------------------------------------------------
SENSOR_REGEX = re.compile(
    r"\[SENSOR NODE\]\s*Tilt:\s*([+-]?\d+(?:\.\d+)?)\s*deg\s*\|\s*Vib:\s*([+-]?\d+(?:\.\d+)?)\s*mm/s\s*\|\s*ML Score:\s*([+-]?\d+(?:\.\d+)?)\s*\|\s*Health:\s*(\w+)",
    re.IGNORECASE
)

def serial_worker():
    if not SERIAL_AVAILABLE:
        logger.warning("pyserial is not installed. Serial reading disabled. Run: pip install pyserial")
        return

    logger.info("Starting background serial reader thread...")
    while True:
        target_port = detect_esp32_port()
        if not target_port:
            state.port = "SCANNING..."
            state.is_connected = False
            broadcast_ws(get_current_packet("heartbeat"))
            time.sleep(2.0)
            continue

        state.port = target_port
        try:
            ser = serial.Serial()
            ser.port = target_port
            ser.baudrate = state.baud
            ser.timeout = 1.0
            ser.dtr = False
            ser.rts = False
            ser.open()
            ser.dtr = False
            ser.rts = False
            time.sleep(0.1)
            ser.reset_input_buffer()

            state.is_connected = True
            logger.info(f"Connected to ESP32 on {target_port} at {state.baud} baud.")
            broadcast_ws(get_current_packet("connected"))

            while True:
                try:
                    raw = ser.readline()
                except Exception:
                    break
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                m = SENSOR_REGEX.search(line)
                if m:
                    state.packets_count += 1
                    state.last_seen_ts = time.time()
                    state.tilt_deg = float(m.group(1))
                    state.vib_rms = float(m.group(2))
                    state.ml_score = float(m.group(3))
                    state.health_status = m.group(4).upper()

                    effective_tilt = state.tilt_deg - state.tilt_tare
                    is_critical = (state.health_status == "CRITICAL" or abs(effective_tilt) >= 4.0 or state.ml_score >= 0.75)
                    state.siren_active = is_critical

                    if is_critical:
                        broadcast_critical_sms(effective_tilt, state.vib_rms)

                    broadcast_ws(get_current_packet("telemetry"))

            ser.close()
        except Exception as e:
            state.is_connected = False
            logger.warning(f"Serial disconnected on {target_port}: {e}")
            time.sleep(2.0)

threading.Thread(target=serial_worker, daemon=True, name="SerialWorker").start()

# Periodic heartbeat broadcast (keeps UI alive if serial is waiting)
def heartbeat_worker():
    while True:
        time.sleep(2.0)
        broadcast_ws(get_current_packet("heartbeat"))

threading.Thread(target=heartbeat_worker, daemon=True, name="HeartbeatWorker").start()

# ------------------------------------------------------------------------------
# 6. HTTP & WebSocket Server Handler
# ------------------------------------------------------------------------------
class SubSenseHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress standard logging for static asset requests to keep console clean
        if "/assets/" not in (args[0] if args else ""):
            logger.debug("%s - %s", self.address_string(), format % args)

    def set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(200)
        self.set_cors_headers()
        self.end_headers()

    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, filepath: str):
        if not os.path.isfile(filepath):
            self.send_error(404, "File Not Found")
            return
        ctype, _ = mimetypes.guess_type(filepath)
        if filepath.endswith(".js"):
            ctype = "application/javascript"
        elif filepath.endswith(".css"):
            ctype = "text/css"
        elif not ctype:
            ctype = "application/octet-stream"

        with open(filepath, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.set_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}
        return {}

    def do_GET(self):
        # 1. WebSocket Upgrade
        if self.headers.get("Upgrade", "").lower() == "websocket":
            self.handle_websocket()
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 2. REST Endpoints
        if path == "/api/sensor":
            self.send_json(get_current_packet("telemetry"))
            return
        elif path == "/api/status":
            self.send_json({
                "port": state.port,
                "is_connected": state.is_connected,
                "packets_count": state.packets_count,
                "tilt": round(state.tilt_deg - state.tilt_tare, 2),
                "vib": round(state.vib_rms, 2),
                "ml_score": round(state.ml_score, 2),
                "health": state.health_status,
                "siren_active": state.siren_active,
            })
            return
        elif path == "/api/mesh":
            self.send_json({
                "nodes": [
                    {
                        "id": "SS-SENSOR-01",
                        "label": "Sensor Node 1 (Physical)",
                        "role": "Sensing & TinyML",
                        "hardware": "ESP32 + MPU6050",
                        "port": state.port,
                        "mac": "24:6F:28:1A:BC:01",
                        "hops": 0,
                        "battery": 94,
                        "rssi": -68,
                        "status": state.health_status,
                        "tilt": round(state.tilt_deg - state.tilt_tare, 2),
                        "vib": round(state.vib_rms, 2),
                        "active": state.is_connected
                    },
                    {
                        "id": "SS-RELAY-01",
                        "label": "Relay Node (Mid-Panel)",
                        "role": "ESP-NOW Forwarder",
                        "hardware": "ESP32 Mesh Node",
                        "port": "Wireless Mesh",
                        "mac": "30:AE:A4:07:0D:20",
                        "hops": 1,
                        "battery": 88,
                        "rssi": -72,
                        "status": "NOMINAL",
                        "active": True
                    },
                    {
                        "id": "SS-GATEWAY-01",
                        "label": "Gateway Root (Pit Head)",
                        "role": "Mesh Sink / Cloud Uplink",
                        "hardware": "ESP32 WiFi Gateway",
                        "port": "Ethernet / LTE",
                        "mac": "24:0A:C4:18:BE:42",
                        "hops": 2,
                        "battery": 100,
                        "rssi": -62,
                        "status": "ONLINE",
                        "active": True
                    }
                ],
                "links": [
                    {"source": "SS-SENSOR-01", "target": "SS-RELAY-01", "protocol": "ESP-NOW", "rssi": -68, "quality": 92},
                    {"source": "SS-RELAY-01", "target": "SS-GATEWAY-01", "protocol": "ESP-NOW", "rssi": -72, "quality": 88},
                ],
                "stats": {
                    "total_packets": state.packets_count,
                    "packet_loss_pct": 0.2,
                    "avg_latency_ms": 14.5
                }
            })
            return
        elif path == "/api/contacts":
            self.send_json(state.contacts)
            return
        elif path == "/api/sms/logs":
            self.send_json(state.sms_logs)
            return

        # 3. Static Files & SPA Routing
        if not DIST_DIR:
            self.send_error(404, "Dashboard UI not found.")
            return

        clean = path.lstrip("/")
        if not clean:
            clean = "index.html"

        candidate = os.path.join(DIST_DIR, clean)
        if os.path.isfile(candidate):
            self.send_file(candidate)
        else:
            # Fallback for client-side routing
            index_path = os.path.join(DIST_DIR, "index.html")
            if os.path.isfile(index_path):
                self.send_file(index_path)
            else:
                self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_json_body()

        if path == "/api/sensor/tare":
            state.tilt_tare = state.tilt_deg
            broadcast_ws(get_current_packet("telemetry"))
            self.send_json({"status": "TARED", "tare_offset": state.tilt_tare})
            return
        elif path == "/api/sensor/simulate-critical":
            state.tilt_deg = 5.25
            state.vib_rms = 1.45
            state.ml_score = 0.92
            state.health_status = "CRITICAL"
            state.siren_active = True
            broadcast_critical_sms(state.tilt_deg, state.vib_rms)
            broadcast_ws(get_current_packet("telemetry"))
            self.send_json({"status": "CRITICAL_SIMULATED", "tilt": state.tilt_deg, "siren": True})
            return
        elif path == "/api/sensor/reset-nominal":
            state.tilt_deg = 0.0
            state.tilt_tare = 0.0
            state.vib_rms = 0.02
            state.ml_score = 0.05
            state.health_status = "NOMINAL"
            state.siren_active = False
            broadcast_ws(get_current_packet("telemetry"))
            self.send_json({"status": "RESET_NOMINAL"})
            return
        elif path == "/api/contacts":
            cid = f"c{len(state.contacts)+1}"
            c = {
                "id": cid,
                "name": body.get("name", "Emergency Responder"),
                "phone": body.get("phone", ""),
                "role": body.get("role", "Emergency Responder"),
                "active": True
            }
            state.contacts.append(c)
            self.send_json(state.contacts)
            return
        elif path == "/api/sms/test":
            target_phone = body.get("phone") or (state.contacts[0]["phone"] if state.contacts else "+917358160485")
            msg = body.get("message") or f"SubSense Test Alert: Physical ESP32 on {state.port} nominal. Time: {datetime.now().strftime('%H:%M:%S')}"
            res = dispatch_termux_sms(target_phone, msg)
            self.send_json(res)
            return
        elif path == "/api/drill/simulate":
            state.siren_active = True
            msg = "EMERGENCY DRILL TRIGGERED: Catastrophic strata failure simulation on Panel 7! Evacuate immediately."
            for c in state.contacts:
                threading.Thread(target=dispatch_termux_sms, args=(c["phone"], msg), daemon=True).start()
            broadcast_ws({"event": "drill_triggered", "siren_active": True})
            self.send_json({"status": "DRILL_DISPATCHED", "recipients": len(state.contacts)})
            return

        self.send_error(404, "Not Found")

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/contacts/"):
            identifier = urllib.parse.unquote(path.split("/api/contacts/")[1])
            state.contacts = [c for c in state.contacts if c.get("id") != identifier and c.get("phone") != identifier]
            self.send_json(state.contacts)
            return
        self.send_error(404, "Not Found")

    def handle_websocket(self):
        sec_key = self.headers.get("Sec-WebSocket-Key", "")
        sha = hashlib.sha1((sec_key.strip() + WS_GUID).encode("utf-8")).digest()
        accept_token = base64.b64encode(sha).decode("utf-8")

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_token}\r\n"
            "\r\n"
        )
        self.wfile.write(response.encode("latin1"))
        self.wfile.flush()

        sock = self.request
        client = WSClient(sock)
        with ws_lock:
            ws_clients.append(client)
        client.send_text(json.dumps(get_current_packet("connected")))

        try:
            while True:
                data = sock.recv(2)
                if not data or len(data) < 2:
                    break
                b1, b2 = data[0], data[1]
                opcode = b1 & 0x0F

                if opcode == 8:  # Close
                    break
                elif opcode == 9:  # Ping -> reply with Pong
                    sock.sendall(b"\x8a\x00")
                    continue

                is_masked = bool(b2 & 0x80)
                length = b2 & 0x7F
                if length == 126:
                    length = struct.unpack("!H", sock.recv(2))[0]
                elif length == 127:
                    length = struct.unpack("!Q", sock.recv(8))[0]

                mask = sock.recv(4) if is_masked else None
                body = b""
                while len(body) < length:
                    chunk = sock.recv(length - len(body))
                    if not chunk:
                        break
                    body += chunk

                if is_masked and mask:
                    body = bytes(b ^ mask[i % 4] for i, b in enumerate(body))

                if opcode == 1:  # Text frame
                    try:
                        msg = json.loads(body.decode("utf-8", errors="ignore"))
                        action = msg.get("action")
                        if action == "silence_siren":
                            state.siren_active = False
                            broadcast_ws({"event": "siren_silenced"})
                        elif action == "tare":
                            state.tilt_tare = state.tilt_deg
                            broadcast_ws(get_current_packet("telemetry"))
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            with ws_lock:
                if client in ws_clients:
                    ws_clients.remove(client)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def run_server(port: int = 8080):
    server = ThreadedHTTPServer(("0.0.0.0", port), SubSenseHandler)
    logger.info(f"SubSense Ultra-Lightweight Server running at http://0.0.0.0:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping server...")
    finally:
        server.server_close()

if __name__ == "__main__":
    run_server(8080)