import glob
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import List, Optional, Dict, Any

from .base import PrinterBackend, PrinterInfo, PrintJobResult

logger = logging.getLogger("cups_linux")

class CupsLinuxPrinterBackend(PrinterBackend):
    """Implementasi printer backend untuk Linux (Linux Mint 22, Ubuntu 22) menggunakan CUPS & CLI lp/lpr."""

    def __init__(self):
        self.lp_bin = shutil.which("lp")
        self.lpstat_bin = shutil.which("lpstat")

    def list_printers(self) -> List[PrinterInfo]:
        results: List[PrinterInfo] = []
        default_name = self.get_default_printer()

        # 1. Cek dari CUPS lpstat
        if self.lpstat_bin:
            try:
                out = subprocess.check_output([self.lpstat_bin, "-p"], text=True, stderr=subprocess.DEVNULL)
                for line in out.splitlines():
                    # Format: printer <name> is idle.  enabled since ...
                    m = re.match(r"^printer\s+([^\s]+)", line.strip())
                    if m:
                        p_name = m.group(1)
                        results.append(PrinterInfo(
                            name=p_name,
                            is_default=(p_name == default_name),
                            status="Ready" if "idle" in line else "Busy",
                            driver="CUPS Driver",
                            port="CUPS",
                            is_network=False
                        ))
            except Exception as e:
                logger.warning(f"[CupsLinux] Gagal membaca lpstat: {e}")

        # 2. Cek perangkat fisik direct USB printer (/dev/usb/lp*)
        usb_printers = glob.glob("/dev/usb/lp*")
        for dev in usb_printers:
            results.append(PrinterInfo(
                name=dev,
                is_default=False,
                status="Direct Device",
                driver="USB Character Device",
                port=dev,
                is_network=False
            ))

        return results

    def get_default_printer(self) -> Optional[str]:
        if not self.lpstat_bin:
            return None
        try:
            out = subprocess.check_output([self.lpstat_bin, "-d"], text=True, stderr=subprocess.DEVNULL)
            # Format: system default destination: <name>
            m = re.search(r"system default destination:\s*([^\s]+)", out)
            if m:
                return m.group(1)
        except Exception:
            pass
        return None

    def print_raw(self, printer_name: str, data: bytes, doc_name: str = "HardwareBridge_Raw") -> PrintJobResult:
        if not printer_name:
            printer_name = self.get_default_printer() or ""
        if not printer_name:
            return PrintJobResult(success=False, printer="", error="Nama printer tidak ditentukan.")

        # Jika printer adalah direct device path seperti /dev/usb/lp0
        if printer_name.startswith("/dev/"):
            try:
                with open(printer_name, "wb") as f:
                    f.write(data)
                return PrintJobResult(
                    success=True,
                    printer=printer_name,
                    message=f"RAW terkirim langsung ke {printer_name}",
                    bytes_sent=len(data)
                )
            except Exception as e:
                return PrintJobResult(success=False, printer=printer_name, error=f"Gagal menulis ke {printer_name}: {e}")

        # Via CUPS lp -o raw
        if not self.lp_bin:
            return PrintJobResult(success=False, printer=printer_name, error="Perintah 'lp' tidak ditemukan di Linux. Pastikan CUPS terpasang.")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".raw") as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            cmd = [self.lp_bin, "-d", printer_name, "-o", "raw", "-t", doc_name, tmp_path]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode == 0:
                m = re.search(r"request id is ([^\s]+)", proc.stdout)
                job_id = m.group(1) if m else None
                return PrintJobResult(
                    success=True,
                    printer=printer_name,
                    job_id=job_id,
                    message=f"RAW berhasil dikirim ke CUPS ({len(data)} bytes)",
                    bytes_sent=len(data)
                )
            else:
                return PrintJobResult(success=False, printer=printer_name, error=proc.stderr.strip() or "CUPS lp error")
        except Exception as e:
            return PrintJobResult(success=False, printer=printer_name, error=str(e))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def print_pdf(self, printer_name: str, pdf_data: bytes, doc_name: str = "HardwareBridge_PDF", options: Optional[Dict[str, Any]] = None) -> PrintJobResult:
        """Mencetak PDF via filter CUPS bawaan Linux (otomatis tanpa dialog cetak)."""
        if not printer_name:
            printer_name = self.get_default_printer() or ""
        if not printer_name:
            return PrintJobResult(success=False, printer="", error="Nama printer tidak ditentukan.")

        if not self.lp_bin:
            return PrintJobResult(success=False, printer=printer_name, error="Perintah 'lp' tidak ditemukan di Linux.")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_data)
                tmp_path = tmp.name

            cmd = [self.lp_bin, "-d", printer_name, "-t", doc_name, tmp_path]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode == 0:
                m = re.search(r"request id is ([^\s]+)", proc.stdout)
                job_id = m.group(1) if m else None
                return PrintJobResult(
                    success=True,
                    printer=printer_name,
                    job_id=job_id,
                    message=f"PDF berhasil dikirim ke antrean CUPS ({len(pdf_data)} bytes)",
                    bytes_sent=len(pdf_data)
                )
            else:
                return PrintJobResult(success=False, printer=printer_name, error=proc.stderr.strip() or "CUPS lp error")
        except Exception as e:
            return PrintJobResult(success=False, printer=printer_name, error=str(e))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def print_image(self, printer_name: str, image_data: bytes, doc_name: str = "HardwareBridge_Image", options: Optional[Dict[str, Any]] = None) -> PrintJobResult:
        """Mencetak gambar via CUPS di Linux."""
        if not printer_name:
            printer_name = self.get_default_printer() or ""
        if not printer_name:
            return PrintJobResult(success=False, printer="", error="Nama printer tidak ditentukan.")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(image_data)
                tmp_path = tmp.name

            cmd = [self.lp_bin, "-d", printer_name, "-t", doc_name, tmp_path]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode == 0:
                return PrintJobResult(
                    success=True,
                    printer=printer_name,
                    message=f"Gambar berhasil dikirim ke CUPS ({len(image_data)} bytes)",
                    bytes_sent=len(image_data)
                )
            else:
                return PrintJobResult(success=False, printer=printer_name, error=proc.stderr.strip())
        except Exception as e:
            return PrintJobResult(success=False, printer=printer_name, error=str(e))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
