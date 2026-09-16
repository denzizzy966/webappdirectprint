"""
Printer module for Universal Hardware Bridge
Supports RAW (ESC/POS, ZPL, TSPL), PDF, Image, and Cash Drawer
"""

from .base import PrinterInfo, PrintJobResult, PrinterBackend
from .printer_manager import printer_manager

__all__ = ["PrinterInfo", "PrintJobResult", "PrinterBackend", "printer_manager"]
