import asyncio
import base64
import json
import logging
import platform
import sys
import time
import io
import zipfile
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, Response
from pydantic import BaseModel, Field

from ..config import config_manager, BASE_DIR
from ..printer import printer_manager
from ..printer.escpos_builder import EscPosBuilder
from ..serial_scale import scale_manager, PROTOCOLS

logger = logging.getLogger("routes_http")
router = APIRouter(prefix="/api")

# ────────────────────────────────────────────────────────────
# Pydantic Request Models
# ────────────────────────────────────────────────────────────

class PrintRawRequest(BaseModel):
    printer: Optional[str] = None
    target: Optional[str] = None
    pool: Optional[str] = None
    data: str = Field(..., description="Data yang akan dicetak (teks langsung, base64:..., atau hex)")
    doc_name: Optional[str] = "DirectPrint_Raw"

# Kunci opsi render yang juga diterima di level atas JSON, demi kompatibilitas
# dengan klien lama (whb_print.js, printService.submit) dan dashboard sandbox.
RENDER_OPTION_KEYS = (
    "mode", "render", "render_mode", "dpi", "qty", "threshold", "dither",
    "darkness", "speed", "rotate", "offset_x", "offset_y",
    "orientation", "fit", "label_width_dots",
    "width_dots", "width_mm", "trim", "cut", "feed",
)


def merge_render_options(req: BaseModel) -> Dict[str, Any]:
    """
    Menggabungkan `options` dengan field render di level atas JSON.

    Field di level atas dipakai hanya bila kunci yang sama belum ada di
    `options`, sehingga `options` tetap menjadi sumber kebenaran.
    """
    opts: Dict[str, Any] = dict(getattr(req, "options", None) or {})
    for key in RENDER_OPTION_KEYS:
        nilai = getattr(req, key, None)
        if nilai is not None and key not in opts:
            opts[key] = nilai
    return opts


class PrintPdfRequest(BaseModel):
    printer: Optional[str] = None
    target: Optional[str] = None
    pool: Optional[str] = None
    pdf_data: Optional[str] = Field(None, description="Data PDF dalam format base64, URL (http://...), atau path berkas")
    file_content: Optional[str] = Field(None, description="Alias pdf_data (kompatibel whb_print.js / printService.submit)")
    url: Optional[str] = Field(None, description="Alias doc_name / sumber PDF (kompatibel whb_print.js)")
    doc_name: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    # Opsi render yang boleh dikirim di level atas
    mode: Optional[str] = Field(None, description="auto (bawaan) | driver | zpl | escpos")
    render: Optional[str] = None
    render_mode: Optional[str] = None
    dpi: Optional[int] = None
    qty: Optional[int] = None
    threshold: Optional[int] = None
    dither: Optional[bool] = None
    darkness: Optional[int] = None
    speed: Optional[int] = None
    rotate: Optional[str] = None
    offset_x: Optional[int] = None
    offset_y: Optional[int] = None
    orientation: Optional[str] = None
    fit: Optional[str] = None
    label_width_dots: Optional[int] = None
    # Opsi khusus jalur ESC/POS
    width_dots: Optional[int] = None
    width_mm: Optional[float] = None
    trim: Optional[bool] = None
    cut: Optional[bool] = None
    feed: Optional[int] = None

    def resolve_source(self) -> str:
        """Mengambil sumber PDF dari pdf_data, file_content, atau url."""
        for kandidat in (self.pdf_data, self.file_content):
            if kandidat and kandidat.strip():
                return kandidat
        if self.url and self.url.strip().lower().startswith(("http://", "https://")):
            return self.url
        return ""

class PrintImageRequest(BaseModel):
    printer: Optional[str] = None
    target: Optional[str] = None
    pool: Optional[str] = None
    image_data: str = Field(..., description="Data gambar (base64 string)")
    doc_name: Optional[str] = "DirectPrint_Image"
    options: Optional[Dict[str, Any]] = None
    mode: Optional[str] = None
    render: Optional[str] = None
    render_mode: Optional[str] = None
    dpi: Optional[int] = None
    qty: Optional[int] = None
    threshold: Optional[int] = None
    dither: Optional[bool] = None
    darkness: Optional[int] = None
    speed: Optional[int] = None
    rotate: Optional[str] = None
    offset_x: Optional[int] = None
    offset_y: Optional[int] = None
    label_width_dots: Optional[int] = None
    width_dots: Optional[int] = None
    width_mm: Optional[float] = None
    trim: Optional[bool] = None
    cut: Optional[bool] = None
    feed: Optional[int] = None

