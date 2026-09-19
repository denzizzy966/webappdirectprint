# 1. Konsep & Alur Data Direct Print

---

## 1.1 Kenapa Bridge Berjalan di PC Klien

Printer USB/LPT dan port COM hanya terlihat oleh sistem operasi **komputer yang
mencolokkannya**. Server web (Laravel, ERPNext, PHP) tidak punya akses ke perangkat
itu. Karena itu Hardware Bridge dipasang di PC operator dan dipanggil dari
JavaScript halaman web melalui `127.0.0.1`.

Penjelasan lengkap: [../01-arsitektur.md](../01-arsitektur.md)

---

## 1.2 Alur Lengkap

```
┌──────────────────────────────────────────────────────────────────────────┐
│ BROWSER (halaman web produksi / POS / ERPNext)                           │
│                                                                          │
│   1. Siapkan data cetak                                                  │
│      • URL PDF     → "http://192.168.3.25/produksi/ProduksiPDF/X.pdf"    │
│      • Base64 PDF  → hasil render html2pdf / jsPDF / dompdf              │
│      • RAW ESC/POS → string perintah struk                               │
│                                                                          │
│   2. fetch POST → http://127.0.0.1:18212/api/print/pdf                   │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │ JSON (localhost, tidak keluar jaringan)
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ HARDWARE BRIDGE (FastAPI, PC klien)                                      │
│                                                                          │
│   3. routes_http.py  → PrintPdfRequest (validasi payload)                │
│   4. printer_manager.print_pdf()                                         │
│        • URL?      → requests.get(url, timeout=15) → bytes               │
│        • base64?   → strip whitespace + auto-padding → b64decode         │
│        • path?     → open(path, "rb").read()                             │
│   5. resolve_printer(target)  → alias pool → nama printer fisik OS       │
│   6. backend cetak:                                                      │
│        • Windows → PyMuPDF raster → GDI Printer DC (win_spooler.py)      │
│        • Linux   → tulis berkas sementara → perintah `lp` (cups_linux)   │
└─────────────────────────────┬────────────────────────────────────────────┘
                              ▼
                     🖨️ Printer (USB / Jaringan / Spooler OS)
```

---

## 1.3 Endpoint Cetak yang Tersedia

| Endpoint | Jenis data | Dipakai untuk |
|----------|-----------|----------------|
| `POST /api/print/pdf` | PDF (URL / Base64 / path) | Faktur, surat jalan, label produksi, hasil render HTML |
| `POST /api/print/raw` | ESC/POS, ZPL, TSPL, teks polos | Struk thermal, label barcode langsung ke bahasa printer |
| `POST /api/print/image` | PNG / JPG / BMP (Base64) | Tangkapan `html2canvas`, logo, QR gambar |
| `POST /api/cashdrawer/open` | — | Pulsa buka laci kasir |
| `POST /api/print/test-receipt` | — | Struk contoh untuk uji printer thermal |
| `POST /api/print/test-label` | — | Label ZPL contoh untuk uji Godex/Zebra |
| `GET  /api/print/history` | — | 100 job cetak terakhir |

Seluruh endpoint di atas juga tersedia lewat WebSocket `ws://127.0.0.1:18212/ws`
dengan `action: "print"` → lihat [06-referensi-api-print.md](06-referensi-api-print.md).

---

## 1.4 Format `pdf_data` yang Dikenali Bridge

`printer_manager.print_pdf()` mendeteksi format secara otomatis, berurutan:

| Urutan | Kondisi | Perlakuan |
|--------|---------|-----------|
| 1 | Diawali `http://` atau `https://` | Diunduh bridge, timeout **15 detik** |
| 2 | Mengandung `;base64,` (data URI) | Ambil potongan setelah `;base64,`, buang spasi, auto-padding `=` |
| 3 | Diawali `base64:` | Buang prefiks, buang spasi, auto-padding `=` |
| 4 | Base64 polos | Di-decode bila hasilnya diawali `%PDF-` **atau** panjang string > 80 karakter |
| 5 | Sisanya | Dianggap **path berkas** di disk PC klien |

> **Catatan penting:** pada urutan ke-4, string Base64 yang panjang tetap diterima
> walau isinya bukan PDF. Kegagalan baru muncul saat PyMuPDF membukanya, dengan
> pesan `Gagal mencetak PDF ke '<printer>': ...`. Inilah yang terjadi bila Anda
> mengirim **HTML yang di-Base64-kan langsung**.

---

## 1.5 Bentuk Respons

**Sukses — HTTP 200:**

```json
{
  "status": "success",
  "result": {
    "success": true,
    "printer": "Godex G500 GZPL",
    "job_id": "42",
    "message": "PDF berhasil dicetak (1 halaman)",
    "bytes_sent": 18342,
    "error": null
  }
}
```

**Gagal — HTTP 500:**

```json
{ "detail": "Gagal mengunduh PDF dari URL: HTTPConnectionPool(host='192.168.3.25', port=80): Read timed out." }
```

Karena kegagalan dikembalikan sebagai **HTTP 500**, `fetch()` tetap resolve
(tidak throw). Selalu periksa `res.ok` atau `json.status`:

```js
const res  = await fetch(url, opt);
const json = await res.json();
if (!res.ok || json.status !== 'success') {
    throw new Error(json.detail || json.message || 'Gagal mencetak');
}
```

---

## 1.6 Perilaku Khusus per Sistem Operasi

| Aspek | Windows (`win_spooler.py`) | Linux (`cups_linux.py`) |
|-------|----------------------------|--------------------------|
| Mesin render PDF | PyMuPDF (`fitz`) → bitmap → GDI | Diserahkan ke filter CUPS (`lp`) |
| `options.dpi` | **Dipakai**, default `300` | Diabaikan |
| `options.orientation` / `fit` | Belum diimplementasikan (diabaikan) | Diabaikan |
| Penskalaan | Otomatis `min(lebar, tinggi)`, rata tengah horizontal, mepet atas | Sesuai pengaturan antrean CUPS |
| Ukuran kertas | **Diambil dari driver printer Windows**, bukan dari payload | Dari opsi antrean CUPS |

> Untuk label 60×25 mm (Godex G500), atur ukuran kertas di **driver printer Windows**
> (Devices and Printers → Printing Preferences). Bridge tidak mengirim ukuran kertas
> dari payload JSON.
