"""
Konversi PDF / gambar menjadi perintah ZPL II raster (^GFA).

Dipakai untuk printer label yang gagal atau tidak akurat bila dicetak lewat
driver grafis Windows (GDI), misalnya Godex G500 GZPL, Zebra ZDesigner, dan
printer lain yang bekerja dengan andal hanya pada jalur RAW.

Alur: PDF -> raster (PyMuPDF) -> monokrom 1-bit (Pillow) -> ^GFA hex -> RAW.
"""

import logging
import math
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pdf_to_zpl")

# Nama/driver printer yang diketahui memakai bahasa ZPL (dipakai oleh mode "auto")
ZPL_DRIVER_PATTERN = re.compile(
    r"(zpl|gzpl|ezpl|zdesigner|zebra|godex|zt\d{3}|gk\d{3}|gx\d{3})",
    re.IGNORECASE
)

# Batas aman lebar label (dot). 203 dpi x 4 inci = 812 dot.
MAX_LABEL_DOTS = 4096


class ZplConversionError(RuntimeError):
    """Gagal mengubah PDF/gambar menjadi ZPL."""


def is_zpl_printer(*candidates: Optional[str]) -> bool:
    """Menebak apakah printer memakai bahasa ZPL berdasarkan nama/driver/port."""
    for c in candidates:
        if c and ZPL_DRIVER_PATTERN.search(c):
            return True
    return False


def _pil_image_to_gfa(img, threshold: int = 128, dither: bool = False) -> Dict[str, Any]:
    """
    Mengubah objek gambar Pillow menjadi potongan data ^GFA.

    Mengembalikan dict berisi `hex`, `total`, `bytes_per_row`, `width`, `height`.
    """
    from PIL import Image

    if img.mode != "L":
        # Ratakan transparansi ke putih agar area kosong tidak menjadi hitam
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            latar = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(latar, img)
        img = img.convert("L")

    if dither:
        bw = img.convert("1")                                  # Floyd-Steinberg
    else:
        t = max(1, min(254, int(threshold)))
        bw = img.point(lambda p: 255 if p > t else 0, mode="1")

    width, height = bw.size
    if width <= 0 or height <= 0:
        raise ZplConversionError("Ukuran gambar hasil render tidak valid (0 piksel).")
    if width > MAX_LABEL_DOTS or height > MAX_LABEL_DOTS:
        raise ZplConversionError(
            f"Ukuran label {width}x{height} dot melebihi batas aman {MAX_LABEL_DOTS} dot. "
            f"Turunkan nilai dpi."
        )

    # Pillow memaketkan mode "1" per baris hingga batas byte; bit 1 = putih.
    # ZPL memakai bit 1 = hitam, sehingga seluruh byte dibalik.
    mentah = bw.tobytes()
    data = bytes((~b) & 0xFF for b in mentah)

    bytes_per_row = (width + 7) // 8
    total = bytes_per_row * height

    if len(data) != total:
        # Jaga-jaga bila versi Pillow memaketkan baris dengan cara berbeda
        raise ZplConversionError(
            f"Ukuran buffer tidak sesuai: {len(data)} byte, diharapkan {total} byte."
        )

    return {
        "hex": data.hex().upper(),
        "total": total,
        "bytes_per_row": bytes_per_row,
        "width": width,
        "height": height,
    }


def _bangun_label(gfa: Dict[str, Any], options: Dict[str, Any]) -> str:
    """Menyusun satu label ZPL lengkap dari potongan ^GFA."""
    qty = max(1, int(options.get("qty", 1) or 1))
    darkness = options.get("darkness")
    speed = options.get("speed")
    rotate = str(options.get("rotate", "N") or "N").upper()[:1]
    offset_x = int(options.get("offset_x", 0) or 0)
    offset_y = int(options.get("offset_y", 0) or 0)

    if rotate not in ("N", "R", "I", "B"):
        rotate = "N"

    baris: List[str] = ["^XA"]

    if darkness is not None:
        baris.append(f"^MD{int(darkness)}")
    if speed is not None:
        baris.append(f"^PR{int(speed)}")

    baris.append(f"^PW{gfa['width']}")
    baris.append(f"^LL{gfa['height']}")
    baris.append("^LH0,0")
    baris.append(f"^PO{rotate}")
    baris.append(f"^FO{offset_x},{offset_y}")
    baris.append(
        f"^GFA,{gfa['total']},{gfa['total']},{gfa['bytes_per_row']},{gfa['hex']}"
    )
    baris.append("^FS")

    if qty > 1:
        baris.append(f"^PQ{qty}")

    baris.append("^XZ")
    return "".join(baris)