class CashDrawerRequest(BaseModel):
    printer: Optional[str] = None
    target: Optional[str] = None
    pool: Optional[str] = None
    pin: Optional[int] = 2

class PrinterPoolsUpdateRequest(BaseModel):
    pools: Dict[str, str]
    default_raw_printer: Optional[str] = None
    default_doc_printer: Optional[str] = None

class ScaleCommandRequest(BaseModel):
    scale: Optional[str] = None
    port: Optional[str] = None
    command: str

class ScaleYieldRequest(BaseModel):
    scale: Optional[str] = None
    seconds: int = 30

class ScaleStartupConfigRequest(BaseModel):
    enable_scale_at_startup: bool

class StableReadRequest(BaseModel):
    scale: Optional[str] = None
    timeout: Optional[float] = 10.0

class ScaleConnectRequest(BaseModel):
    name: Optional[str] = None
    port: str
    protocol: Optional[str] = "auto"
    baud: Optional[int] = 9600
    databits: Optional[int] = 8
    parity: Optional[str] = "N"
    stopbits: Optional[int] = 1
    poll_interval: Optional[float] = 0.5
    handshake: Optional[str] = "none"
    mode: Optional[str] = "poll"

class ScaleDisconnectRequest(BaseModel):
    port: Optional[str] = None
    scale: Optional[str] = None

# ────────────────────────────────────────────────────────────
# Printer Endpoints
# ────────────────────────────────────────────────────────────

@router.get("/printers")
def get_printers():
    """Mengambil daftar seluruh printer yang terhubung (OS lokal & Jaringan) beserta pool/label mapping."""
    printers = printer_manager.list_printers()
    default_p = printer_manager.get_default_printer()
    pools = printer_manager.get_pools()
    p_cfg = config_manager.get_printer_config()
    return {
        "status": "success",
        "default": default_p,
        "default_raw": p_cfg.get("default_raw_printer"),
        "default_doc": p_cfg.get("default_doc_printer"),
        "pools": pools,
        "count": len(printers),
        "printers": [p.to_dict() for p in printers]
    }

@router.get("/printers/pools")
def get_printer_pools():
    """Mengambil daftar alias label / pool printer beserta konfigurasi default."""
    p_cfg = config_manager.get_printer_config()
    return {
        "status": "success",
        "pools": printer_manager.get_pools(),
        "default_raw_printer": p_cfg.get("default_raw_printer"),
        "default_doc_printer": p_cfg.get("default_doc_printer")
    }

@router.post("/printers/pools")
def update_printer_pools(req: PrinterPoolsUpdateRequest):
    """Menyimpan pemetaan printer pool / target label dan default printer."""
    cfg = config_manager.config
    printers_cfg = cfg.setdefault("printers", {})
    printers_cfg["pools"] = req.pools
    if req.default_raw_printer is not None:
        printers_cfg["default_raw_printer"] = req.default_raw_printer
    if req.default_doc_printer is not None:
        printers_cfg["default_doc_printer"] = req.default_doc_printer

    ok = config_manager.save(cfg)
    if not ok:
        raise HTTPException(status_code=500, detail="Gagal menyimpan konfigurasi printer pool")
    return {
        "status": "success",
        "message": "Konfigurasi printer pool berhasil diperbarui",
        "pools": printers_cfg["pools"],
        "default_raw_printer": printers_cfg.get("default_raw_printer"),
        "default_doc_printer": printers_cfg.get("default_doc_printer")
    }

@router.post("/print/raw")
def print_raw_job(req: PrintRawRequest):
    """Mencetak data mentah (ESC/POS, ZPL, TSPL, Plain Text) tanpa memunculkan dialog cetak."""
    target_p = req.printer or req.target or req.pool
    res = printer_manager.print_raw(target_p, req.data, doc_name=req.doc_name or "HardwareBridge_Raw")
    if not res.success:
        raise HTTPException(status_code=500, detail=res.error or "Gagal mencetak RAW")
    return {"status": "success", "result": res.to_dict()}

