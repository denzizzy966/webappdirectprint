import base64
import logging
import sys
import time
from collections import deque
from typing import List, Optional, Dict, Any

import requests

from .base import PrinterBackend, PrinterInfo, PrintJobResult
from .escpos_builder import EscPosBuilder
from .network_socket import print_network_raw
from .pdf_to_escpos import (
    EscPosConversionError,
    image_to_escpos,
    lebar_dot as lebar_dot_escpos,
    pdf_to_escpos,
)
from .pdf_to_zpl import ZplConversionError, image_to_zpl, is_zpl_printer, pdf_to_zpl
from ..config import config_manager

logger = logging.getLogger("printer_manager")

class PrinterManager:
    """Manajer printer universal yang mengatur pencetakan lintas platform (Windows & Linux)."""

    def __init__(self):
        self.backend: Optional[PrinterBackend] = None
        self._init_backend()
        self.job_history = deque(maxlen=100)
        self._job_counter = 0

    def _init_backend(self):
        if sys.platform == "win32":
            try:
                from .win_spooler import WinSpoolerPrinterBackend
                self.backend = WinSpoolerPrinterBackend()
                logger.info("[PrinterManager] Menggunakan backend: Windows Spooler")
            except Exception as e:
                logger.error(f"[PrinterManager] Gagal inisialisasi WinSpoolerBackend: {e}")
        else:
            try:
                from .cups_linux import CupsLinuxPrinterBackend
                self.backend = CupsLinuxPrinterBackend()
                logger.info("[PrinterManager] Menggunakan backend: Linux CUPS")
            except Exception as e:
                logger.error(f"[PrinterManager] Gagal inisialisasi CupsLinuxBackend: {e}")

    def list_printers(self) -> List[PrinterInfo]:
        """Mengambil seluruh printer OS lokal ditambah konfigurasi printer jaringan."""
        results: List[PrinterInfo] = []
        if self.backend:
            results.extend(self.backend.list_printers())

        # Tambahkan printer jaringan dari konfigurasi
        p_cfg = config_manager.get_printer_config()
        net_printers = p_cfg.get("network_printers", [])
        for np in net_printers:
            results.append(PrinterInfo(
                name=np.get("name", "Network Printer"),
                is_default=False,
                status="Network (TCP)",
                driver="Raw Socket 9100",
                port=f"{np.get('ip')}:{np.get('port', 9100)}",
                is_network=True,
                ip=np.get("ip"),
                network_port=int(np.get("port", 9100))
            ))

        return results

    def get_pools(self) -> Dict[str, str]:
        """Mengambil kamus pemetaan printer pool / alias label."""
        return config_manager.get_printer_config().get("pools", {})

    def resolve_printer(self, target: Optional[str] = None, job_type: str = "raw") -> str:
        """
        Menerjemahkan nama target / label / pool menjadi nama printer fisik OS yang sebenarnya.
        Contoh:
          - 'receipt'      -> 'EPSON TM-T82'
          - 'asset_label'  -> 'Godex G500 GZPL'
          - 'label'        -> 'Godex G500 GZPL'
          - 'invoice'      -> 'HP LaserJet'
        Jika target kosong atau tidak cocok, fallback ke default printer.
        """
        p_cfg = config_manager.get_printer_config()
        pools = p_cfg.get("pools", {})

        target_clean = (target or "").strip()

        # 1. Cek apakah cocok dengan nama label / pool (case-insensitive)
        if target_clean:
            for pool_key, mapped_printer in pools.items():
                if pool_key.lower() == target_clean.lower() and mapped_printer:
                    return mapped_printer

        # 2. Cek apakah target langsung cocok dengan printer fisik OS terpasang
        installed = self.list_printers()
        installed_names = [p.name for p in installed]
        if target_clean in installed_names:
            return target_clean

        # 3. Cek apakah target cocok dengan printer jaringan (TCP socket)
        if self._find_network_printer(target_clean):
            return target_clean

        # 4. Fuzzy search nama printer fisik yang mengandung teks target
        if target_clean:
            for p_name in installed_names:
                if target_clean.lower() in p_name.lower():
                    return p_name

        # 5. Fallback sesuai job_type
        if job_type in ("pdf", "doc"):
            def_doc = p_cfg.get("default_doc_printer")
            if def_doc:
                return def_doc
            for k in ("invoice", "asset_label", "doc"):
                if pools.get(k):
                    return pools[k]

        def_raw = p_cfg.get("default_raw_printer")
        if def_raw:
            return def_raw
        for k in ("receipt", "label", "raw"):
            if pools.get(k):
                return pools[k]

        # 6. Fallback ke default printer OS
        os_default = self.get_default_printer()
        if os_default:
            return os_default

        # 7. Fallback ke printer fisik pertama
        if installed_names:
            return installed_names[0]

        return target_clean

    def get_default_printer(self) -> Optional[str]:
        # Cek konfigurasi terlebih dahulu
        cfg_def = config_manager.get_printer_config().get("default_raw_printer")
        if cfg_def:
            return cfg_def
        if self.backend:
            return self.backend.get_default_printer()
        return None

    def _find_network_printer(self, printer_name: str) -> Optional[Dict[str, Any]]:
        net_printers = config_manager.get_printer_config().get("network_printers", [])
        for np in net_printers:
            if np.get("name") == printer_name or f"{np.get('ip')}:{np.get('port')}" == printer_name:
                return np
        return None

    def get_printer_info(self, printer_name: str) -> Optional[PrinterInfo]:
        """Mencari metadata printer (driver, port) berdasarkan nama fisiknya."""
        if not printer_name:
            return None
        for p in self.list_printers():
            if p.name == printer_name:
                return p
        low = printer_name.lower()
        for p in self.list_printers():
            if low in p.name.lower():
                return p
        return None

    def printer_uses_zpl(self, printer_name: str) -> bool:
        """Menebak apakah printer tujuan memakai bahasa ZPL (Godex GZPL, Zebra, dsb)."""
        info = self.get_printer_info(printer_name)
        if info:
            return is_zpl_printer(info.name, info.driver, info.port)
        return is_zpl_printer(printer_name)

    @staticmethod
    def _resolve_render_mode(options: Optional[Dict[str, Any]]) -> str:
        """Membaca mode render dari options: auto (bawaan), driver, zpl, atau escpos."""
        opts = options or {}
        mode = opts.get("mode") or opts.get("render") or opts.get("render_mode") or "auto"
        mode = str(mode).strip().lower()
        if mode in ("escpos", "esc/pos", "esc-pos", "thermal", "gsv0"):
            return "escpos"
        if mode in ("zpl", "zpl_raster", "raster", "gfa"):
            return "zpl"
        if mode in ("driver", "gdi", "spooler", "native"):
            return "driver"
        return "auto"

    def load_pdf_bytes(self, pdf_data: Any) -> bytes:
        """
        Membaca sumber PDF menjadi byte mentah.

        Menerima bytes, URL http(s), data URI base64, prefiks `base64:`,
        base64 polos, atau path berkas lokal.

        Melempar ValueError dengan pesan yang siap ditampilkan bila gagal.
        """
        if isinstance(pdf_data, bytes):
            return pdf_data
        if not isinstance(pdf_data, str):
            raise ValueError("Format data PDF tidak valid.")

        if pdf_data.startswith("http://") or pdf_data.startswith("https://"):
            try:
                resp = requests.get(pdf_data, timeout=15)
                resp.raise_for_status()
                return resp.content
            except Exception as e:
                raise ValueError(f"Gagal mengunduh PDF dari URL: {e}") from e

        if ";base64," in pdf_data:
            hasil = self._decode_base64(pdf_data.split(";base64,")[1])
            if hasil is None:
                raise ValueError("Data URI base64 tidak dapat di-decode.")
            return hasil

        if pdf_data.startswith("base64:"):
            hasil = self._decode_base64(pdf_data[7:])
            if hasil is None:
                raise ValueError("String setelah prefiks 'base64:' tidak dapat di-decode.")
            return hasil

        b64_clean = "".join(pdf_data.split())
        decoded = self._decode_base64(b64_clean)
        if decoded is not None and (decoded.startswith(b"%PDF-") or len(b64_clean) > 80):
            return decoded

        try:
            with open(pdf_data.strip(), "rb") as f:
                return f.read()
        except Exception as e:
            raise ValueError(f"Gagal membaca data PDF atau berkas: {e}") from e

    @staticmethod
    def _decode_base64(payload: str) -> Optional[bytes]:
        """Decode base64 dengan pembuangan spasi dan penambalan padding otomatis."""
        try:
            bersih = "".join(payload.split())
            kurang = len(bersih) % 4
            if kurang:
                bersih += "=" * (4 - kurang)
            return base64.b64decode(bersih)
        except Exception:
            return None

    def _record_job(self, job_type: str, printer: str, result: PrintJobResult):
        self._job_counter += 1
        self.job_history.append({
            "id": self._job_counter,
            "type": job_type,
            "printer": printer,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "success": result.success,
            "message": result.message or result.error,
            "bytes": result.bytes_sent
        })

    def print_raw(self, printer_name: Optional[str], data: Any, doc_name: str = "HardwareBridge_Raw") -> PrintJobResult:
        """
        Mencetak data raw (ESC/POS, ZPL, text).
        `data` bisa berupa bytes, str (plain text atau base64 jika berawalan base64:).
        """
        raw_bytes: bytes
        if isinstance(data, bytes):
            raw_bytes = data
        elif isinstance(data, str):
            if data.startswith("data:") and ";base64," in data:
                raw_bytes = base64.b64decode(data.split(";base64,")[1])
            elif data.startswith("base64:"):
                raw_bytes = base64.b64decode(data[7:])
            else:
                # Coba parse apakah base64 valid, jika tidak anggap teks string
                try:
                    # Validasi apakah string adalah base64
                    decoded = base64.b64decode(data, validate=True)
                    # Jika berhasil dan memiliki karakter non-ascii/binary, gunakan decoded
                    raw_bytes = decoded
                except Exception:
                    enc = config_manager.get_printer_config().get("default_encoding", "cp437")
                    raw_bytes = data.encode(enc, errors="replace")
        else:
            res = PrintJobResult(success=False, printer=str(printer_name), error="Format data tidak didukung (harus bytes atau string).")
            self._record_job("RAW", str(printer_name), res)
            return res

        target_printer = self.resolve_printer(printer_name, job_type="raw")
        res, jalur = self._send_raw(target_printer, raw_bytes, doc_name)
        self._record_job("RAW (Network)" if jalur == "network" else "RAW", target_printer, res)
        return res

    def _send_raw(self, target_printer: str, raw_bytes: bytes, doc_name: str):
        """
        Mengirim byte mentah ke printer tanpa mencatat riwayat job.

        Mengembalikan pasangan (PrintJobResult, jalur) dengan jalur bernilai
        "network" atau "spooler". Dipakai bersama oleh print_raw dan jalur
        konversi PDF/gambar ke ZPL.
        """
        net_p = self._find_network_printer(target_printer)
        if net_p:
            res = print_network_raw(net_p["ip"], int(net_p.get("port", 9100)), raw_bytes)
            return res, "network"

        if not self.backend:
            return PrintJobResult(
                success=False, printer=target_printer, error="Backend printer tidak aktif."
            ), "spooler"

        return self.backend.print_raw(target_printer, raw_bytes, doc_name=doc_name), "spooler"

    def print_pdf(self, printer_name: Optional[str], pdf_data: Any, doc_name: str = "HardwareBridge_PDF", options: Optional[Dict[str, Any]] = None) -> PrintJobResult:
        """
        Mencetak PDF secara silent.

        `pdf_data` bisa berupa bytes, base64 string, URL, atau path berkas.

        `options["mode"]` menentukan jalur pencetakan:
          - "auto"   : jalur driver, kecuali printer terdeteksi memakai ZPL (bawaan)
          - "driver" : paksa jalur driver grafis (Windows GDI / CUPS)
          - "zpl"    : paksa konversi PDF menjadi ZPL raster ^GFA lalu kirim RAW
        """
        try:
            raw_bytes = self.load_pdf_bytes(pdf_data)
        except ValueError as e:
            res = PrintJobResult(success=False, printer=str(printer_name), error=str(e))
            self._record_job("PDF", str(printer_name), res)
            return res

        target_printer = self.resolve_printer(printer_name, job_type="pdf")
        options = dict(options or {})
        mode = self._resolve_render_mode(options)
        qty = max(1, int(options.get("qty", 1) or 1))

        # ── Jalur ESC/POS raster: PDF diubah menjadi GS v 0 lalu dikirim RAW ──
        # Dipakai oleh printer struk thermal yang dipasang sebagai perangkat
        # langsung (/dev/usb/lp*) atau antrean RAW, sehingga tidak ada filter
        # CUPS / driver Windows yang bisa meraster PDF untuknya.
        if mode == "escpos":
            try:
                escpos_bytes = pdf_to_escpos(raw_bytes, options)
            except EscPosConversionError as e:
                res = PrintJobResult(
                    success=False, printer=target_printer,
                    error=f"Gagal mengubah PDF menjadi ESC/POS: {e}"
                )
                self._record_job("PDF->ESCPOS", target_printer, res)
                return res

            res, jalur = self._send_raw(target_printer, escpos_bytes, doc_name)
            if res.success:
                res.message = (
                    f"PDF dicetak sebagai raster ESC/POS ({len(escpos_bytes)} byte, "
                    f"lebar {lebar_dot_escpos(options)} dot)"
                )
            self._record_job(
                "PDF->ESCPOS (Network)" if jalur == "network" else "PDF->ESCPOS",
                target_printer, res
            )
            return res

        # ── Jalur ZPL raster: PDF diubah menjadi ^GFA lalu dikirim sebagai RAW ──
        # Dipakai oleh printer label (Godex GZPL, Zebra) yang gagal atau tidak
        # akurat bila dicetak lewat driver grafis Windows.
        pakai_zpl = mode == "zpl" or (mode == "auto" and self.printer_uses_zpl(target_printer))

        if pakai_zpl:
            try:
                zpl_bytes = pdf_to_zpl(raw_bytes, options)
                res, jalur = self._send_raw(target_printer, zpl_bytes, doc_name)
                if res.success:
                    res.message = (
                        f"PDF dicetak sebagai ZPL raster ({len(zpl_bytes)} byte, "
                        f"{options.get('dpi') or 203} dpi)"
                    )
                self._record_job(
                    "PDF->ZPL (Network)" if jalur == "network" else "PDF->ZPL",
                    target_printer, res
                )
                return res
            except ZplConversionError as e:
                if mode == "zpl":
                    res = PrintJobResult(
                        success=False, printer=target_printer,
                        error=f"Gagal mengubah PDF menjadi ZPL: {e}"
                    )
                    self._record_job("PDF->ZPL", target_printer, res)
                    return res
                logger.warning(
                    f"[PrinterManager] Konversi ZPL gagal ({e}), kembali ke jalur driver."
                )

        if not self.backend:
            res = PrintJobResult(success=False, printer=target_printer, error="Backend printer tidak aktif.")
            self._record_job("PDF", target_printer, res)
            return res

        res = self.backend.print_pdf(target_printer, raw_bytes, doc_name=doc_name, options=options)
        for _ in range(qty - 1):
            if not res.success:
                break
            res = self.backend.print_pdf(target_printer, raw_bytes, doc_name=doc_name, options=options)
        self._record_job("PDF", target_printer, res)
        return res

    def print_image(self, printer_name: Optional[str], image_data: Any, doc_name: str = "HardwareBridge_Image", options: Optional[Dict[str, Any]] = None) -> PrintJobResult:
        """Mencetak gambar langsung ke printer."""
        raw_bytes: bytes
        if isinstance(image_data, bytes):
            raw_bytes = image_data
        elif isinstance(image_data, str):
            if ";base64," in image_data:
                raw_bytes = base64.b64decode(image_data.split(";base64,")[1])
            elif image_data.startswith("base64:"):
                raw_bytes = base64.b64decode(image_data[7:])
            else:
                raw_bytes = base64.b64decode(image_data)
        else:
            res = PrintJobResult(success=False, printer=str(printer_name), error="Format data gambar tidak valid.")
            self._record_job("IMAGE", str(printer_name), res)
            return res

        target_printer = self.resolve_printer(printer_name, job_type="doc")
        options = dict(options or {})
        mode = self._resolve_render_mode(options)
        pakai_zpl = mode == "zpl" or (mode == "auto" and self.printer_uses_zpl(target_printer))

        if mode == "escpos":
            try:
                escpos_bytes = image_to_escpos(raw_bytes, options)
            except EscPosConversionError as e:
                res = PrintJobResult(
                    success=False, printer=target_printer,
                    error=f"Gagal mengubah gambar menjadi ESC/POS: {e}"
                )
                self._record_job("IMAGE->ESCPOS", target_printer, res)
                return res

            res, jalur = self._send_raw(target_printer, escpos_bytes, doc_name)
            if res.success:
                res.message = f"Gambar dicetak sebagai raster ESC/POS ({len(escpos_bytes)} byte)"
            self._record_job(
                "IMAGE->ESCPOS (Network)" if jalur == "network" else "IMAGE->ESCPOS",
                target_printer, res
            )
            return res

        if pakai_zpl:
            try:
                zpl_bytes = image_to_zpl(raw_bytes, options)
                res, jalur = self._send_raw(target_printer, zpl_bytes, doc_name)
                if res.success:
                    res.message = f"Gambar dicetak sebagai ZPL raster ({len(zpl_bytes)} byte)"
                self._record_job(
                    "IMAGE->ZPL (Network)" if jalur == "network" else "IMAGE->ZPL",
                    target_printer, res
                )
                return res
            except ZplConversionError as e:
                if mode == "zpl":
                    res = PrintJobResult(
                        success=False, printer=target_printer,
                        error=f"Gagal mengubah gambar menjadi ZPL: {e}"
                    )
                    self._record_job("IMAGE->ZPL", target_printer, res)
                    return res
                logger.warning(
                    f"[PrinterManager] Konversi ZPL gagal ({e}), kembali ke jalur driver."
                )

        if not self.backend:
            res = PrintJobResult(success=False, printer=target_printer, error="Backend printer tidak aktif.")
            self._record_job("IMAGE", target_printer, res)
            return res

        res = self.backend.print_image(target_printer, raw_bytes, doc_name=doc_name, options=options)
        self._record_job("IMAGE", target_printer, res)
        return res

    def open_cash_drawer(self, printer_name: Optional[str] = None, pin: int = 2) -> PrintJobResult:
        """Mengirimkan pulsa pembuka laci kasir (kick cash drawer)."""
        target_printer = self.resolve_printer(printer_name, job_type="raw")
        pulse = EscPosBuilder.DRAWER_KICK if pin == 2 else EscPosBuilder.DRAWER_KICK_PIN5
        res = self.print_raw(target_printer, pulse, doc_name="Drawer_Kick")
        if res.success:
            res.message = f"Pulsa laci kasir (Pin {pin}) berhasil dikirim ke {target_printer}"
        self._record_job("DRAWER", target_printer, res)
        return res

printer_manager = PrinterManager()
