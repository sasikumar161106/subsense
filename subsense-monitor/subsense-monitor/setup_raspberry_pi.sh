#!/usr/bin/env bash
# ─── SubSense Sensor Monitoring Dashboard ─── Raspberry Pi Fast Setup ───
# Ultra-lightweight: Zero Rust/Cython compilation, zero heavy dependencies.
# Installs in seconds using pre-built packages.

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo -e "\033[1;36m"
echo "╔══════════════════════════════════════════════════╗"
echo "║   SubSense Monitor - Fast Raspberry Pi Setup    ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "\033[0m"

# 1. Install system packages via APT (pre-built binaries: 5 seconds)
echo -e "\033[1;33m[1/3] Installing pre-built system packages (instant APT)...\033[0m"
sudo apt-get update
sudo apt-get install -y python3 python3-serial python3-pip openssh-client adb curl
echo "      ✓ System packages installed."

# 2. Grant hardware serial port permissions
echo -e "\033[1;33m[2/3] Adding user '$(whoami)' to dialout group for USB UART access...\033[0m"
sudo usermod -a -G dialout "$USER"
echo "      ✓ dialout group assigned."

# 3. Ensure pyserial is present for python3
python3 -c "import serial" 2>/dev/null || pip3 install --break-system-packages pyserial || pip install pyserial

# 4. Background service setup (systemd)
echo -e "\033[1;33m[3/3] Setting up systemd background service...\033[0m"
SERVICE_FILE="/etc/systemd/system/subsense.service"
sudo bash -c "cat <<EOF > ${SERVICE_FILE}
[Unit]
Description=SubSense Sensor Monitoring Dashboard
After=network.target network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 ${DIR}/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
echo "      ✓ Installed ${SERVICE_FILE}"

PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}') || PI_IP="<pi-ip>"

echo -e "\033[1;32m"
echo "══════════════════════════════════════════════════════════"
echo "  ✅ Setup COMPLETE in under 30 seconds!"
echo ""
echo "  To start the monitor manually:"
echo "    ./start_monitor.sh"
echo ""
echo "  To run as auto-boot background service:"
echo "    sudo systemctl enable --now subsense.service"
echo ""
echo "  View live logs:"
echo "    sudo journalctl -u subsense.service -f"
echo ""
echo "  Open Dashboard on any phone/PC on Wi-Fi:"
echo "    http://${PI_IP}:8080"
echo "══════════════════════════════════════════════════════════"
echo -e "\033[0m"
echo -e "\033[0;33mNOTE: If this was the first time adding user to 'dialout', reboot once: sudo reboot\033[0m"