@router.post("/print/pdf")
def print_pdf_job(req: PrintPdfRequest):
    """
    Mencetak berkas PDF (Base64 atau URL) langsung ke printer secara silent.

    `options.mode` menentukan cara pencetakan:
      - `auto`   : jalur driver, kecuali printer terdeteksi memakai ZPL (bawaan)
      - `driver` : paksa jalur driver grafis (Windows GDI / CUPS)
      - `zpl`    : paksa konversi PDF menjadi ZPL raster ^GFA lalu kirim RAW
      - `escpos` : paksa konversi PDF menjadi raster ESC/POS GS v 0 lalu kirim
                   RAW. Dipakai printer struk thermal pada /dev/usb/lp* atau
                   antrean RAW yang tidak punya filter peraster PDF.
                   Opsi tambahan: width_dots / width_mm, threshold, dither,
                   trim, cut, feed.
    """
    sumber = req.resolve_source()
    if not sumber:
        raise HTTPException(
            status_code=422,
            detail="Data PDF kosong. Isi salah satu dari: pdf_data, file_content, atau url."
        )

    target_p = req.printer or req.target or req.pool
    doc_name = req.doc_name or req.url or "HardwareBridge_PDF"
    res = printer_manager.print_pdf(
        target_p, sumber, doc_name=doc_name, options=merge_render_options(req)
    )
    if not res.success:
        raise HTTPException(status_code=500, detail=res.error or "Gagal mencetak PDF")
    return {"status": "success", "result": res.to_dict()}

@router.post("/print/pdf-to-zpl")
def convert_pdf_to_zpl(req: PrintPdfRequest):
    """
    Mengubah PDF menjadi perintah ZPL raster (^GFA) TANPA mencetak.

    Berguna untuk pratinjau, penelusuran masalah, atau bila perintah ZPL-nya
    ingin dikirim sendiri lewat jalur RAW yang sudah terbukti jalan.
    """
    from ..printer.pdf_to_zpl import ZplConversionError, pdf_to_zpl

    sumber = req.resolve_source()
    if not sumber:
        raise HTTPException(
            status_code=422,
            detail="Data PDF kosong. Isi salah satu dari: pdf_data, file_content, atau url."
        )

    try:
        pdf_bytes = printer_manager.load_pdf_bytes(sumber)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        zpl = pdf_to_zpl(pdf_bytes, merge_render_options(req))
    except ZplConversionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    teks = zpl.decode("ascii")
    return {
        "status": "success",
        "labels": teks.count("^XA"),
        "pdf_bytes": len(pdf_bytes),
        "zpl_bytes": len(zpl),
        "zpl": teks,
    }

@router.post("/print/image")
def print_image_job(req: PrintImageRequest):
    """Mencetak gambar (Base64) langsung ke printer."""
    target_p = req.printer or req.target or req.pool
    res = printer_manager.print_image(
        target_p, req.image_data, doc_name=req.doc_name or "HardwareBridge_Image",
        options=merge_render_options(req)
    )
    if not res.success:
        raise HTTPException(status_code=500, detail=res.error or "Gagal mencetak gambar")
    return {"status": "success", "result": res.to_dict()}

@router.post("/cashdrawer/open")
def open_cash_drawer(req: CashDrawerRequest):
    """Mengirim sinyal pulsa pembuka laci kasir (Pin 2 atau Pin 5)."""
    target_p = req.printer or req.target or req.pool
    res = printer_manager.open_cash_drawer(target_p, pin=req.pin or 2)
    if not res.success:
        raise HTTPException(status_code=500, detail=res.error or "Gagal membuka laci kasir")
    return {"status": "success", "result": res.to_dict()}

@router.post("/print/test-receipt")
def print_test_receipt(printer: Optional[str] = Query(None)):
    """Mencetak struk belanja contoh pengujian printer thermal POS."""
    sample_bytes = EscPosBuilder.generate_sample_receipt(store_name="DEMO BRIDGE POS")
    res = printer_manager.print_raw(printer, sample_bytes, doc_name="Test_Receipt")
    if not res.success:
        raise HTTPException(status_code=500, detail=res.error or "Gagal mencetak test receipt")
    return {"status": "success", "result": res.to_dict()}

