#!/usr/bin/env python3
"""
WebApp Hardware Bridge Universal - Desktop System Tray Indicator
Berjalan di tray taskbar Linux Mint (Cinnamon/MATE), Ubuntu, dan Windows 10/11.
Memantau status daemon bridge, menampilkan menu cepat, dan membuka dashboard web.
"""

import os
import sys
import time
import socket
import threading
import webbrowser
import subprocess
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    print("[Tray] Error: Pustaka 'pystray' dan 'Pillow' diperlukan untuk System Tray.")
    print("       Jalankan: pip install pystray Pillow")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "bridge_config.json"

def get_bridge_port() -> int:
    try:
        import json
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return int(cfg.get("server", {}).get("port", 18212))
    except Exception:
        pass
    return 18212

BRIDGE_PORT = get_bridge_port()
API_BASE = f"http://127.0.0.1:{BRIDGE_PORT}"

bridge_status = {
    "online": False,
    "version": "2.1.0",
    "web_port": BRIDGE_PORT,
    "default_printer": "-",
    "total_printers": 0,
    "total_scales": 0,
    "connected_scale_ports": [],
    "scale_info_text": "Memeriksa..."
}

def generate_icon(online: bool = True):
    """Membuat gambar ikon bulat dengan simbol petir (Hijau jika Online, Abu-abu jika Offline)."""
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bg_color = (16, 185, 129, 255) if online else (148, 163, 184, 255)
    border_color = (5, 150, 105, 255) if online else (100, 116, 139, 255)

    draw.ellipse((2, 2, 62, 62), fill=bg_color, outline=border_color, width=2)
    polygon_points = [(34, 8), (20, 34), (32, 34), (26, 56), (46, 26), (34, 26)]
    draw.polygon(polygon_points, fill=(255, 255, 255, 255))
    return img

def check_status_loop(icon: pystray.Icon):
    """Thread latar belakang untuk polling status bridge setiap 2.5 detik."""
    last_online = None
    while getattr(icon, '_running', True):
        is_online = False
        try:
            if requests:
                resp = requests.get(f"{API_BASE}/api/status", timeout=1.8)
                if resp.status_code == 200:
                    data = resp.json()
                    is_online = True
                    bridge_status["online"] = True
                    bridge_status["version"] = data.get("version", "2.1.0")
                    bridge_status["default_printer"] = data.get("default_printer") or "-"
                    bridge_status["total_printers"] = data.get("total_printers", 0)
                    bridge_status["total_scales"] = data.get("total_scales", 0)
                    scale_ports = data.get("connected_scale_ports", [])
                    bridge_status["connected_scale_ports"] = scale_ports
                    if scale_ports:
                        bridge_status["scale_info_text"] = ", ".join(scale_ports)
                    else:
                        bridge_status["scale_info_text"] = "Tidak ada aktif"
            else:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    if s.connect_ex(("127.0.0.1", BRIDGE_PORT)) == 0:
                        is_online = True
        except Exception:
            is_online = False

        bridge_status["online"] = is_online
        if not is_online:
            bridge_status["scale_info_text"] = "Service Offline"

        if is_online != last_online:
            last_online = is_online
            try:
                icon.icon = generate_icon(is_online)
                status_text = "🟢 Online" if is_online else "🔴 Offline"
                icon.title = f"Hardware Bridge ({status_text}) - Port {BRIDGE_PORT}"
            except Exception:
                pass

        time.sleep(2.5)

def open_dashboard(icon=None, item=None):
    webbrowser.open(f"http://127.0.0.1:{BRIDGE_PORT}")

def get_web_port_label(item=None):
    if bridge_status["online"]:
        return f"🟢 Online — Port Web: {BRIDGE_PORT}"
    return f"🔴 Offline — Port Web: {BRIDGE_PORT}"

def get_scale_port_label(item=None):
    return f"⚖️ Timbangan: {bridge_status.get('scale_info_text', 'Tidak ada aktif')}"

def get_printer_label(item=None):
    p = bridge_status.get("default_printer", "-")
    return f"🖨️ Printer: {p[:24]}"

def restart_service(icon=None, item=None):
    if sys.platform == "win32":
        subprocess.Popen([sys.executable, str(BASE_DIR / "app.py")])
    else:
        cmd = "sudo systemctl restart hardware-bridge 2>/dev/null || systemctl --user restart hardware-bridge 2>/dev/null || (pkill -f app.py && nohup python3 app.py >/dev/null 2>&1 &)"
        os.system(cmd)

def stop_service(icon=None, item=None):
    if sys.platform == "win32":
        os.system('taskkill /F /IM HardwareBridge.exe 2>nul || taskkill /F /FI "WINDOWTITLE eq HardwareBridge*" 2>nul')
    else:
        cmd = "sudo systemctl stop hardware-bridge 2>/dev/null || systemctl --user stop hardware-bridge 2>/dev/null || pkill -f app.py"
        os.system(cmd)
    bridge_status["online"] = False
    bridge_status["scale_info_text"] = "Service Dimatikan"
    if icon:
        try:
            icon.icon = generate_icon(False)
            icon.title = f"Hardware Bridge (🔴 Offline) - Port {BRIDGE_PORT}"
        except Exception:
            pass

def quit_app(icon: pystray.Icon, item=None):
    stop_service(icon, item)
    if icon:
        icon.stop()
    os._exit(0)

def create_menu():
    return pystray.Menu(
        pystray.MenuItem("🌐 Buka Dashboard Web", open_dashboard, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(get_web_port_label, None, enabled=False),
        pystray.MenuItem(get_scale_port_label, None, enabled=False),
        pystray.MenuItem(get_printer_label, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("🔄 Restart Service", restart_service),
        pystray.MenuItem("⏹️ Hentikan Service (Close)", stop_service),
        pystray.MenuItem("❌ Tutup Aplikasi & Tray", quit_app)
    )

def main():
    icon = pystray.Icon(
        name="HardwareBridge",
        icon=generate_icon(False),
        title=f"Hardware Bridge - Port {BRIDGE_PORT}",
        menu=create_menu()
    )

    t = threading.Thread(target=check_status_loop, args=(icon,), daemon=True)
    t.start()

    try:
        icon.run()
    except Exception as e:
        print(f"[Tray] Gagal menjalankan System Tray: {e}")

if __name__ == "__main__":
    main()
