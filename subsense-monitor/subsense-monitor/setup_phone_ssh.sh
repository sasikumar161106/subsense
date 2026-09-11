#!/usr/bin/env bash
# ─── SubSense Phone Wi-Fi SSH Link Helper ───
# Configures passwordless SSH from the Raspberry Pi to your Android Termux phone.

PHONE_IP="${1:-192.168.219.12}"
PHONE_USER="${2:-u0_a382}"
PHONE_PORT="8022"

echo -e "\033[1;36mLinking Raspberry Pi to Android Termux at ${PHONE_USER}@${PHONE_IP}:${PHONE_PORT}...\033[0m"

# 1. Ensure SSH key exists
if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
    echo "Generating ed25519 keypair..."
    ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519"
fi

# 2. Copy key to phone (enter password once)
echo "Copying key to Termux (enter phone password when prompted)..."
ssh-copy-id -p "$PHONE_PORT" -o StrictHostKeyChecking=no "${PHONE_USER}@${PHONE_IP}"

# 3. Add to ~/.ssh/config for zero-config SSH
mkdir -p "$HOME/.ssh"
if ! grep -q "$PHONE_IP" "$HOME/.ssh/config" 2>/dev/null; then
    cat <<EOF >> "$HOME/.ssh/config"

Host ${PHONE_IP}
    HostName ${PHONE_IP}
    User ${PHONE_USER}
    Port ${PHONE_PORT}
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking no
EOF
    chmod 600 "$HOME/.ssh/config"
fi

echo -e "\033[1;32m✓ Phone SSH link successfully configured!\033[0m"
