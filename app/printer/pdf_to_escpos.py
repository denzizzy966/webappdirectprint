"""
Konversi PDF / gambar menjadi perintah raster ESC/POS (GS v 0).

Dipakai untuk printer struk thermal yang dipasang sebagai perangkat langsung
(`/dev/usb/lp0`, `/dev/usb/lp1`) atau antrean RAW, sehingga tidak ada filter
CUPS / driver Windows yang bisa meraster PDF untuknya.

Alur: PDF -> raster (PyMuPDF) -> monokrom 1-bit (Pillow) -> GS v 0 -> RAW.

Berbeda dengan jalur ZPL yang memakai satuan dot bebas, printer ESC/POS punya
lebar cetak tetap. Halaman PDF karena itu selalu diskalakan agar lebarnya pas
dengan lebar kertas, bukan mengikuti dpi.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pdf_to_escpos")

ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"                 # inisialisasi printer
CUT_FEED = GS + b"V\x42\x00"      # potong kertas disertai feed

# Lebar cetak printer thermal umum, dalam dot (203 dpi = 8 dot/mm)
LEBAR_KERTAS_MM = {58: 384, 72: 512, 76: 512, 80: 576}
LEBAR_BAWAAN = 576                # 80 mm
MAX_LEBAR_DOTS = 2048

# Satu perintah GS v 0 dibatasi agar tidak melebihi buffer printer murah
PITA_BARIS = 128


class EscPosConversionError(RuntimeError):
    """Gagal mengubah PDF/gambar menjadi ESC/POS."""


def lebar_dot(options: Optional[Dict[str, Any]] = None) -> int:
    """
    Menentukan lebar cetak dalam dot dari options.

    Urutan yang dibaca: width_dots / paper_width_dots / label_width_dots,
    lalu paper_width_mm / width_mm, terakhir bawaan 576 dot (80 mm).
    Nilai selalu dibulatkan turun ke kelipatan 8 karena satu byte = 8 dot.
    """
    opts = options or {}

    lebar = None
    for kunci in ("width_dots", "paper_width_dots", "label_width_dots"):
        nilai = opts.get(kunci)
        if nilai:
            lebar = int(nilai)
            break

    if lebar is None:
        mm = opts.get("paper_width_mm") or opts.get("width_mm")
        if mm:
            mm_bulat = int(round(float(mm)))
            lebar = LEBAR_KERTAS_MM.get(mm_bulat) or int(round(float(mm) * 8))
        else:
            lebar = LEBAR_BAWAAN

    if lebar <= 0:
        raise EscPosConversionError(f"Lebar cetak tidak valid: {lebar} dot.")
    if lebar > MAX_LEBAR_DOTS:
        raise EscPosConversionError(
            f"Lebar cetak {lebar} dot melebihi batas aman {MAX_LEBAR_DOTS} dot."
        )

    return (lebar // 8) * 8 or 8


def _pil_ke_raster(img, lebar: int, options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mengubah objek gambar Pillow menjadi buffer bit raster ESC/POS.

    Gambar diskalakan agar lebarnya tepat `lebar` dot. Baris kosong di bagian
    bawah dibuang bila `trim` aktif, supaya kertas tidak terbuang percuma.

    Mengembalikan dict berisi `data`, `bytes_per_row`, `width`, `height`.
    """
    from PIL import Image

    threshold = int(options.get("threshold") or 128)
    dither = bool(options.get("dither", False))
    trim = options.get("trim", True)
    margin_bawah = int(options.get("bottom_margin_dots", 16) or 0)

    # Ratakan transparansi ke putih agar area kosong tidak menjadi hitam pekat
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        latar = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(latar, img)

    if img.width != lebar:
        tinggi_baru = max(1, int(round(img.height * lebar / img.width)))
        img = img.resize((lebar, tinggi_baru), Image.LANCZOS)

    if img.mode != "L":
        img = img.convert("L")

    if dither:
        bw = img.convert("1")                                  # Floyd-Steinberg
    else:
        t = max(1, min(254, threshold))
        bw = img.point(lambda p: 255 if p > t else 0, mode="1")

    width, height = bw.size
    if width <= 0 or height <= 0:
        raise EscPosConversionError("Ukuran gambar hasil render tidak valid (0 piksel).")

    # Pillow memaketkan mode "1" per baris hingga batas byte; bit 1 = putih.
    # ESC/POS memakai bit 1 = titik hitam, sehingga seluruh byte dibalik.
    mentah = bw.tobytes()
    data = bytes((~b) & 0xFF for b in mentah)

    bytes_per_row = (width + 7) // 8
    if len(data) != bytes_per_row * height:
        raise EscPosConversionError(
            f"Ukuran buffer tidak sesuai: {len(data)} byte, "
            f"diharapkan {bytes_per_row * height} byte."
        )

    if trim:
        baris_isi = height
        while baris_isi > 0:
            awal = (baris_isi - 1) * bytes_per_row
            if any(data[awal:awal + bytes_per_row]):
                break
            baris_isi -= 1
        if baris_isi == 0:
            raise EscPosConversionError(
                "Halaman kosong setelah dikonversi ke hitam-putih. "
                "Turunkan nilai threshold bila isinya berwarna terang."
            )
        height = min(height, baris_isi + max(0, margin_bawah))
        data = data[:bytes_per_row * height]

    return {
        "data": data,
        "bytes_per_row": bytes_per_row,
        "width": width,
        "height": height,
    }