@router.post("/print/test-label")
def print_test_label(printer: Optional[str] = Query(None)):
    """Mencetak label barcode contoh pengujian printer barcode ZPL (Godex / Zebra)."""
    sample_zpl = EscPosBuilder.generate_sample_zpl()
    res = printer_manager.print_raw(printer, sample_zpl, doc_name="Test_Label_ZPL")
    if not res.success:
        raise HTTPException(status_code=500, detail=res.error or "Gagal mencetak test label ZPL")
    return {"status": "success", "result": res.to_dict()}

@router.get("/print/history")
def get_print_history():
    """Mengambil riwayat pencetakan terakhir."""
    return {"status": "success", "history": list(printer_manager.job_history)}

# ────────────────────────────────────────────────────────────
# Scale & Serial Endpoints
# ────────────────────────────────────────────────────────────

@router.get("/scales")
def get_scales(format: Optional[str] = Query(None)):
    """Mengambil daftar seluruh timbangan terdaftar beserta status saat ini."""
    server_cfg = config_manager.get_server_config()
    scale_list = scale_manager.get_all_status()
    if format in ("list", "array"):
        return scale_list
    return {
        "status": "success",
        "enable_scale_at_startup": server_cfg.get("enable_scale_at_startup", False),
        "scales": scale_list
    }

@router.get("/scale-list")
def get_scale_list():
    """Mengambil daftar timbangan langsung berupa array JSON."""
    return scale_manager.get_all_status()

@router.post("/scale/startup-config")
def update_scale_startup_config(req: ScaleStartupConfigRequest):
    """Mengatur apakah timbangan otomatis tersambung saat startup bridge atau tidak."""
    scale_manager.set_enable_scale_at_startup(req.enable_scale_at_startup)
    return {
        "status": "success",
        "enable_scale_at_startup": req.enable_scale_at_startup,
        "message": f"Koneksi timbangan di startup berhasil {'diaktifkan' if req.enable_scale_at_startup else 'dinonaktifkan (port COM bebas untuk Web Serial JS)'}"
    }

@router.get("/weight")
def get_weight(scale: Optional[str] = Query(None), port: Optional[str] = Query(None)):
    """Mengambil berat saat ini dari timbangan (cepat & non-blocking)."""
    target = scale or port
    instance = scale_manager.get_scale(target)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Timbangan '{target}' tidak ditemukan")
    data = instance.get_data()
    return {
        "status": "success",
        "ok": data.get("ok", data.get("connected", False)),
        "name": data.get("name"),
        "port": data.get("port"),
        "weight": data.get("weight"),
        "raw_weight": data.get("raw_weight"),
        "unit": data.get("unit"),
        "stable": data.get("stable"),
        "age": data.get("age", 0.0),
        "data": data
    }

@router.get("/scale/stable-read")
@router.get("/stable-read")
@router.post("/scale/stable-read")
@router.post("/stable-read")
async def get_stable_read(
    scale: Optional[str] = Query(None),
    port: Optional[str] = Query(None),
    timeout: Optional[float] = Query(None),
    body: Optional[StableReadRequest] = None
):
    """Menunggu hingga timbangan menghasilkan data yang STABIL (maksimal timeout detik)."""
    target_scale = scale or port or (body.scale if body else None)
    target_timeout = timeout if timeout is not None else (body.timeout if body and body.timeout is not None else 10.0)

    instance = scale_manager.get_scale(target_scale)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Timbangan '{target_scale}' tidak ditemukan")

    instance.mark_api_activity()
    start_t = time.time()
    while (time.time() - start_t) < target_timeout:
        d = instance.get_data()
        if d.get("connected") and d.get("stable"):
            elapsed = round(time.time() - start_t, 2)
            return {
                "status": "success",
                "ok": True,
                "name": d.get("name"),
                "port": d.get("port"),
                "weight": d.get("weight"),
                "unit": d.get("unit"),
                "stable": True,
                "elapsed": elapsed,
                "elapsed_seconds": elapsed,
                "data": d
            }
        await asyncio.sleep(0.1)

    # Timeout reached
    d = instance.get_data()
    elapsed = round(time.time() - start_t, 2)
    return {
        "status": "timeout",
        "ok": False,
        "name": d.get("name"),
        "port": d.get("port"),
        "weight": d.get("weight"),
        "unit": d.get("unit"),
        "stable": False,
        "elapsed": elapsed,
        "elapsed_seconds": elapsed,
        "error": f"Timbangan '{instance.name}' belum stabil dalam {target_timeout} detik.",
        "message": f"Timbangan '{instance.name}' belum stabil dalam {target_timeout} detik.",
        "data": d
    }

