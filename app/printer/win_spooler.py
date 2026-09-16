import io
import logging
import os
import sys
import tempfile
from typing import List, Optional, Dict, Any

from .base import PrinterBackend, PrinterInfo, PrintJobResult

logger = logging.getLogger("win_spooler")

class WinSpoolerPrinterBackend(PrinterBackend):
    """Implementasi printer backend untuk Windows 10/11 menggunakan Win32 Spooler API."""

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("WinSpoolerPrinterBackend hanya dapat dijalankan di Windows")
        import win32print
        import win32ui
        import win32con
        self.win32print = win32print
        self.win32ui = win32ui
        self.win32con = win32con

    def list_printers(self) -> List[PrinterInfo]:
        results: List[PrinterInfo] = []
        try:
            default_name = self.get_default_printer()
            flags = self.win32print.PRINTER_ENUM_LOCAL | self.win32print.PRINTER_ENUM_CONNECTIONS
            printers = self.win32print.EnumPrinters(flags)

            for p in printers:
                # p format: (flags, description, name, comment)
                p_name = p[2]
                is_def = (p_name == default_name)
                
                # Coba ambil detail port & driver
                port_str = ""
                driver_str = ""
                try:
                    hPrinter = self.win32print.OpenPrinter(p_name)
                    try:
                        p_info2 = self.win32print.GetPrinter(hPrinter, 2)
                        port_str = p_info2.get("pPortName", "")
                        driver_str = p_info2.get("pDriverName", "")
                    finally:
                        self.win32print.ClosePrinter(hPrinter)
                except Exception:
                    pass

                results.append(PrinterInfo(
                    name=p_name,
                    is_default=is_def,
                    status="Ready",
                    driver=driver_str,
                    port=port_str,
                    is_network=False
                ))
        except Exception as e:
            logger.error(f"[WinSpooler] Gagal list printers: {e}")
        return results

    def get_default_printer(self) -> Optional[str]:
        try:
            return self.win32print.GetDefaultPrinter()
        except Exception as e:
            logger.warning(f"[WinSpooler] Gagal membaca default printer: {e}")
            return None

    def print_raw(self, printer_name: str, data: bytes, doc_name: str = "HardwareBridge_Raw") -> PrintJobResult:
        if not printer_name:
            printer_name = self.get_default_printer() or ""
        if not printer_name:
            return PrintJobResult(success=False, printer="", error="Tidak ada printer yang dipilih atau default printer tidak ditemukan.")

        hPrinter = None
        try:
            hPrinter = self.win32print.OpenPrinter(printer_name)
            job_id = self.win32print.StartDocPrinter(hPrinter, 1, (doc_name, None, "RAW"))
            try:
                self.win32print.StartPagePrinter(hPrinter)
                self.win32print.WritePrinter(hPrinter, data)
                self.win32print.EndPagePrinter(hPrinter)
            finally:
                self.win32print.EndDocPrinter(hPrinter)

            logger.info(f"[WinSpooler] RAW print berhasil ke '{printer_name}' ({len(data)} bytes, JobID: {job_id})")
            return PrintJobResult(
                success=True,
                printer=printer_name,
                job_id=str(job_id),
                message=f"Berhasil dicetak ({len(data)} bytes)",
                bytes_sent=len(data)
            )
        except Exception as e:
            err_msg = f"Gagal mencetak RAW ke '{printer_name}': {e}"
            logger.error(f"[WinSpooler] {err_msg}")
            return PrintJobResult(success=False, printer=printer_name, error=err_msg)
        finally:
            if hPrinter:
                try:
                    self.win32print.ClosePrinter(hPrinter)
                except Exception:
                    pass

    def print_pdf(self, printer_name: str, pdf_data: bytes, doc_name: str = "HardwareBridge_PDF", options: Optional[Dict[str, Any]] = None) -> PrintJobResult:
        """Mencetak PDF ke printer Windows tanpa dialog cetak menggunakan PyMuPDF + Win32 GDI."""
        if not printer_name:
            printer_name = self.get_default_printer() or ""
        if not printer_name:
            return PrintJobResult(success=False, printer="", error="Nama printer tidak ditentukan.")

        options = options or {}
        dpi = int(options.get("dpi", 300))

        try:
            import fitz  # PyMuPDF
            from PIL import Image, ImageWin

            doc = fitz.open(stream=pdf_data, filetype="pdf")
            total_pages = len(doc)
            if total_pages == 0:
                return PrintJobResult(success=False, printer=printer_name, error="Dokumen PDF kosong.")

            hDC = self.win32ui.CreateDC()
            hDC.CreatePrinterDC(printer_name)
            hDC.StartDoc(doc_name)

            printable_w = hDC.GetDeviceCaps(self.win32con.HORZRES)
            printable_h = hDC.GetDeviceCaps(self.win32con.VERTRES)

            for page_idx in range(total_pages):
                page = doc.load_page(page_idx)
                pix = page.get_pixmap(dpi=dpi)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # Menghitung skala agar proporsional di area cetak printer
                img_w, img_h = img.size
                ratio = min(printable_w / img_w, printable_h / img_h)
                dest_w = int(img_w * ratio)
                dest_h = int(img_h * ratio)

                # Rata tengah horizontal
                dest_x = (printable_w - dest_w) // 2
                dest_y = 0

                hDC.StartPage()
                dib = ImageWin.Dib(img)
                dib.draw(hDC.GetHandleOutput(), (dest_x, dest_y, dest_x + dest_w, dest_y + dest_h))
                hDC.EndPage()

            hDC.EndDoc()
            del hDC

            logger.info(f"[WinSpooler] PDF print berhasil ke '{printer_name}' ({total_pages} halaman)")
            return PrintJobResult(
                success=True,
                printer=printer_name,
                message=f"PDF berhasil dicetak ({total_pages} halaman)",
                bytes_sent=len(pdf_data)
            )

        except Exception as e:
            err_msg = f"Gagal mencetak PDF ke '{printer_name}': {e}"
            logger.error(f"[WinSpooler] {err_msg}")
            return PrintJobResult(success=False, printer=printer_name, error=err_msg)

    def print_image(self, printer_name: str, image_data: bytes, doc_name: str = "HardwareBridge_Image", options: Optional[Dict[str, Any]] = None) -> PrintJobResult:
        """Mencetak gambar (PNG, JPG, BMP) ke printer Windows."""
        if not printer_name:
            printer_name = self.get_default_printer() or ""
        if not printer_name:
            return PrintJobResult(success=False, printer="", error="Nama printer tidak ditentukan.")

        try:
            from PIL import Image, ImageWin
            img = Image.open(io.BytesIO(image_data))
            if img.mode != "RGB":
                img = img.convert("RGB")

            hDC = self.win32ui.CreateDC()
            hDC.CreatePrinterDC(printer_name)
            hDC.StartDoc(doc_name)

            printable_w = hDC.GetDeviceCaps(self.win32con.HORZRES)
            printable_h = hDC.GetDeviceCaps(self.win32con.VERTRES)

            img_w, img_h = img.size
            ratio = min(printable_w / img_w, printable_h / img_h)
            dest_w = int(img_w * ratio)
            dest_h = int(img_h * ratio)
            dest_x = (printable_w - dest_w) // 2
            dest_y = 0

            hDC.StartPage()
            dib = ImageWin.Dib(img)
            dib.draw(hDC.GetHandleOutput(), (dest_x, dest_y, dest_x + dest_w, dest_y + dest_h))
            hDC.EndPage()

            hDC.EndDoc()
            del hDC

            return PrintJobResult(
                success=True,
                printer=printer_name,
                message=f"Gambar berhasil dicetak ({len(image_data)} bytes)",
                bytes_sent=len(image_data)
            )
        except Exception as e:
            err_msg = f"Gagal mencetak gambar ke '{printer_name}': {e}"
            logger.error(f"[WinSpooler] {err_msg}")
            return PrintJobResult(success=False, printer=printer_name, error=err_msg)
