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

        # Cek apakah target adalah printer jaringan
        net_p = self._find_network_printer(target_printer)
        if net_p:
            res = print_network_raw(net_p["ip"], int(net_p.get("port", 9100)), raw_bytes)
            self._record_job("RAW (Network)", target_printer, res)
            return res

        if not self.backend:
            res = PrintJobResult(success=False, printer=target_printer, error="Backend printer tidak aktif.")
            self._record_job("RAW", target_printer, res)
            return res

        res = self.backend.print_raw(target_printer, raw_bytes, doc_name=doc_name)
        self._record_job("RAW", target_printer, res)
        return res

    def print_pdf(self, printer_name: Optional[str], pdf_data: Any, doc_name: str = "HardwareBridge_PDF", options: Optional[Dict[str, Any]] = None) -> PrintJobResult:
        """
        Mencetak PDF secara silent.
        `pdf_data` bisa berupa bytes, base64 string, atau URL berkas PDF.
        """
        raw_bytes: bytes
        if isinstance(pdf_data, bytes):
            raw_bytes = pdf_data
        elif isinstance(pdf_data, str):
            if pdf_data.startswith("http://") or pdf_data.startswith("https://"):
                try:
                    resp = requests.get(pdf_data, timeout=15)
                    resp.raise_for_status()
                    raw_bytes = resp.content
                except Exception as e:
                    res = PrintJobResult(success=False, printer=str(printer_name), error=f"Gagal mengunduh PDF dari URL: {e}")
                    self._record_job("PDF", str(printer_name), res)
                    return res
            elif ";base64," in pdf_data:
                raw_bytes = base64.b64decode(pdf_data.split(";base64,")[1])
            elif pdf_data.startswith("base64:"):
                raw_bytes = base64.b64decode(pdf_data[7:])
            else:
                try:
                    raw_bytes = base64.b64decode(pdf_data, validate=True)
                except Exception:
                    # Mungkin path berkas lokal
                    try:
                        with open(pdf_data, "rb") as f:
                            raw_bytes = f.read()
                    except Exception as e:
                        res = PrintJobResult(success=False, printer=str(printer_name), error=f"Gagal membaca berkas PDF: {e}")
                        self._record_job("PDF", str(printer_name), res)
                        return res
        else:
            res = PrintJobResult(success=False, printer=str(printer_name), error="Format data PDF tidak valid.")
            self._record_job("PDF", str(printer_name), res)
            return res

        target_printer = self.resolve_printer(printer_name, job_type="pdf")
        if not self.backend:
            res = PrintJobResult(success=False, printer=target_printer, error="Backend printer tidak aktif.")
            self._record_job("PDF", target_printer, res)
            return res

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
