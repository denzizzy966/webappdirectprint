import asyncio
import copy
import io
import logging
import os
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

# ────────────────────────────────────────────────────────────
# Fix Windows GUI / PyInstaller console=False (sys.stdout is None)
# ────────────────────────────────────────────────────────────
class SafeNullStream:
    """Stream pengganti stdout/stderr jika aplikasi berjalan tanpa jendela konsol (pythonw / PyInstaller console=False)."""
    encoding = "utf-8"
    errors = "replace"
    closed = False

    def write(self, s):
        pass

    def writelines(self, lines):
        pass

    def flush(self):
        pass

    def isatty(self):
        return False

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False

if sys.stdout is None or not hasattr(sys.stdout, "isatty"):
    sys.stdout = SafeNullStream()

if sys.stderr is None or not hasattr(sys.stderr, "isatty"):
    sys.stderr = SafeNullStream()

if sys.stdin is None:
    sys.stdin = io.StringIO()

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, LOG_DIR, config_manager
from app.api import http_router, ws_router
from app.printer import printer_manager
from app.serial_scale import scale_manager

# ────────────────────────────────────────────────────────────
# Setup Logging (Safe for Windows console cp1252 and GUI mode)
# ────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)

class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            if stream is None:
                return
            # Hindari UnicodeEncodeError pada terminal cp1252 Windows
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                stream.write(msg.encode('ascii', errors='backslashreplace').decode('ascii') + self.terminator)
            except Exception:
                pass
            self.flush()
        except Exception:
            self.handleError(record)

console_handler = SafeStreamHandler(sys.stdout)
file_handler = logging.FileHandler(LOG_DIR / "hardware_bridge.log", encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[console_handler, file_handler]
)
logger = logging.getLogger("hardware_bridge")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("[START] WebApp Hardware Bridge Universal v2.1.0 Aktif!")
    logger.info(f"   Platform: {sys.platform} ({os.name})")
    server_cfg = config_manager.get_server_config()
    scale_startup = server_cfg.get("enable_scale_at_startup", False)
    logger.info(f"   Koneksi Timbangan di Startup: {'AKTIF' if scale_startup else 'NONAKTIF (Port COM bebas untuk Web Serial JS browser)'}")
    logger.info("=" * 60)
    yield
    logger.info("[STOP] Mematikan Hardware Bridge dan menutup seluruh koneksi port...")
    for sc in scale_manager.scales.values():
        sc.disconnect()

# ────────────────────────────────────────────────────────────
# FastAPI Application
# ────────────────────────────────────────────────────────────
app = FastAPI(
    title="WebApp Hardware Bridge Universal",
    description="Bridge Direct Printing (Silent Print) & Serial Scale Connector untuk ERPNext dan Web Apps",
    version="2.1.0",
    lifespan=lifespan
)

