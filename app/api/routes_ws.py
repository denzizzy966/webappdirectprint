import asyncio
import json
import logging
from typing import Set, Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..printer import printer_manager
from ..serial_scale import scale_manager

logger = logging.getLogger("routes_ws")
router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"[WebSocket] Client terhubung. Total client: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"[WebSocket] Client terputus. Total client: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        msg_str = json.dumps(message)
        for conn in list(self.active_connections):
            try:
                await conn.send_text(msg_str)
            except Exception:
                self.disconnect(conn)

ws_manager = ConnectionManager()

@router.websocket("/ws")
@router.websocket("/")
@router.websocket("/printer")
@router.websocket("/serial/DISPLAY")
@router.websocket("/serial/WEIGH")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket Endpoint kompatibel dengan protokol webapp-hardware-bridge (imTigger).
    Mendukung rute /printer dan /serial yang digunakan oleh whb_print.js di ERPNext.
    """
    await ws_manager.connect(websocket)
    sub_task = None

    # Background task untuk streaming pembacaan timbangan jika klien berlangganan
    scale_subscribers = False

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                req = json.loads(raw_text)
            except Exception:
                await websocket.send_text(json.dumps({"status": "error", "message": "Format pesan harus JSON valid"}))
                continue

            # ────────────────────────────────────────────────────────────
            # 0. Dukungan Format Langsung whb_print.js di ERPNext (Asset Label PDF)
            # ────────────────────────────────────────────────────────────
            if "file_content" in req or req.get("type") in ("asset_label", "pdf"):
                base64_data = req.get("file_content") or req.get("data")
                qty = max(1, int(req.get("qty", 1)))
                doc_name = req.get("url") or req.get("docName") or "Asset_Label"
                target = req.get("printer") or req.get("target") or req.get("pool") or req.get("type") or "asset_label"
                res = None
                for _ in range(qty):
                    res = printer_manager.print_pdf(target, base64_data, doc_name=doc_name)
                
                resp = {
                    "status": "success" if res and res.success else "error",
                    "printer": res.printer if res else str(target),
                    "message": (res.message if res else "Print terkirim") if (res and res.success) else (res.error if res else "Gagal"),
                    "qty": qty
                }
                await websocket.send_text(json.dumps(resp))
                continue

            action = req.get("action", "")
            response: Dict[str, Any] = {"action": action}

            # ────────────────────────────────────────────────────────────
            # 1. Printer Actions
            # ────────────────────────────────────────────────────────────
            if action == "getPrinters":
                printers = printer_manager.list_printers()
                default_p = printer_manager.get_default_printer()
                pools = printer_manager.get_pools()
                response.update({
                    "status": "success",
                    "defaultPrinter": default_p,
                    "pools": pools,
                    "printers": [p.name for p in printers],
                    "details": [p.to_dict() for p in printers]
                })

            elif action == "print":
                printer_name = req.get("printer") or req.get("target") or req.get("pool")
                print_type = req.get("type", "raw").lower()
                data = req.get("data", "")
                doc_name = req.get("docName", "WS_PrintJob")

                if print_type == "raw":
                    res = printer_manager.print_raw(printer_name, data, doc_name=doc_name)
                elif print_type == "pdf":
                    res = printer_manager.print_pdf(printer_name, data, doc_name=doc_name)
                elif print_type == "image":
                    res = printer_manager.print_image(printer_name, data, doc_name=doc_name)
                else:
                    res = printer_manager.print_raw(printer_name, data, doc_name=doc_name)

                response.update({
                    "status": "success" if res.success else "error",
                    "printer": res.printer,
                    "message": res.message or res.error,
                    "bytes": res.bytes_sent
                })

            elif action == "openCashDrawer":
                printer_name = req.get("printer") or req.get("target") or req.get("pool")
                pin = int(req.get("pin", 2))
                res = printer_manager.open_cash_drawer(printer_name, pin=pin)
                response.update({
                    "status": "success" if res.success else "error",
                    "message": res.message or res.error
                })

            # ────────────────────────────────────────────────────────────
            # 2. Scale & Serial Actions
            # ────────────────────────────────────────────────────────────
            elif action == "getSerialPorts":
                ports = scale_manager.list_serial_ports()
                response.update({
                    "status": "success",
                    "ports": ports
                })

            elif action == "getWeight":
                scale_name = req.get("scale")
                instance = scale_manager.get_scale(scale_name)
                if instance:
                    data = instance.get_data()
                    response.update({
                        "status": "success",
                        "scale": instance.name,
                        "weight": data["weight"],
                        "unit": data["unit"],
                        "stable": data["stable"],
                        "data": data
                    })
                else:
                    response.update({"status": "error", "message": "Timbangan tidak ditemukan"})

            elif action == "zero":
                scale_name = req.get("scale")
                instance = scale_manager.get_scale(scale_name)
                if instance and instance.zero():
                    response.update({"status": "success", "message": "Perintah Zero dikirim"})
                else:
                    response.update({"status": "error", "message": "Gagal mengirim Zero"})

            elif action == "tare":
                scale_name = req.get("scale")
                instance = scale_manager.get_scale(scale_name)
                if instance and instance.tare():
                    response.update({"status": "success", "message": "Perintah Tare dikirim"})
                else:
                    response.update({"status": "error", "message": "Gagal mengirim Tare"})

            elif action == "subscribeScale":
                # Mengaktifkan stream berkala ke socket ini
                if not scale_subscribers:
                    scale_subscribers = True
                    async def stream_worker():
                        while scale_subscribers:
                            try:
                                status_data = scale_manager.get_all_status()
                                await websocket.send_text(json.dumps({
                                    "action": "scale_update",
                                    "scales": status_data
                                }))
                                await asyncio.sleep(0.3)
                            except Exception:
                                break
                    sub_task = asyncio.create_task(stream_worker())
                response.update({"status": "success", "message": "Berlangganan update timbangan aktif"})

            elif action == "unsubscribeScale":
                scale_subscribers = False
                if sub_task:
                    sub_task.cancel()
                response.update({"status": "success", "message": "Berlangganan dihentikan"})

            elif action == "ping":
                response.update({"status": "success", "message": "pong"})

            else:
                response.update({"status": "error", "message": f"Action '{action}' tidak dikenali"})

            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"[WebSocket] Error: {e}")
    finally:
        scale_subscribers = False
        if sub_task:
            sub_task.cancel()
        ws_manager.disconnect(websocket)
