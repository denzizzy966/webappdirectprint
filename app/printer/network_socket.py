import logging
import socket
from typing import Optional

from .base import PrintJobResult

logger = logging.getLogger("network_socket")

def print_network_raw(host: str, port: int, data: bytes, timeout: float = 5.0) -> PrintJobResult:
    """Mengirim data RAW langsung ke printer jaringan melalui TCP port 9100 (JetDirect)."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.sendall(data)
        logger.info(f"[NetworkPrint] Berhasil mengirim {len(data)} bytes ke {host}:{port}")
        return PrintJobResult(
            success=True,
            printer=f"{host}:{port}",
            message=f"Berhasil dikirim ke printer jaringan {host}:{port}",
            bytes_sent=len(data)
        )
    except Exception as e:
        err = f"Gagal terhubung ke printer jaringan {host}:{port}: {e}"
        logger.error(f"[NetworkPrint] {err}")
        return PrintJobResult(success=False, printer=f"{host}:{port}", error=err)
