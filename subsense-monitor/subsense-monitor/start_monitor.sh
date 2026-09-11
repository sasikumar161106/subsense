#!/usr/bin/env bash
# ─── SubSense Sensor Monitoring Dashboard ─── Linux / Raspberry Pi Launcher ───
# Single-process: Python backend + embedded React dashboard on :8080
# No Node.js / npm required!

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo -e "\033[1;36m"
echo "╔══════════════════════════════════════════════════╗"
echo "║   SubSense - Sensor Monitoring Dashboard         ║"
echo "║   Raspberry Pi / Linux Launcher                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "\033[0m"

# 1. Detect Python 3
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo -e "\033[1;31m[ERROR] Python 3 not found. Run: sudo apt install python3 python3-pip python3-venv\033[0m"
    exit 1
fi

# 2. Activate virtualenv if present
if [ -d "$DIR/venv" ]; then
    source "$DIR/venv/bin/activate"
elif [ -d "$HOME/subsense-venv" ]; then
    source "$HOME/subsense-venv/bin/activate"
fi

# 3. Optional ADB check for Termux SMS
if command -v adb &>/dev/null; then
    if adb devices | grep -q "device$"; then
        adb forward tcp:8022 tcp:8022 2>/dev/null || true
        echo -e "  \033[1;32m✓ ADB forwarded tcp:8022 -> tcp:8022 (Termux SMS ready)\033[0m"
    fi
fi

# 4. Get LAN IP for remote dashboard access
PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}') || PI_IP="localhost"

echo -e "\033[1;32m"
echo "══════════════════════════════════════════════════"
echo "  ✅ SubSense Monitor is STARTING!"
echo "  🌐 Dashboard URL:  http://${PI_IP}:8080"
echo "  📡 Local URL:      http://localhost:8080"
echo "  🔌 Serial Ports:   Auto-scanning (/dev/ttyUSB*, /dev/ttyACM*, COM*)"
echo "══════════════════════════════════════════════════"
echo -e "\033[0m"
echo "Press Ctrl+C to stop."

exec $PYTHON_CMD app.py