@router.post("/scale/zero")
def scale_zero(scale: Optional[str] = Query(None), port: Optional[str] = Query(None)):
    """Mengirim perintah Zero (Nol) ke timbangan."""
    target = scale or port
    instance = scale_manager.get_scale(target)
    if not instance:
        raise HTTPException(status_code=404, detail="Timbangan tidak ditemukan")
    ok = instance.zero()
    return {"status": "success" if ok else "error", "message": f"Perintah Zero dikirim ke {instance.name} ({instance.port})", "ok": ok}

@router.post("/scale/tare")
def scale_tare(scale: Optional[str] = Query(None), port: Optional[str] = Query(None)):
    """Mengirim perintah Tare ke timbangan."""
    target = scale or port
    instance = scale_manager.get_scale(target)
    if not instance:
        raise HTTPException(status_code=404, detail="Timbangan tidak ditemukan")
    ok = instance.tare()
    return {"status": "success" if ok else "error", "message": f"Perintah Tare dikirim ke {instance.name} ({instance.port})", "ok": ok}

@router.get("/ports")
def get_ports_list():
    """Mengambil daftar port serial lengkap beserta flag connected (kompatibel timbangan-service)."""
    ports = scale_manager.list_serial_ports()
    connected_ports = {sc.port.upper() for sc in scale_manager.scales.values() if sc.connected}
    out = []
    for p in ports:
        dev = p["device"]
        out.append({
            "device": dev,
            "description": p.get("description", ""),
            "connected": dev.upper() in connected_ports
        })
    return out

@router.post("/connect")
@router.post("/scale/connect")
def connect_scale_api(req: ScaleConnectRequest):
    """Menyambungkan timbangan pada port tertentu (atau SIM) dengan konfigurasi protocol/baud."""
    instance = scale_manager.connect_port(
        port=req.port,
        protocol=req.protocol or "auto",
        baud=req.baud or 9600,
        databits=req.databits or 8,
        parity=req.parity or "N",
        stopbits=req.stopbits or 1,
        poll_interval=req.poll_interval or 0.5
    )
    return {
        "ok": instance.connected,
        "status": "success" if instance.connected else "error",
        "name": instance.name,
        "port": instance.port,
        "state": instance.state,
        "detail": instance.status_detail
    }

@router.post("/disconnect")
@router.post("/scale/disconnect")
def disconnect_scale_api(req: Optional[ScaleDisconnectRequest] = None):
    """Memutuskan koneksi timbangan."""
    target_port = req.port if req else None
    target_scale = req.scale if req else None
    instance = None
    if target_scale:
        instance = scale_manager.get_scale(target_scale)
    elif target_port:
        for sc in scale_manager.scales.values():
            if sc.port.lower() == target_port.lower():
                instance = sc
                break
    if not instance:
        instance = scale_manager.get_scale()
    if instance:
        instance.disconnect()
        instance.manual_stop = True
        return {"ok": True, "status": "success", "message": f"Koneksi {instance.name} ({instance.port}) ditutup"}
    return {"ok": False, "status": "error", "message": "Timbangan tidak ditemukan"}

@router.get("/state")
@router.get("/scale/state")
def get_scale_state_api(port: Optional[str] = Query(None), since: Optional[int] = Query(0)):
    """Mengambil status detail, live metrics, dan delta log RX/TX."""
    target = None
    if port:
        for sc in scale_manager.scales.values():
            if sc.port.lower() == port.lower() or (port.upper() == "SIM" and sc.port.upper() == "SIM"):
                target = sc
                break
    if not target:
        target = scale_manager.get_scale()
    if not target:
        return {"ok": False, "connected": False, "log": [], "log_last_id": 0}
    return target.get_state(since=since or 0)