def pdf_to_zpl(pdf_bytes: bytes, options: Optional[Dict[str, Any]] = None) -> bytes:
    """
    Mengubah berkas PDF menjadi perintah ZPL raster.

    Setiap halaman PDF menjadi satu label terpisah.

    Opsi yang dikenali:
        dpi        int   resolusi printer, bawaan 203
        threshold  int   ambang hitam-putih 1..254, bawaan 128
        dither     bool  pakai dithering Floyd-Steinberg, bawaan False
        qty        int   jumlah cetak per label (^PQ), bawaan 1
        darkness   int   kegelapan pemanas (^MD) -30..30
        speed      int   kecepatan cetak (^PR)
        rotate     str   N / R / I / B (^PO), bawaan N
        offset_x   int   geser horizontal dalam dot, bawaan 0
        offset_y   int   geser vertikal dalam dot, bawaan 0
    """
    options = dict(options or {})
    dpi = int(options.get("dpi") or 203)
    if dpi <= 0:
        dpi = 203
    threshold = int(options.get("threshold") or 128)
    dither = bool(options.get("dither", False))

    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise ZplConversionError(
            "PyMuPDF (fitz) tidak tersedia, konversi PDF ke ZPL tidak dapat dilakukan. "
            "Jalankan: pip install pymupdf"
        ) from e

    try:
        from PIL import Image
    except ImportError as e:
        raise ZplConversionError(
            "Pillow tidak tersedia, konversi PDF ke ZPL tidak dapat dilakukan. "
            "Jalankan: pip install pillow"
        ) from e

    # PyMuPDF versi baru ikut mengenali HTML/XPS dan merendernya pada halaman
    # bawaan 400x600 pt. Untuk printer label hasilnya salah ukuran, sehingga
    # data non-PDF ditolak di sini dengan pesan yang bisa ditindaklanjuti.
    kepala = bytes(pdf_bytes[:1024]).lstrip()
    if not kepala.startswith(b"%PDF-"):
        contoh = kepala[:40].decode("ascii", errors="replace")
        if kepala[:1] == b"<":
            raise ZplConversionError(
                "Data yang dikirim adalah HTML, bukan PDF. Render HTML menjadi PDF "
                "terlebih dahulu (dompdf, html2pdf.js, atau jsPDF), baru kirim "
                f"Base64 hasilnya. Awal data: {contoh!r}"
            )
        raise ZplConversionError(
            f"Data yang dikirim bukan berkas PDF (tidak diawali '%PDF-'). "
            f"Awal data: {contoh!r}"
        )

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ZplConversionError(f"Berkas bukan PDF yang valid: {e}") from e

    if len(doc) == 0:
        raise ZplConversionError("Dokumen PDF kosong (0 halaman).")

    potongan: List[str] = []
    try:
        for idx in range(len(doc)):
            halaman = doc.load_page(idx)
            pix = halaman.get_pixmap(dpi=dpi, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            gfa = _pil_image_to_gfa(img, threshold=threshold, dither=dither)
            potongan.append(_bangun_label(gfa, options))
            logger.info(
                "[PdfToZpl] Halaman %d/%d -> %dx%d dot (%d byte raster) @ %d dpi",
                idx + 1, len(doc), gfa["width"], gfa["height"], gfa["total"], dpi
            )
    finally:
        try:
            doc.close()
        except Exception:
            pass

    return "".join(potongan).encode("ascii")


def image_to_zpl(image_bytes: bytes, options: Optional[Dict[str, Any]] = None) -> bytes:
    """Mengubah berkas gambar (PNG/JPG/BMP) menjadi perintah ZPL raster."""
    options = dict(options or {})
    threshold = int(options.get("threshold") or 128)
    dither = bool(options.get("dither", False))

    try:
        import io
        from PIL import Image
    except ImportError as e:
        raise ZplConversionError("Pillow tidak tersedia untuk konversi gambar ke ZPL.") from e

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as e:
        raise ZplConversionError(f"Berkas gambar tidak dapat dibaca: {e}") from e

    # Skala ulang bila lebar label diminta secara eksplisit (dalam dot)
    lebar_target = options.get("label_width_dots")
    if lebar_target:
        lebar_target = int(lebar_target)
        if lebar_target > 0 and img.width != lebar_target:
            tinggi_baru = max(1, int(round(img.height * lebar_target / img.width)))
            img = img.resize((lebar_target, tinggi_baru))

    gfa = _pil_image_to_gfa(img, threshold=threshold, dither=dither)
    return _bangun_label(gfa, options).encode("ascii")


def mm_ke_dot(mm: float, dpi: int = 203) -> int:
    """Konversi milimeter ke dot printer (203 dpi = 8 dot/mm)."""
    return int(math.ceil(mm * dpi / 25.4))
