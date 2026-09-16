#!/usr/bin/env bash
# ==============================================================================
# Uninstaller WebApp Hardware Bridge (Linux Mint / Ubuntu)
# ==============================================================================

CURRENT_USER="${SUDO_USER:-$USER}"

echo "=========================================================="
echo "  Mencopot WebApp Hardware Bridge..."
echo "=========================================================="

echo "[1/4] Menghentikan service Hardware Bridge di background..."
sudo systemctl stop hardware-bridge.service 2>/dev/null || true
sudo systemctl disable hardware-bridge.service 2>/dev/null || true

echo "[2/4] Menghentikan System Tray Indicator & Autostart..."
pkill -f "tray_indicator.py" 2>/dev/null || true

USER_HOME=$(getent passwd "$CURRENT_USER" | cut -d: -f6)
if [ -z "$USER_HOME" ]; then
    USER_HOME="/home/$CURRENT_USER"
fi
if [ -f "$USER_HOME/.config/autostart/hardware-bridge-tray.desktop" ]; then
    rm -f "$USER_HOME/.config/autostart/hardware-bridge-tray.desktop"
fi

echo "[3/4] Menghapus berkas service systemd..."
if [ -f "/etc/systemd/system/hardware-bridge.service" ]; then
    sudo rm -f "/etc/systemd/system/hardware-bridge.service"
    sudo systemctl daemon-reload
    sudo systemctl reset-failed 2>/dev/null || true
fi

echo "[4/4] Menghapus aturan udev serial & printer..."
if [ -f "/etc/udev/rules.d/99-hardware-bridge.rules" ]; then
    sudo rm -f "/etc/udev/rules.d/99-hardware-bridge.rules"
    sudo udevadm control --reload-rules 2>/dev/null || true
fi

echo "=========================================================="
echo "  ✅ WebApp Hardware Bridge berhasil dicopot sepenuhnya!"
echo "=========================================================="