@router.post("/scale/scan-baud")
def scan_baud_api(port: Optional[str] = Query(None)):
    """Pindai baud rate otomatis (9600, 4800, 2400, 1200)."""
    target = scale_manager.get_scale(port)
    if not target or target.sim:
        return {"ok": True, "baud": 9600, "parity": "8N", "message": "Baudrate 9600 OK"}
    # Tes baud rate umum
    bauds_to_test = [9600, 4800, 2400, 1200, 19200]
    for b in bauds_to_test:
        target.connect({"baud": b})
        time.sleep(0.3)
        if target.weight is not None and target.last_update_ts and (time.time() - target.last_update_ts < 2.0):
            return {"ok": True, "baud": b, "message": f"Baudrate ditemukan: {b}"}
    # Kembalikan ke 9600
    target.connect({"baud": 9600})
    return {"ok": False, "message": "Tidak ada respons timbangan pada baudrate umum, dikembalikan ke 9600"}

@router.post("/command")
@router.post("/scale/command")
def scale_custom_command(req: ScaleCommandRequest):
    """Mengirim perintah teks kustom ke timbangan (misal: SI, S, SIR, O9, Z)."""
    instance = None
    if req.scale:
        instance = scale_manager.get_scale(req.scale)
    elif req.port:
        for sc in scale_manager.scales.values():
            if sc.port.lower() == req.port.lower():
                instance = sc
                break
    if not instance:
        instance = scale_manager.get_scale()
    if not instance:
        raise HTTPException(status_code=404, detail="Timbangan tidak ditemukan")
    ok = instance.send_command(req.command)
    return {"status": "success" if ok else "error", "command": req.command, "ok": ok}

@router.post("/scale/pause")
def scale_pause(scale: Optional[str] = Query(None), port: Optional[str] = Query(None), seconds: Optional[int] = Query(None)):
    """Melepas port serial untuk dipakai software lain (misal Delphi)."""
    target = scale or port
    instance = scale_manager.get_scale(target)
    if not instance:
        raise HTTPException(status_code=404, detail="Timbangan tidak ditemukan")
    instance.pause(seconds=seconds)
    return {"status": "success", "message": f"Port {instance.port} dilepas ({instance.state})"}

@router.post("/scale/resume")
def scale_resume(scale: Optional[str] = Query(None), port: Optional[str] = Query(None)):
    """Menyambungkan kembali timbangan yang sebelumnya di-pause."""
    target = scale or port
    instance = scale_manager.get_scale(target)
    if not instance:
        raise HTTPException(status_code=404, detail="Timbangan tidak ditemukan")
    instance.resume()
    scale_manager.rescan_and_reconnect()
    return {
        "status": "success",
        "message": f"Port disambung kembali ({instance.port} - {instance.state})",
        "port": instance.port,
        "state": instance.state,
        "connected": instance.connected
    }

@router.get("/serial/ports")
def get_serial_ports():
    """Mendeteksi daftar port COM / ttyUSB fisik yang terpasang di sistem."""
    ports = scale_manager.list_serial_ports()
    return {"status": "success", "count": len(ports), "ports": ports}

# ────────────────────────────────────────────────────────────
# Real-Time SSE (Server-Sent Events) Stream
# ────────────────────────────────────────────────────────────

