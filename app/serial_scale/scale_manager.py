import asyncio
import logging
import math
import random
import re
import sys
import threading
import time
from collections import deque
from typing import Dict, Any, List, Optional

import serial
import serial.tools.list_ports

from .protocols import PROTOCOLS, parse_scale_line
from ..config import config_manager

logger = logging.getLogger("scale_manager")

class ScaleInstance:
    """Mengelola koneksi serial satu perangkat timbangan digital."""

    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.name = cfg.get("name", "Timbangan")
        self.port = cfg.get("port", "")
        self.usb_serial = (cfg.get("usb_serial") or "").strip().upper()
        self.protocol = cfg.get("protocol", "auto")  # mettler | shinko | and | auto
        self.mode = cfg.get("mode", "poll")          # poll | continuous
        self.baud = int(cfg.get("baud", 9600))
        self.databits = int(cfg.get("databits", 8))
        self.parity = cfg.get("parity", "N")
        self.stopbits = int(cfg.get("stopbits", 1))
        self.poll_interval = float(cfg.get("poll_interval", 0.5))
        self.autoconnect = cfg.get("autoconnect", True)

        self.ser: Optional[serial.Serial] = None
        self.lock = threading.RLock()
        self.connected = False
        self.sim = False
        self.manual_stop = False
        self.state = "disconnected"  # online, standby, locked_by_other, idle_released, paused, disconnected
        self.status_detail = ""

        # Data pembacaan
        self.weight: Optional[float] = 0.0
        self.unit = "g"
        self.stable: Optional[bool] = False
        self.last_update_ts: float = 0.0
        self.tare_offset: float = 0.0
        self.consecutive_empty_polls = 0

        # On-Demand & Sharing
        self.last_api_activity = time.time()
        self.sharing_mode = config_manager.get_server_config().get("sharing_mode", "continuous")
        self.idle_release_seconds = float(config_manager.get_server_config().get("idle_release_seconds", 4.0))

        # Threading
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._threads: List[threading.Thread] = []

        # Log lokal
        self.log_history = deque(maxlen=200)

    def _log(self, direction: str, message: str):
        ts = time.strftime("%H:%M:%S")
        self.log_history.append({"ts": ts, "dir": direction, "msg": message})
        logger.info(f"[{self.name}] {direction}: {message}")

    def mark_api_activity(self):
        """Membangkitkan port jika sedang idle_released pada mode on_demand."""
        server_cfg = config_manager.get_server_config()
        if not server_cfg.get("enable_scale_at_startup", False) and not self.connected:
            return
        self.last_api_activity = time.time()
        if self.sharing_mode == "on_demand" and not self.sim and not self._paused.is_set():
            if not self.connected and self.state == "idle_released":
                threading.Thread(target=self._reopen_serial, daemon=True).start()

    def _force_close_serial(self):
        with self.lock:
            s = self.ser
            self.ser = None
            self.connected = False
            if s:
                try:
                    for cancel in ('cancel_read', 'cancel_write'):
                        if hasattr(s, cancel):
                            getattr(s, cancel)()
                except Exception:
                    pass
                try:
                    s.close()
                except Exception:
                    pass

    def _auto_resolve_port(self) -> bool:
        """Deteksi otomatis jika port serial berpindah slot USB (misal COM5 -> COM1)."""
        try:
            present_ports = list(serial.tools.list_ports.comports())
            present_devices = {p.device for p in present_ports}

            # 1. Jika port yang dikonfigurasi saat ini masih terpasang, tetap gunakan
            if self.port and self.port in present_devices:
                return True

            # 2. Jika port lama hilang, cari berdasarkan USB Serial Number (e.g. BMCBE14A312)
            if self.usb_serial:
                for p in present_ports:
                    sn = (p.serial_number or "").strip().upper()
                    hw = (p.hwid or "").strip().upper()
                    if self.usb_serial == sn or f"SER={self.usb_serial}" in hw:
                        logger.info(f"[{self.name}] Port otomatis berpindah dari '{self.port}' ke '{p.device}' (S/N: {self.usb_serial})")
                        self.port = p.device
                        return True

            # 3. Fallback: Cari adapter USB Serial (Prolific PL2303, CH340, FTDI, CP210)
            for p in present_ports:
                hw = (p.hwid or "").upper()
                desc = (p.description or "").upper()
                if "067B:23A3" in hw or "PL2303" in desc or "CH340" in desc or "FTDI" in desc or "CP210" in desc:
                    logger.info(f"[{self.name}] Port otomatis mendeteksi adapter serial di '{p.device}' ({p.description})")
                    self.port = p.device
                    return True
        except Exception as e:
            logger.debug(f"Auto resolve port error: {e}")
        return False

    def _kickstart_stream(self):
        """Kirim perintah inisialisasi / streaming ke timbangan agar mulai mengirim data."""
        if not self.ser or not self.connected:
            return
        try:
            if self.protocol in ("shinko", "auto"):
                self.ser.write(b"O1\r\n")
                self.ser.write(b"O9\r\n")
            elif self.protocol == "mettler":
                self.ser.write(b"SIR\r\n")
                self.ser.write(b"SI\r\n")
            elif self.protocol == "and":
                self.ser.write(b"SIR\r\n")
                self.ser.write(b"Q\r\n")
        except Exception as e:
            logger.debug(f"Kickstart stream error: {e}")

    def connect(self, override_cfg: Optional[Dict[str, Any]] = None) -> bool:
        with self.lock:
            self.disconnect()
            self._stop.clear()
            self._paused.clear()
            self.manual_stop = False

            if override_cfg:
                self.cfg.update(override_cfg)
                self.port = self.cfg.get("port", self.port)
                self.baud = int(self.cfg.get("baud", self.baud))
                self.protocol = self.cfg.get("protocol", self.protocol)

            # Mode Simulator
            if self.port.upper() == "SIM":
                self.sim = True
                self.connected = True
                self.state = "online"
                self.status_detail = "Simulator Timbangan Aktif"
                t = threading.Thread(target=self._simulator_loop, daemon=True)
                t.start()
                self._threads = [t]
                self._log("SYS", "Terhubung ke simulator timbangan.")
                return True

            self.sim = False
            return self._open_serial_port()

    def _open_serial_port(self) -> bool:
        parity_map = {
            'N': serial.PARITY_NONE,
            'E': serial.PARITY_EVEN,
            'O': serial.PARITY_ODD
        }
        try:
            self._stop.clear()
            self._paused.clear()

            self._auto_resolve_port()

            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=serial.SEVENBITS if self.databits == 7 else serial.EIGHTBITS,
                parity=parity_map.get(self.parity, serial.PARITY_NONE),
                stopbits=serial.STOPBITS_ONE if self.stopbits == 1 else serial.STOPBITS_TWO,
                timeout=0.2,
                write_timeout=0.5
            )

            # Aktifkan sinyal DTR & RTS (Sangat krusial untuk adapter Prolific PL2303 & isolator sinyal!)
            try:
                self.ser.dtr = True
                self.ser.rts = True
            except Exception:
                pass

            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except Exception:
                pass

            self.connected = True
            self.state = "online"
            self.status_detail = f"Terhubung ke {self.port} ({self.baud} baud)"
            self._log("SYS", f"Port {self.port} berhasil dibuka.")

            # Thread 1: Read Loop (Non-blocking framing pembaca buffer)
            t_read = threading.Thread(target=self._read_loop, daemon=True)
            t_read.start()
            self._threads = [t_read]

            # Kickstart continuous stream atau poll
            self._kickstart_stream()

            # Thread 2: Poll Loop (jika mode poll atau auto)
            t_poll = threading.Thread(target=self._poll_loop, daemon=True)
            t_poll.start()
            self._threads.append(t_poll)

            return True

        except serial.SerialException as e:
            err = str(e)
            if "PermissionError" in err or "Access is denied" in err or "Device or resource busy" in err:
                self.state = "locked_by_other"
                self.status_detail = "Port sedang dipakai aplikasi lain (Delphi / Browser)"
            elif "FileNotFoundError" in err or "cannot find the file" in err:
                self.state = "disconnected"
                self.status_detail = f"Port {self.port} tidak ditemukan (kabel belum dicolok)"
            else:
                self.state = "disconnected"
                self.status_detail = f"Gagal buka port: {err}"
            self._log("ERR", self.status_detail)
            return False
        except Exception as e:
            self.state = "disconnected"
            self.status_detail = str(e)
            return False

    def _reopen_serial(self):
        with self.lock:
            if not self.connected and not self.sim and not self.manual_stop:
                self._open_serial_port()

    def disconnect(self, is_manual: bool = False):
        with self.lock:
            if is_manual:
                self.manual_stop = True
                self.state = "paused"
                self.status_detail = "Port dilepas manual oleh operator"
            else:
                self.state = "disconnected"
                self.status_detail = "Koneksi diputus"

            self._stop.set()
            self._force_close_serial()

            for t in self._threads:
                t.join(timeout=0.3)
            self._threads = []
            self.sim = False

    def pause(self, seconds: Optional[int] = None):
        """Melepas port serial sementara agar aplikasi lain (misal Delphi) bisa mengakses COM."""
        self.disconnect(is_manual=True)
        if seconds and seconds > 0:
            def auto_resume():
                time.sleep(seconds)
                if self.manual_stop:
                    self.resume()
            threading.Thread(target=auto_resume, daemon=True).start()

    def resume(self):
        """Menyambungkan kembali port timbangan."""
        with self.lock:
            self.manual_stop = False
            self._paused.clear()
            self._stop.clear()
            if not self.sim:
                self._auto_resolve_port()
                self._open_serial_port()

    def send_command(self, cmd: str) -> bool:
        self.mark_api_activity()
        if not cmd:
            return False

        if self.sim:
            if cmd.strip().upper() in ('Z', 'ZERO'):
                self.tare_offset = self.weight or 0.0
                self.weight = 0.0
                self.stable = True
                return True
            if cmd.strip().upper() in ('T', 'TARE'):
                self.tare_offset = self.weight or 0.0
                self.weight = 0.0
                self.stable = True
                return True
            return True

        with self.lock:
            if not self.ser or not self.connected:
                return False
            try:
                data = cmd if cmd.endswith("\r\n") or cmd.endswith("\n") else cmd + "\r\n"
                self.ser.write(data.encode("ascii", errors="ignore"))
                self._log("TX", cmd.strip())
                return True
            except Exception as e:
                self._log("ERR", f"Gagal kirim command: {e}")
                return False

    def zero(self) -> bool:
        proto = PROTOCOLS.get(self.protocol, PROTOCOLS["shinko"] if self.protocol == "shinko" else PROTOCOLS["mettler"])
        cmd = proto.get("zero", "Z\r\n")
        return self.send_command(cmd)

    def tare(self) -> bool:
        proto = PROTOCOLS.get(self.protocol, PROTOCOLS["shinko"] if self.protocol == "shinko" else PROTOCOLS["mettler"])
        cmd = proto.get("tare", "T\r\n")
        return self.send_command(cmd)

    def get_data(self) -> Dict[str, Any]:
        self.mark_api_activity()
        w = round(self.weight - self.tare_offset, 3) if self.weight is not None else 0.0
        now = time.time()
        age = round(now - self.last_update_ts, 2) if self.last_update_ts else 999.0
        return {
            "name": self.name,
            "port": self.port,
            "protocol": self.protocol,
            "state": self.state,
            "status_detail": self.status_detail,
            "connected": self.connected,
            "autoconnect": self.autoconnect,
            "weight": w,
            "raw_weight": round(self.weight, 3) if self.weight is not None else 0.0,
            "unit": self.unit,
            "stable": self.stable,
            "timestamp": self.last_update_ts,
            "age": age,
            "ok": self.connected and (age < 10.0 if not self.sim else True)
        }

    # ────────────────────────────────────────────────────────────
    # Loop Pembaca Buffer Serial (Framing Per-Baris Non-Blocking)
    # ────────────────────────────────────────────────────────────
    def _read_loop(self):
        buf = b""
        while not self._stop.is_set():
            ser = self.ser
            if not ser or not self.connected:
                break
            try:
                chunk = ser.read(256)
            except Exception as e:
                # HOTPLUG DISCONNECT: Kabel dicabut saat runtime!
                self._log("SYS", f"Kabel serial terputus (Hotplug): {e}")
                self._force_close_serial()
                self.state = "disconnected"
                self.status_detail = "Kabel USB dicabut"
                break

            if not chunk:
                time.sleep(0.02)
                continue

            buf += chunk
            while True:
                m = re.search(rb'\r\n|\r|\n', buf)
                if not m:
                    break
                line_raw = buf[:m.start()]
                buf = buf[m.end():]
                line_str = line_raw.decode("latin1", errors="ignore").strip()
                if line_str:
                    self._handle_line(line_str)

            if len(buf) > 4096:
                buf = b""

    def _handle_line(self, line: str):
        parsed = parse_scale_line(line)
        now = time.time()

        if parsed["kind"] == "weight":
            self.weight = parsed["weight"]
            self.unit = parsed.get("unit", "g")
            self.stable = parsed.get("stable", True)
            self.last_update_ts = now
            self.consecutive_empty_polls = 0

            # Selalu pastikan status Online dengan berat terbaru
            self.state = "online"
            self.status_detail = f"Online - {self.weight} {self.unit}"

            # Auto-detect protokol dari format stream
            if self.protocol == "auto" or self.protocol != parsed.get("protocol"):
                detected = parsed.get("protocol")
                if detected and detected in PROTOCOLS:
                    self.protocol = detected

            self._log("RX", f"{line} -> {self.weight} {self.unit} (Stable: {self.stable})")

        elif parsed["kind"] == "status":
            self.status_detail = parsed["status"]
            self.last_update_ts = now
            self._log("RX", parsed["status"])

        elif parsed["kind"] == "ack":
            self.last_update_ts = now
            self.consecutive_empty_polls = 0
            if self.state == "standby":
                self.state = "online"
                self.status_detail = "Online"

    # ────────────────────────────────────────────────────────────
    # Loop Polling & Heartbeat Saklar
    # ────────────────────────────────────────────────────────────
    def _poll_loop(self):
        while not self._stop.is_set():
            if not self.connected and not self.sim:
                break

            now = time.time()
            if self.last_update_ts and (now - self.last_update_ts > 2.5):
                self.consecutive_empty_polls += 1
            else:
                self.consecutive_empty_polls = 0

            if self.consecutive_empty_polls >= 2 and self.state == "online":
                self.state = "standby"
                self.status_detail = "Standby (Saklar timbangan off?)"

            # Jika standby atau tidak ada data masuk, bersihkan buffer dan coba pancing (probe/heartbeat)
            if self.state == "standby" and self.ser:
                try:
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                except Exception:
                    pass
                self._kickstart_stream()
            elif self.mode == "poll" or self.protocol in ("mettler", "and", "shinko"):
                proto = PROTOCOLS.get(self.protocol, PROTOCOLS["shinko"] if self.protocol == "shinko" else PROTOCOLS["mettler"])
                poll_cmd = proto.get("poll")
                if poll_cmd:
                    try:
                        self.send_command(poll_cmd)
                    except Exception:
                        pass

            sleep_time = 1.0 if self.state == "standby" else self.poll_interval
            self._stop.wait(sleep_time)

    # ────────────────────────────────────────────────────────────
    # Loop Simulator
    # ────────────────────────────────────────────────────────────
    def _simulator_loop(self):
        base_weight = 125.40
        step = 0
        while not self._stop.is_set():
            if self._paused.is_set():
                time.sleep(0.5)
                continue

            step += 1
            cycle = step % 20
            if cycle < 12:
                self.stable = True
                self.weight = base_weight + (int(step / 40) % 5) * 10.0
            else:
                self.stable = False
                noise = random.uniform(-0.8, 0.8)
                self.weight = base_weight + noise

            self.unit = "g"
            self.last_update_ts = time.time()
            time.sleep(self.poll_interval)