server_cfg = config_manager.get_server_config()
origins = server_cfg.get("cors_origins", ["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & Templates
static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "templates"

if getattr(sys, 'frozen', False):
    if not static_dir.exists() and (BASE_DIR / "_internal" / "static").exists():
        static_dir = BASE_DIR / "_internal" / "static"
    if not templates_dir.exists() and (BASE_DIR / "_internal" / "templates").exists():
        templates_dir = BASE_DIR / "_internal" / "templates"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(templates_dir))

# Routers
app.include_router(http_router)
app.include_router(ws_router)

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Menampilkan dashboard web pemantauan hardware bridge."""
    try:
        # Format modern Starlette 0.36+ / 1.0+ (mendukung keyword arguments)
        return templates.TemplateResponse(request=request, name="index.html", context={"request": request})
    except TypeError:
        try:
            # Format lama Starlette < 0.36 (name sebagai argumen pertama)
            return templates.TemplateResponse("index.html", {"request": request})
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"[Dashboard] Jinja2 template error: {e}")

    # Fallback aman: jika Jinja2 mengalami kendala, sajikan berkas index.html langsung
    index_file = templates_dir / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>WebApp Hardware Bridge is Running</h1><p>Dashboard template not found.</p>")

# ────────────────────────────────────────────────────────────
# System Tray Integration (Windows & Linux Desktops)
# ────────────────────────────────────────────────────────────

def create_tray_icon(port: int, scale_port: Optional[int] = None):
    """Membuat ikon System Tray di pojok kanan bawah desktop (Windows)."""
    try:
        import pystray
        from PIL import Image, ImageDraw

        def generate_icon_image():
            img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse((4, 4, 60, 60), fill=(16, 185, 129))
            draw.polygon([(32, 10), (22, 34), (32, 34), (28, 54), (44, 28), (34, 28)], fill=(255, 255, 255))
            return img

        def open_browser(icon=None, item=None):
            webbrowser.open(f"http://127.0.0.1:{port}")

        def get_web_port_label(item=None):
            if scale_port and scale_port != port:
                return f"🟢 Port Print: {port} | Timbangan: {scale_port}"
            return f"🟢 Online — Port: {port}"

        def get_scale_port_label(item=None):
            try:
                active_ports = [
                    f"{sc.port} ({sc.name})" if sc.name else sc.port
                    for sc in scale_manager.scales.values()
                    if sc.connected and sc.port and sc.port.upper() != "SIM"
                ]
                if active_ports:
                    return f"⚖️ Timbangan: {', '.join(active_ports)}"
                sim = any(sc.connected and sc.port == "SIM" for sc in scale_manager.scales.values())
                if sim:
                    return "⚖️ Timbangan: SIM (Simulator)"
                return "⚖️ Timbangan: Tidak ada aktif"
            except Exception:
                return "⚖️ Timbangan: Memeriksa..."

        def get_printer_label(item=None):
            try:
                p = printer_manager.get_default_printer() or "(Belum disetel)"
                return f"🖨️ Printer: {p[:24]}"
            except Exception:
                return "🖨️ Printer: -"

        def restart_app(icon=None, item=None):
            logger.info("[Tray] Merestart Hardware Bridge...")
            if icon:
                try:
                    icon.stop()
                except Exception:
                    pass
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable] + sys.argv[1:])
            else:
                subprocess.Popen([sys.executable, str(BASE_DIR / "app.py")] + sys.argv[1:])
            os._exit(0)

        def stop_service_action(icon=None, item=None):
            logger.info("[Tray] Menghentikan Hardware Bridge (Close Service)...")
            if icon:
                try:
                    icon.stop()
                except Exception:
                    pass
            os._exit(0)

        def quit_app(icon=None, item=None):
            logger.info("[Tray] Menutup Hardware Bridge & Tray...")
            if icon:
                try:
                    icon.stop()
                except Exception:
                    pass
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("🌐 Buka Dashboard Web", open_browser, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(get_web_port_label, None, enabled=False),
            pystray.MenuItem(get_scale_port_label, None, enabled=False),
            pystray.MenuItem(get_printer_label, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🔄 Restart Service", restart_app),
            pystray.MenuItem("⏹️ Hentikan Service (Close)", stop_service_action),
            pystray.MenuItem("❌ Tutup Aplikasi & Tray", quit_app)
        )

        icon = pystray.Icon("HardwareBridge", generate_icon_image(), f"Hardware Bridge (🟢 Online) - Port {port}", menu)
        icon.run()
    except Exception as e:
        logger.warning(f"[Tray] System tray dinonaktifkan atau tidak tersedia: {e}")

# ────────────────────────────────────────────────────────────
# Helper Cek Port Bebas
# ────────────────────────────────────────────────────────────

def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except socket.error:
            return False

# ────────────────────────────────────────────────────────────
# Main Entry Point
# ────────────────────────────────────────────────────────────

def main():
    host = server_cfg.get("host", "127.0.0.1")
    configured_port = int(server_cfg.get("port", 18212))

    # Cek apakah port yang dikonfigurasi bebas
    active_port = configured_port
    if not is_port_available(host, active_port):
        logger.warning(f"[Port] Port {active_port} sedang dipakai oleh aplikasi lain!")
        # Jika port 12212 sibuk (misal dipakai javaw.exe bridge lama), fallback ke 18212
        if active_port == 12212 and is_port_available(host, 18212):
            active_port = 18212
            logger.info(f"[Port] Beralih otomatis ke port alternatif: {active_port}")
        elif active_port == 18212 and is_port_available(host, 12212):
            active_port = 12212
            logger.info(f"[Port] Beralih otomatis ke port alternatif: {active_port}")

    enable_tray = server_cfg.get("enable_tray", True) and ("--no-tray" not in sys.argv)

    # Port khusus timbangan (jika diset terpisah di bridge_config.json)
    scale_port_cfg = server_cfg.get("scale_port")
    active_scale_port = None
    if scale_port_cfg:
        try:
            sp = int(scale_port_cfg)
            if sp > 0 and sp != active_port:
                if is_port_available(host, sp):
                    active_scale_port = sp
                else:
                    logger.warning(f"[ScalePort] Port khusus timbangan {sp} sedang dipakai aplikasi lain!")
        except Exception as e:
            logger.warning(f"[ScalePort] Nilai scale_port '{scale_port_cfg}' tidak valid: {e}")

    if enable_tray and sys.platform == "win32":
        tray_thread = threading.Thread(target=create_tray_icon, args=(active_port, active_scale_port), daemon=True)
        tray_thread.start()

    logger.info(f"[Server] Berjalan di: http://{host}:{active_port}")
    logger.info(f"[Server] WebSocket: ws://{host}:{active_port}/ws")

    import uvicorn.config
    log_config = copy.deepcopy(uvicorn.config.LOGGING_CONFIG)
    if "formatters" in log_config:
        for fmt in log_config["formatters"].values():
            if isinstance(fmt, dict) and "use_colors" in fmt:
                fmt["use_colors"] = False

    # Jika port timbangan dipisah, jalankan server kedua di background thread
    if active_scale_port:
        logger.info(f"[ScaleServer] Port Khusus Timbangan Terpisah Aktif: http://{host}:{active_scale_port}")
        logger.info(f"[ScaleServer] WebSocket Timbangan: ws://{host}:{active_scale_port}/ws")
        def run_scale_listener():
            try:
                scale_cfg = uvicorn.Config(app, host=host, port=active_scale_port, log_level="warning", log_config=log_config)
                server = uvicorn.Server(scale_cfg)
                server.run()
            except Exception as ex:
                logger.error(f"[ScaleServer] Gagal menjalankan server timbangan di port {active_scale_port}: {ex}")

        scale_thread = threading.Thread(target=run_scale_listener, daemon=True)
        scale_thread.start()

    uvicorn.run(app, host=host, port=active_port, log_level="info", log_config=log_config)

if __name__ == "__main__":
    main()