@router.get("/stream")
async def event_stream(request: Request):
    """Stream SSE untuk update berat timbangan real-time ke web app / browser."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            payload = {
                "ts": time.time(),
                "scales": scale_manager.get_all_status()
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ────────────────────────────────────────────────────────────
# System Health & Configuration
# ────────────────────────────────────────────────────────────

@router.get("/status")
def get_system_status():
    """Informasi status bridge, sistem operasi, versi, dan konfigurasi."""
    connected_scale_ports = [
        f"{sc.port} ({sc.name})" if sc.name else sc.port
        for sc in scale_manager.scales.values() if sc.connected and sc.port and sc.port.upper() != "SIM"
    ]
    return {
        "status": "online",
        "app": "WebApp Hardware Bridge Universal",
        "version": "2.1.0",
        "os": sys.platform,
        "os_details": platform.platform(),
        "python_version": sys.version,
        "default_printer": printer_manager.get_default_printer(),
        "total_printers": len(printer_manager.list_printers()),
        "total_scales": len(scale_manager.scales),
        "connected_scale_ports": connected_scale_ports,
        "scales": scale_manager.get_all_status()
    }

@router.get("/config")
def get_configuration():
    return config_manager.config

@router.post("/config")
def update_configuration(new_cfg: Dict[str, Any]):
    old_server_cfg = config_manager.get_server_config()
    old_val = old_server_cfg.get("enable_scale_at_startup", False)
    new_server_cfg = new_cfg.get("server", {})
    new_val = new_server_cfg.get("enable_scale_at_startup", old_val)

    ok = config_manager.save(new_cfg)
    if ok and new_val != old_val:
        scale_manager.set_enable_scale_at_startup(new_val)

    return {"status": "success" if ok else "error"}

# ────────────────────────────────────────────────────────────
# SDK & Client Script Download Endpoints
# ────────────────────────────────────────────────────────────

@router.get("/download/hardware-bridge.js")
def download_hardware_bridge_js():
    """Download SDK JavaScript Universal untuk Web Browser & POS."""
    file_path = BASE_DIR / "static" / "js" / "hardware-bridge.js"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File hardware-bridge.js tidak ditemukan")
    return FileResponse(
        path=str(file_path),
        filename="hardware-bridge.js",
        media_type="application/javascript"
    )

@router.get("/download/erpnext-client-script.js")
def download_erpnext_client_script():
    """Download Script ERPNext Client Script (POS & Sales Invoice)."""
    file_path = BASE_DIR / "erpnext" / "erpnext_hardware_bridge.js"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File erpnext_hardware_bridge.js tidak ditemukan")
    return FileResponse(
        path=str(file_path),
        filename="erpnext_hardware_bridge.js",
        media_type="application/javascript"
    )

@router.get("/download/erpnext-pos-script.js")
def download_erpnext_pos_script():
    """Download Script Auto-Print & Drawer untuk POS Awesome / ERPNext POS."""
    file_path = BASE_DIR / "erpnext" / "erpnext_pos_direct_print.js"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File erpnext_pos_direct_print.js tidak ditemukan")
    return FileResponse(
        path=str(file_path),
        filename="erpnext_pos_direct_print.js",
        media_type="application/javascript"
    )

@router.get("/download/all-scripts.zip")
def download_all_scripts_zip():
    """Download paket komplit seluruh SDK, Client Scripts, dan Panduan (.zip)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        js_path = BASE_DIR / "static" / "js" / "hardware-bridge.js"
        if js_path.exists():
            zf.write(js_path, arcname="hardware-bridge.js")
        erp_path = BASE_DIR / "erpnext" / "erpnext_hardware_bridge.js"
        if erp_path.exists():
            zf.write(erp_path, arcname="erpnext_hardware_bridge.js")
        pos_path = BASE_DIR / "erpnext" / "erpnext_pos_direct_print.js"
        if pos_path.exists():
            zf.write(pos_path, arcname="erpnext_pos_direct_print.js")
        # Dokumentasi terpusat di folder docs/ (fallback ke lokasi lama bila belum dipindah)
        doc_files = [
            (BASE_DIR / "docs" / "integrasi" / "erpnext.md", "docs/integrasi/erpnext.md",
             BASE_DIR / "erpnext" / "PANDUAN_ERPNEXT.md"),
            (BASE_DIR / "docs" / "01-arsitektur.md", "docs/01-arsitektur.md",
             BASE_DIR / "ARCHITECTURE_EXPLANATION.md"),
            (BASE_DIR / "docs" / "README.md", "docs/README.md", None),
            (BASE_DIR / "docs" / "05-api-reference.md", "docs/05-api-reference.md", None),
            (BASE_DIR / "docs" / "07-sdk-javascript.md", "docs/07-sdk-javascript.md", None),
        ]
        for primary, arcname, legacy in doc_files:
            src = primary if primary.exists() else legacy
            if src and src.exists():
                zf.write(src, arcname=arcname)

        dp_dir = BASE_DIR / "docs" / "direct-print"
        if dp_dir.is_dir():
            for md in sorted(dp_dir.glob("*.md")):
                zf.write(md, arcname=f"docs/direct-print/{md.name}")
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=hardware-bridge-sdk-all.zip"}
    )