class ScaleManager:
    """Manajer koleksi timbangan dengan Hotplug Watchdog & Auto-Connect Aktif."""

    def __init__(self):
        self.scales: Dict[str, ScaleInstance] = {}
        self._watchdog_stop = threading.Event()
        self._watchdog_thread: Optional[threading.Thread] = None
        self._init_scales()
        self._start_watchdog()

    def _init_scales(self):
        server_cfg = config_manager.get_server_config()
        enable_startup = server_cfg.get("enable_scale_at_startup", False)
        scales_cfg = config_manager.get_scales_config()
        for sc in scales_cfg:
            instance = ScaleInstance(sc)
            self.scales[instance.name] = instance
            if enable_startup and sc.get("autoconnect", True):
                instance.connect()
            else:
                instance.state = "disconnected"
                if not enable_startup:
                    instance.status_detail = "Startup nonaktif (port bebas untuk JS / browser)"
                else:
                    instance.status_detail = "Koneksi diputus (autoconnect off)"
        if not enable_startup:
            logger.info("[ScaleManager] Opsi startup timbangan dinonaktifkan: Port serial tidak dibuka saat startup (port bebas untuk browser JS).")

    def _start_watchdog(self):
        """Menjalankan watchdog di background untuk auto-detect & auto-reconnect saat USB dicolok."""
        self._watchdog_stop.clear()
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()
        logger.info("[ScaleManager] Background Hotplug Watchdog aktif (deteksi otomatis setiap 1 detik).")

    def _watchdog_loop(self):
        while not self._watchdog_stop.is_set():
            try:
                server_cfg = config_manager.get_server_config()
                enable_startup = server_cfg.get("enable_scale_at_startup", False)
                present_ports = list(serial.tools.list_ports.comports())
                present_devices = {p.device for p in present_ports}

                # 1. Cek port yang dicabut
                for sc in self.scales.values():
                    if sc.port != "SIM" and sc.connected and sc.port not in present_devices:
                        logger.warning(f"[Watchdog] Perangkat {sc.name} ({sc.port}) dicabut dari port USB!")
                        sc.disconnect()

                # 2. Cek port yang baru dicolokkan (Auto-Connect & Auto-Resolve)
                # Hanya jika opsi startup / autoconnect timbangan diizinkan aktif
                if enable_startup:
                    for sc in self.scales.values():
                        if sc.port == "SIM":
                            continue
                        if sc.manual_stop:
                            continue

                        # Jika belum terhubung dan autoconnect aktif
                        if not sc.connected and sc.autoconnect:
                            matched_port = None

                            # Cocokkan berdasarkan USB Serial Number (e.g. BMCBE14A312)
                            if sc.usb_serial:
                                for p in present_ports:
                                    sn = (p.serial_number or "").strip().upper()
                                    hw = (p.hwid or "").strip().upper()
                                    if sc.usb_serial == sn or f"SER={sc.usb_serial}" in hw:
                                        matched_port = p.device
                                        break

                            # Cocokkan berdasarkan port name (e.g. COM5)
                            if not matched_port and sc.port in present_devices:
                                matched_port = sc.port

                            # Jika ditemukan, koneksikan otomatis!
                            if matched_port:
                                logger.info(f"[Watchdog] Timbangan '{sc.name}' terdeteksi dicolokkan ke {matched_port}. Melakukan Auto-Connect...")
                                sc.port = matched_port
                                sc.connect()

            except Exception as e:
                logger.debug(f"[Watchdog] Error: {e}")

            time.sleep(1.0)

    def rescan_and_reconnect(self):
        """Pindai ulang seluruh port COM dan sambungkan timbangan fisik yang baru terdeteksi."""
        server_cfg = config_manager.get_server_config()
        enable_startup = server_cfg.get("enable_scale_at_startup", False)
        if not enable_startup:
            return
        for sc in self.scales.values():
            if sc.port == "SIM":
                continue
            if not sc.connected and sc.autoconnect and not sc.manual_stop:
                sc._auto_resolve_port()
                sc.connect()

    def set_enable_scale_at_startup(self, enabled: bool) -> bool:
        """Mengubah setelan nyalakan timbangan di startup dan sinkronkan status port seketika."""
        cfg = config_manager.config
        server_cfg = cfg.setdefault("server", {})
        server_cfg["enable_scale_at_startup"] = bool(enabled)
        config_manager.save(cfg)

        if not enabled:
            # Jika dimatikan, putus koneksi seluruh timbangan fisik agar port serial COM langsung bebas untuk JS
            for sc in self.scales.values():
                if sc.port != "SIM" and sc.connected:
                    sc.disconnect()
                    sc.status_detail = "Startup nonaktif (port bebas untuk JS / browser)"
            logger.info("[ScaleManager] Opsi startup timbangan dinonaktifkan: Port serial COM dilepas dan dibebaskan untuk browser JS.")
        else:
            # Jika diaktifkan, sambungkan timbangan fisik yang diset autoconnect
            logger.info("[ScaleManager] Opsi startup timbangan diaktifkan: Menyambungkan kembali timbangan autoconnect...")
            for sc in self.scales.values():
                if sc.port != "SIM" and sc.autoconnect and not sc.connected and not sc.manual_stop:
                    sc._auto_resolve_port()
                    sc.connect()
        return True

    def list_serial_ports(self) -> List[Dict[str, Any]]:
        results = []
        try:
            ports = serial.tools.list_ports.comports()
            for p in ports:
                results.append({
                    "device": p.device,
                    "description": p.description,
                    "hwid": p.hwid,
                    "manufacturer": p.manufacturer or "",
                    "serial_number": p.serial_number or "",
                    "vid": f"{p.vid:04X}" if p.vid else "",
                    "pid": f"{p.pid:04X}" if p.pid else ""
                })
        except Exception as e:
            logger.error(f"[ScaleManager] Gagal mendeteksi comports: {e}")

        results.append({
            "device": "SIM",
            "description": "Virtual Scale Simulator",
            "hwid": "VIRTUAL_SIM",
            "manufacturer": "HardwareBridge",
            "serial_number": "SIM-001",
            "vid": "0000",
            "pid": "0000"
        })
        return results

    def get_scale(self, name: Optional[str] = None) -> Optional[ScaleInstance]:
        if not self.scales:
            return None
        if name:
            name_clean = str(name).strip()
            # 1. Pencocokan tepat (Exact match)
            if name_clean in self.scales:
                return self.scales[name_clean]
            # 2. Pencocokan case-insensitive
            for k, sc in self.scales.items():
                if k.lower() == name_clean.lower():
                    return sc
            # 3. Pencocokan nama port (misal "COM5" atau "/dev/ttyUSB0")
            for sc in self.scales.values():
                if sc.port and sc.port.lower() == name_clean.lower():
                    return sc
            # 4. Pencocokan substring nama (misal "mettler", "shinko", atau "meja 1")
            for k, sc in self.scales.items():
                if name_clean.lower() in k.lower():
                    return sc

        # Fallback default: Timbangan fisik pertama yang terhubung, lalu simulator, lalu timbangan terdaftar pertama
        for sc in self.scales.values():
            if sc.connected and sc.port != "SIM":
                return sc
        for sc in self.scales.values():
            if sc.connected:
                return sc
        return next(iter(self.scales.values()))

    def get_all_status(self) -> List[Dict[str, Any]]:
        return [sc.get_data() for sc in self.scales.values()]

scale_manager = ScaleManager()
