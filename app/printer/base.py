from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class PrinterInfo:
    name: str
    is_default: bool = False
    status: str = "Ready"
    driver: str = ""
    port: str = ""
    is_network: bool = False
    ip: Optional[str] = None
    network_port: int = 9100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "is_default": self.is_default,
            "status": self.status,
            "driver": self.driver,
            "port": self.port,
            "is_network": self.is_network,
            "ip": self.ip,
            "network_port": self.network_port,
        }

@dataclass
class PrintJobResult:
    success: bool
    printer: str
    job_id: Optional[str] = None
    message: str = ""
    bytes_sent: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "printer": self.printer,
            "job_id": self.job_id,
            "message": self.message,
            "bytes_sent": self.bytes_sent,
            "error": self.error,
        }

class PrinterBackend(ABC):
    @abstractmethod
    def list_printers(self) -> List[PrinterInfo]:
        """Mengembalikan daftar printer yang terdeteksi di OS."""
        pass

    @abstractmethod
    def get_default_printer(self) -> Optional[str]:
        """Mengembalikan nama printer default OS."""
        pass

    @abstractmethod
    def print_raw(self, printer_name: str, data: bytes, doc_name: str = "HardwareBridge_Raw") -> PrintJobResult:
        """Mencetak data raw (ESC/POS, ZPL, TSPL, dll)."""
        pass

    @abstractmethod
    def print_pdf(self, printer_name: str, pdf_data: bytes, doc_name: str = "HardwareBridge_PDF", options: Optional[Dict[str, Any]] = None) -> PrintJobResult:
        """Mencetak dokumen PDF secara silent tanpa memunculkan dialog cetak."""
        pass

    @abstractmethod
    def print_image(self, printer_name: str, image_data: bytes, doc_name: str = "HardwareBridge_Image", options: Optional[Dict[str, Any]] = None) -> PrintJobResult:
        """Mencetak gambar (PNG, JPG, BMP) ke printer."""
        pass
