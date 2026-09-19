# 🚀 Quick Start — Mencetak Pertama Kali dalam 5 Menit

Panduan instalasi lengkap ada di [03-instalasi.md](03-instalasi.md). Halaman ini
adalah jalur tercepat sampai kertas keluar dari printer.

---

## Langkah 1 — Jalankan Bridge

### Windows (paket portable)

```
1. Ekstrak HardwareBridge_Windows_x64_Portable.zip
2. Klik ganda Run_HardwareBridge.bat
3. Ikon ⚡ hijau muncul di system tray (pojok kanan bawah)
```

### Windows (dari kode sumber)

```powershell
pip install -r requirements.txt
python app.py
```

### Linux Mint 22 / Ubuntu 22

```bash
cd linux && ./run.sh
```

Bridge berjalan di `http://127.0.0.1:18212`. Bila port itu terpakai, bridge
otomatis berpindah ke `12212` — lihat baris `[Port]` pada log.

---

## Langkah 2 — Pastikan Bridge Hidup

Buka `http://127.0.0.1:18212` di browser PC yang sama. Dashboard harus tampil.

Atau lewat terminal:

```bash
curl http://127.0.0.1:18212/api/status
```

---

## Langkah 3 — Kenali Nama Printer Anda

```bash
curl http://127.0.0.1:18212/api/printers
```

Catat nilai `name` persis seperti yang tertulis, misalnya `Godex G500 GZPL`.

---

## Langkah 4 — Uji Cetak Tanpa Menulis Kode

Dashboard → kartu **Sandbox**:

| Tab | Fungsi |
|-----|--------|
| **Cetak Base64 PDF** | Tempel string Base64 PDF, pratinjau, lalu cetak |
| **Cetak dari Berkas / URL** | Masukkan URL PDF atau unggah berkas |
| **Struk ESC/POS** | Cetak struk contoh |
| **RAW Kustom** | Kirim perintah ZPL / TSPL / ESC/POS mentah |

Atau lewat terminal:

```bash
curl -X POST "http://127.0.0.1:18212/api/print/test-label?printer=Godex%20G500%20GZPL"
```

Kalau langkah ini berhasil, printer dan bridge sudah beres. Sisanya tinggal
memanggil dari aplikasi web.

---

## Langkah 5 — Atur Alias Printer (Pool)

Supaya kode aplikasi tidak terikat pada nama printer tiap PC, buka
Dashboard → **Pengaturan** → **Printer Pool**, lalu petakan:

| Alias | Printer Fisik |
|-------|---------------|
| `asset_label` | Godex G500 GZPL |
| `receipt` | EPSON TM-T82 |
| `invoice` | HP LaserJet Pro |

Kode aplikasi cukup menyebut `asset_label`, dan tiap PC memetakannya sendiri.

---

## Langkah 6 — Panggil dari Aplikasi Web

```html
<script src="http://127.0.0.1:18212/api/download/hardware-bridge.js"></script>

<button onclick="cetak()">🖨️ Cetak</button>

<script>
async function cetak() {
    try {
        const r = await HardwareBridge.printPdf(
            'asset_label',                                                   // alias pool
            'http://192.168.3.25/produksi/ProduksiPDF/PRD-2026-0012.pdf',    // URL PDF
            'Label Produksi',                                                // nama job
            { dpi: 203 }                                                     // opsi
        );
        if (r.status !== 'success') throw new Error(r.detail || 'Gagal');
        alert('✅ Terkirim ke ' + r.result.printer);
    } catch (e) {
        alert('❌ ' + e.message);
    }
}
</script>
```

Tanpa SDK, dengan `fetch` biasa:

```js
const res = await fetch('http://127.0.0.1:18212/api/print/pdf', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        printer:  'asset_label',
        pdf_data: 'http://192.168.3.25/produksi/ProduksiPDF/PRD-2026-0012.pdf',
        doc_name: 'Label Produksi',
        options:  { dpi: 203 }
    })
});
const json = await res.json();
if (!res.ok || json.status !== 'success') throw new Error(json.detail);
```

---

## Langkah Berikutnya

| Kebutuhan | Dokumen |
|-----------|---------|
| HTML → Base64 → cetak | [direct-print/02-html-ke-base64.md](direct-print/02-html-ke-base64.md) |
| Detail lengkap cetak dari URL | [direct-print/03-pdf-dari-url.md](direct-print/03-pdf-dari-url.md) |
| Struk thermal / label barcode | [direct-print/04-raw-escpos-zpl.md](direct-print/04-raw-escpos-zpl.md) |
| Bridge jalan otomatis saat booting | [03-instalasi.md](03-instalasi.md) |
| Membaca timbangan digital | [06-timbangan-serial.md](06-timbangan-serial.md) |
| Cetak gagal | [direct-print/07-troubleshooting-print.md](direct-print/07-troubleshooting-print.md) |
