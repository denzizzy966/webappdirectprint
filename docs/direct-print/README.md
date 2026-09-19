# 🖨️ Panduan Direct Print (Silent Print) — Hardware Bridge

Dokumen ini adalah **pintu masuk** seluruh panduan cetak langsung tanpa dialog
(`silent print`) pada WebApp Hardware Bridge Universal.

---

## 📑 Daftar Berkas di Folder Ini

| Berkas | Isi |
|--------|-----|
| [01-konsep-dan-alur.md](01-konsep-dan-alur.md) | Alur data browser → bridge → printer, dan format data yang diterima |
| [02-html-ke-base64.md](02-html-ke-base64.md) | **Cetak dari HTML yang dikonversi ke Base64** (html2pdf, jsPDF, dompdf, html2canvas) |
| [03-pdf-dari-url.md](03-pdf-dari-url.md) | **Cetak dari URL PDF** seperti `http://192.168.3.25/produksi/ProduksiPDF/<data>.pdf` |
| [04-raw-escpos-zpl.md](04-raw-escpos-zpl.md) | Cetak RAW: struk thermal ESC/POS, label barcode ZPL/TSPL, laci kasir |
| [05-printer-target-pool.md](05-printer-target-pool.md) | Memilih printer: nama fisik, alias `pool`, printer jaringan TCP 9100 |
| [06-referensi-api-print.md](06-referensi-api-print.md) | Referensi lengkap payload & respons endpoint cetak (REST + WebSocket) |
| [07-troubleshooting-print.md](07-troubleshooting-print.md) | Daftar galat yang sering muncul beserta solusinya |
| [08-printer-label-zpl.md](08-printer-label-zpl.md) | **Mode ZPL Raster**: solusi bila PDF/Base64 gagal dicetak di printer label |

---

## ⚡ Ringkasan 30 Detik

Bridge berjalan di **PC klien** (kasir / operator produksi) dan membuka HTTP API lokal:

```
http://127.0.0.1:18212/api/print/pdf     ← fallback port lama: 12212
```

Kirim JSON `POST`, isi `pdf_data` dengan **salah satu** dari:

| Isi `pdf_data` | Contoh | Siapa yang mengambil data |
|----------------|--------|---------------------------|
| URL berkas PDF | `http://192.168.3.25/produksi/ProduksiPDF/PRD-001.pdf` | **Bridge** (Python `requests`), bukan browser |
| Data URI Base64 | `data:application/pdf;base64,JVBERi0xLjQK...` | Browser yang menyusun, bridge decode |
| Prefiks `base64:` | `base64:JVBERi0xLjQK...` | Browser yang menyusun, bridge decode |
| Base64 polos | `JVBERi0xLjQK...` | Browser yang menyusun, bridge decode |
| Path berkas lokal | `C:\temp\label.pdf` | Bridge membaca disk PC klien |

```js
await fetch('http://127.0.0.1:18212/api/print/pdf', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    printer:  'asset_label',                 // nama printer ATAU alias pool
    pdf_data: 'http://192.168.3.25/produksi/ProduksiPDF/PRD-001.pdf',
    doc_name: 'Label Produksi PRD-001',
    options:  { dpi: 203 }                   // dpi WAJIB di dalam "options"
  })
});
```

---

## ❗ Tiga Hal yang Paling Sering Salah

1. **HTML mentah tidak bisa dicetak lewat `/api/print/pdf`.**
   Endpoint ini hanya menerima **PDF**. HTML harus dirender jadi PDF (atau gambar)
   lebih dulu → lihat [02-html-ke-base64.md](02-html-ke-base64.md).

2. **`dpi` / `orientation` harus berada di dalam objek `options`,** bukan di level atas
   JSON. Field di level atas akan diabaikan oleh model Pydantic `PrintPdfRequest`.

3. **URL PDF diunduh oleh bridge, bukan oleh browser.**
   Jadi PC tempat bridge berjalan yang harus bisa menjangkau `192.168.3.25`,
   dan URL tersebut harus bisa dibuka **tanpa login/sesi** → lihat
   [03-pdf-dari-url.md](03-pdf-dari-url.md).

4. **Printer label menolak PDF?** Kirim `options: { mode: "zpl", dpi: 203 }`.
   PDF diubah menjadi perintah ZPL raster lalu dikirim lewat jalur RAW — jalur
   yang sama dengan template ZPL yang sudah berhasil di tab Custom RAW →
   [08-printer-label-zpl.md](08-printer-label-zpl.md).