def _bungkus_raster(raster: Dict[str, Any]) -> bytes:
    """Membungkus buffer bit menjadi rentetan perintah GS v 0 per pita baris."""
    data = raster["data"]
    bytes_per_row = raster["bytes_per_row"]
    height = raster["height"]

    potongan: List[bytes] = []
    for y0 in range(0, height, PITA_BARIS):
        tinggi_pita = min(PITA_BARIS, height - y0)
        awal = y0 * bytes_per_row
        akhir = awal + tinggi_pita * bytes_per_row

        potongan.append(
            GS + b"v0" + bytes([
                0x00,                                  # m = mode normal
                bytes_per_row & 0xFF,                  # xL
                (bytes_per_row >> 8) & 0xFF,           # xH
                tinggi_pita & 0xFF,                    # yL
                (tinggi_pita >> 8) & 0xFF,             # yH
            ])
        )
        potongan.append(data[awal:akhir])

    return b"".join(potongan)


def _bungkus_dokumen(halaman: List[bytes], options: Dict[str, Any]) -> bytes:
    """Menambahkan inisialisasi, feed, potong kertas, dan pengulangan qty."""
    qty = max(1, int(options.get("qty", 1) or 1))
    potong = options.get("cut", True)
    feed = max(0, int(options.get("feed", 3) or 0))

    satu = bytearray(INIT)
    for isi in halaman:
        satu.extend(isi)
    satu.extend(b"\n" * feed)
    if potong:
        satu.extend(CUT_FEED)

    return bytes(satu) * qty


def pdf_to_escpos(pdf_bytes: bytes, options: Optional[Dict[str, Any]] = None) -> bytes:
    """
    Mengubah berkas PDF menjadi perintah raster ESC/POS.

    Setiap halaman PDF diskalakan agar lebarnya pas dengan lebar kertas, lalu
    dirangkai menjadi satu dokumen cetak.

    Opsi yang dikenali:
        width_dots   int   lebar cetak dalam dot, bawaan 576 (80 mm)
        width_mm     int   alternatif width_dots dalam milimeter (58/72/80)
        threshold    int   ambang hitam-putih 1..254, bawaan 128
        dither       bool  pakai dithering Floyd-Steinberg, bawaan False
        trim         bool  buang baris kosong di bawah isi, bawaan True
        qty          int   jumlah salinan, bawaan 1
        cut          bool  potong kertas di akhir, bawaan True
        feed         int   jumlah baris feed sebelum potong, bawaan 3
        bottom_margin_dots int  sisa margin setelah trim, bawaan 16
    """
    options = dict(options or {})
    lebar = lebar_dot(options)

    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise EscPosConversionError(
            "PyMuPDF (fitz) tidak tersedia, konversi PDF ke ESC/POS tidak dapat "
            "dilakukan. Jalankan: pip install pymupdf"
        ) from e

    try:
        from PIL import Image
    except ImportError as e:
        raise EscPosConversionError(
            "Pillow tidak tersedia, konversi PDF ke ESC/POS tidak dapat dilakukan. "
            "Jalankan: pip install pillow"
        ) from e

    # PyMuPDF versi baru ikut mengenali HTML/XPS dan merendernya pada halaman
    # bawaan 400x600 pt. Data non-PDF ditolak di sini dengan pesan yang bisa
    # ditindaklanjuti, bukan dibiarkan tercetak salah ukuran.
    kepala = bytes(pdf_bytes[:1024]).lstrip()
    if not kepala.startswith(b"%PDF-"):
        contoh = kepala[:40].decode("ascii", errors="replace")
        if kepala[:1] == b"<":
            raise EscPosConversionError(
                "Data yang dikirim adalah HTML, bukan PDF. Bila sumbernya berupa "
                "URL, kemungkinan besar server mengembalikan halaman login karena "
                "bridge mengunduh tanpa sesi. Unduh PDF di sisi aplikasi lalu "
                f"kirim Base64-nya. Awal data: {contoh!r}"
            )
        raise EscPosConversionError(
            f"Data yang dikirim bukan berkas PDF (tidak diawali '%PDF-'). "
            f"Awal data: {contoh!r}"
        )

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise EscPosConversionError(f"Berkas bukan PDF yang valid: {e}") from e

    if len(doc) == 0:
        raise EscPosConversionError("Dokumen PDF kosong (0 halaman).")

    halaman: List[bytes] = []
    try:
        for idx in range(len(doc)):
            page = doc.load_page(idx)
            if page.rect.width <= 0:
                raise EscPosConversionError(f"Halaman {idx + 1} punya lebar 0 pt.")

            # Skala dihitung dari lebar halaman, bukan dpi, supaya hasilnya
            # selalu tepat selebar kertas printer.
            zoom = lebar / page.rect.width
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            raster = _pil_ke_raster(img, lebar, options)
            halaman.append(_bungkus_raster(raster))
            logger.info(
                "[PdfToEscPos] Halaman %d/%d -> %dx%d dot (%d byte raster), "
                "lebar halaman %.1f pt",
                idx + 1, len(doc), raster["width"], raster["height"],
                len(raster["data"]), page.rect.width
            )
    finally:
        try:
            doc.close()
        except Exception:
            pass

    return _bungkus_dokumen(halaman, options)


def image_to_escpos(image_bytes: bytes, options: Optional[Dict[str, Any]] = None) -> bytes:
    """Mengubah berkas gambar (PNG/JPG/BMP) menjadi perintah raster ESC/POS."""
    options = dict(options or {})
    lebar = lebar_dot(options)

    try:
        import io
        from PIL import Image
    except ImportError as e:
        raise EscPosConversionError(
            "Pillow tidak tersedia untuk konversi gambar ke ESC/POS."
        ) from e

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as e:
        raise EscPosConversionError(f"Berkas gambar tidak dapat dibaca: {e}") from e

    raster = _pil_ke_raster(img, lebar, options)
    return _bungkus_dokumen([_bungkus_raster(raster)], options)
