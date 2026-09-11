# SubSense — Standalone Sensor Monitoring Dashboard (Ultra-Lightweight)
### Real-Time Telemetry, Pitch/Vibration Sensing & ESP-NOW Mesh Display

A 100% pure Python HTTP & WebSocket monitoring server.
- **Zero heavy frameworks**: No FastAPI, No Pydantic, No Uvicorn, No Node.js.
- **Zero Rust / Cython compilation**: Installs in under **20 seconds** on any Raspberry Pi.
- **Only 1 dependency**: `pyserial` (can even be installed via `apt`).

---

## Folder Contents

```
subsense-monitor/
├── app.py                 # Pure Python server (Serial reader + WebSocket + Static server)
├── requirements.txt       # ONLY 'pyserial>=3.5'
├── dist/                  # Pre-compiled React SPA dashboard UI
│   ├── index.html
│   └── assets/            # Bundled CSS & JavaScript
├── start_monitor.sh       # 1-click launcher for Linux / Raspberry Pi
├── start_monitor.ps1      # 1-click launcher for Windows
├── setup_raspberry_pi.sh  # Fast provisioner (pre-built apt packages: 20 seconds)
├── subsense.service       # Systemd unit file for auto-start on boot
└── README.md              # Instructions
```

---

## Running on Raspberry Pi (Fast Setup)

### 1. Copy to Raspberry Pi
From your PC terminal:
```powershell
scp -r e:\Subsense\subsense-monitor pi@<raspberry-pi-ip>:~/
```
*(Or transfer `subsense-monitor.zip` and unzip it on the Pi).*

### 2. Fast Setup (Takes ~20 Seconds)
```bash
cd ~/subsense-monitor
chmod +x setup_raspberry_pi.sh start_monitor.sh
./setup_raspberry_pi.sh
```

### 3. Run SubSense

**Manual Start**:
```bash
./start_monitor.sh
```
*(Or simply `python3 app.py`)*

**Background Auto-Start on Boot (Systemd)**:
```bash
sudo systemctl enable --now subsense.service
```

---

## Running on Windows PC

```powershell
powershell -ExecutionPolicy Bypass -File e:\Subsense\subsense-monitor\start_monitor.ps1
```
Or simply:
```bash
cd e:\Subsense\subsense-monitor
pip install pyserial
python app.py
```

---

## Open the Dashboard

From any device on the same Wi-Fi:
```
http://<raspberry-pi-ip>:8080/
```
*(Locally: `http://localhost:8080/`)*
