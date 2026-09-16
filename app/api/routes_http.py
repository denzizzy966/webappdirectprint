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

class PrintPdfRequest(BaseModel):
    printer: Optional[str] = None
    target: Optional[str] = None
    pool: Optional[str] = None
    pdf_data: str = Field(..., description="Data PDF dalam format base64, URL (http://...), atau path berkas")
    doc_name: Optional[str] = "DirectPrint_PDF"
    options: Optional[Dict[str, Any]] = None

class PrintImageRequest(BaseModel):
    printer: Optional[str] = None
    target: Optional[str] = None
    pool: Optional[str] = None
    image_data: str = Field(..., description="Data gambar (base64 string)")
    doc_name: Optional[str] = "DirectPrint_Image"

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
    name: str
    port: str
    protocol: Optional[str] = "mettler"
    baud: Optional[int] = 9600
    databits: Optional[int] = 8
    parity: Optional[str] = "N"
    stopbits: Optional[int] = 1
    poll_interval: Optional[float] = 0.5

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
    """Mencetak berkas PDF (Base64 atau URL) langsung ke printer secara silent."""
    target_p = req.printer or req.target or req.pool
    res = printer_manager.print_pdf(target_p, req.pdf_data, doc_name=req.doc_name or "HardwareBridge_PDF", options=req.options)
    if not res.success:
        raise HTTPException(status_code=500, detail=res.error or "Gagal mencetak PDF")
    return {"status": "success", "result": res.to_dict()}

@router.post("/print/image")
def print_image_job(req: PrintImageRequest):
    """Mencetak gambar (Base64) langsung ke printer."""
    target_p = req.printer or req.target or req.pool
    res = printer_manager.print_image(target_p, req.image_data, doc_name=req.doc_name or "HardwareBridge_Image")
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
def get_weight(scale: Optional[str] = Query(None)):
    """Mengambil berat saat ini dari timbangan (cepat & non-blocking)."""
    instance = scale_manager.get_scale(scale)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Timbangan '{scale}' tidak ditemukan")
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
    timeout: Optional[float] = Query(None),
    body: Optional[StableReadRequest] = None
):
    """Menunggu hingga timbangan menghasilkan data yang STABIL (maksimal timeout detik)."""
    target_scale = scale or (body.scale if body else None)
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
def scale_zero(scale: Optional[str] = Query(None)):
    """Mengirim perintah Zero (Nol) ke timbangan."""
    instance = scale_manager.get_scale(scale)
    if not instance:
        raise HTTPException(status_code=404, detail="Timbangan tidak ditemukan")
    ok = instance.zero()
    return {"status": "success" if ok else "error", "message": "Perintah Zero dikirim"}

@router.post("/scale/tare")
def scale_tare(scale: Optional[str] = Query(None)):
    """Mengirim perintah Tare ke timbangan."""
    instance = scale_manager.get_scale(scale)
    if not instance:
        raise HTTPException(status_code=404, detail="Timbangan tidak ditemukan")
    ok = instance.tare()
    return {"status": "success" if ok else "error", "message": "Perintah Tare dikirim"}

@router.post("/scale/command")
def scale_custom_command(req: ScaleCommandRequest):
    """Mengirim perintah teks kustom ke timbangan (misal: SI, S, SIR, O9, Z)."""
    instance = scale_manager.get_scale(req.scale)
    if not instance:
        raise HTTPException(status_code=404, detail="Timbangan tidak ditemukan")
    ok = instance.send_command(req.command)
    return {"status": "success" if ok else "error", "command": req.command}

@router.post("/scale/pause")
def scale_pause(scale: Optional[str] = Query(None), seconds: Optional[int] = Query(None)):
    """Melepas port serial untuk dipakai software lain (misal Delphi)."""
    instance = scale_manager.get_scale(scale)
    if not instance:
        raise HTTPException(status_code=404, detail="Timbangan tidak ditemukan")
    instance.pause(seconds=seconds)
    return {"status": "success", "message": f"Port dilepas ({instance.state})"}

@router.post("/scale/resume")
def scale_resume(scale: Optional[str] = Query(None)):
    """Menyambungkan kembali timbangan yang sebelumnya di-pause."""
    instance = scale_manager.get_scale(scale)
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
    return {
        "status": "online",
        "app": "WebApp Hardware Bridge Universal",
        "version": "2.1.0",
        "os": sys.platform,
        "os_details": platform.platform(),
        "python_version": sys.version,
        "default_printer": printer_manager.get_default_printer(),
        "total_printers": len(printer_manager.list_printers()),
        "total_scales": len(scale_manager.scales)
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
        guide_path = BASE_DIR / "erpnext" / "PANDUAN_ERPNEXT.md"
        if guide_path.exists():
            zf.write(guide_path, arcname="PANDUAN_ERPNEXT.md")
        arch_path = BASE_DIR / "ARCHITECTURE_EXPLANATION.md"
        if arch_path.exists():
            zf.write(arch_path, arcname="ARCHITECTURE_EXPLANATION.md")
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=hardware-bridge-sdk-all.zip"}
    )

