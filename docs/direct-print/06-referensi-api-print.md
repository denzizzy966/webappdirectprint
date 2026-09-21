# 6. Referensi API Cetak (REST & WebSocket)

Alamat dasar: `http://127.0.0.1:18212` (fallback otomatis ke `12212`).
Semua respons berformat JSON.

---

## 6.1 `POST /api/print/pdf`

Mencetak PDF secara silent. Model: `PrintPdfRequest` di
[`app/api/routes_http.py`](../../app/api/routes_http.py).

### Body

| Field | Tipe | Wajib | Keterangan |
|-------|------|-------|------------|
| `pdf_data` | string | **Ya**\* | URL, data URI Base64, `base64:...`, Base64 polos, atau path berkas lokal |
| `file_content` | string | Tidak | Alias `pdf_data` (kompatibel `printService.submit` / `whb_print.js`) |
| `url` | string | Tidak | Dipakai sebagai `doc_name`; bila berupa `http(s)://` juga menjadi sumber PDF |
| `printer` | string | Tidak | Nama printer fisik atau alias pool |
| `target` | string | Tidak | Sinonim `printer` (kompatibilitas imTigger) |
| `pool` | string | Tidak | Sinonim `printer` |
| `doc_name` | string | Tidak | Nama job di spooler. Bawaan `HardwareBridge_PDF` |
| `options` | objek | Tidak | Lihat tabel di bawah |

\* Isi salah satu dari `pdf_data`, `file_content`, atau `url`. Bila ketiganya
kosong, bridge mengembalikan HTTP 422.

### `options`

| Kunci | Tipe | Bawaan | Status |
|-------|------|--------|--------|
| `mode` | string | `auto` | `auto` / `driver` / `zpl` / `escpos` — lihat §6.1.1 |
| `dpi` | int | `203` pada mode ZPL, `300` pada mode driver | ✅ Dipakai di Windows & mode ZPL. Diabaikan di Linux/CUPS |
| `qty` | int | `1` | ✅ Jumlah rangkap |
| `threshold` | int | `128` | ✅ Ambang hitam-putih, hanya mode ZPL |
| `dither` | bool | `false` | ✅ Dithering, hanya mode ZPL |
| `darkness` | int | — | ✅ `^MD`, hanya mode ZPL |
| `speed` | int | — | ✅ `^PR`, hanya mode ZPL |
| `rotate` | string | `N` | ✅ `^PO` N/R/I/B, hanya mode ZPL |
| `offset_x`, `offset_y` | int | `0` | ✅ `^FO`, hanya mode ZPL |
| `orientation` | string | — | ⚠️ Diterima tetapi belum diimplementasikan |
| `fit` | string | — | ⚠️ Diterima tetapi belum diimplementasikan |
| `width_dots` | int | `576` | ✅ Lebar cetak dalam dot, hanya mode ESC/POS. Dibulatkan turun ke kelipatan 8 |
| `width_mm` | int | `80` | ✅ Alternatif `width_dots` dalam milimeter (58/72/80), hanya mode ESC/POS |
| `trim` | bool | `true` | ✅ Buang baris kosong di bawah isi, hanya mode ESC/POS |
| `cut` | bool | `true` | ✅ Potong kertas di akhir, hanya mode ESC/POS |
| `feed` | int | `3` | ✅ Baris feed sebelum potong, hanya mode ESC/POS |

> ℹ️ Seluruh kunci di atas **juga boleh dikirim di level atas JSON**, demi
> kompatibilitas dengan klien lama. Nilai di dalam `options` menang bila kunci
> yang sama muncul di kedua tempat.

### 6.1.1 `options.mode`

| Nilai | Perilaku |
|-------|----------|
| `auto` | **Bawaan.** Memakai ZPL raster bila nama/driver printer mengandung `zpl`, `gzpl`, `ezpl`, `zdesigner`, `zebra`, `godex`, `zt###`, `gk###`, `gx###`. Selain itu memakai driver. Bila konversi ZPL gagal, otomatis kembali ke driver |
| `zpl` | Selalu mengubah PDF menjadi ZPL `^GFA` lalu kirim lewat jalur RAW. Kegagalan dikembalikan sebagai galat |
| `escpos` | Selalu mengubah PDF menjadi raster ESC/POS `GS v 0` lalu kirim lewat jalur RAW. Kegagalan dikembalikan sebagai galat |
| `driver` | Selalu memakai driver grafis (Windows GDI / CUPS) |

`auto` **tidak pernah** memilih `escpos` sendiri — printer ESC/POS tidak bisa
dikenali dari namanya seandal printer ZPL, dan salah tebak berarti berlembar-lembar
kertas sampah. Mode ini harus diminta secara eksplisit.

Mode `escpos` diperlukan bila printer struk dipasang sebagai perangkat langsung
(`/dev/usb/lp0`, `/dev/usb/lp1`) atau antrean RAW: di situ tidak ada filter CUPS
maupun driver Windows yang bisa meraster PDF, sehingga mode `driver` akan gagal.
Berbeda dengan mode ZPL, skala halaman dihitung dari `width_dots` (bukan `dpi`)
agar hasilnya selalu tepat selebar kertas.

```bash
curl -X POST http://127.0.0.1:18212/api/print/pdf   -H "Content-Type: application/json"   -d '{"printer":"tmt","pdf_data":"JVBERi0xLjQK...","doc_name":"Struk_POS",
       "options":{"mode":"escpos","width_mm":80,"threshold":128,"qty":1}}'
```

Panduan lengkap ZPL: [08-printer-label-zpl.md](08-printer-label-zpl.md).

### Contoh

```json
{
  "printer":  "asset_label",
  "pdf_data": "http://192.168.3.25/produksi/ProduksiPDF/PRD-2026-0012.pdf",
  "doc_name": "Produksi_PRD-2026-0012",
  "options":  { "dpi": 203 }
}
```

### Respons Sukses — HTTP 200

```json
{
  "status": "success",
  "result": {
    "success": true,
    "printer": "Godex G500 GZPL",
    "job_id": null,
    "message": "PDF berhasil dicetak (1 halaman)",
    "bytes_sent": 18342,
    "error": null
  }
}
```

`job_id` terisi pada Linux (id antrean CUPS) dan pada jalur RAW Windows; pada
jalur PDF Windows bernilai `null` karena memakai GDI Printer DC.

### Respons Gagal — HTTP 500

```json
{ "detail": "Gagal mengunduh PDF dari URL: 404 Client Error: Not Found for url: ..." }
```

---

## 6.2 `POST /api/print/raw`

| Field | Tipe | Wajib | Keterangan |
|-------|------|-------|------------|
| `data` | string | **Ya** | ESC/POS, ZPL, TSPL, teks polos, `base64:...`, atau data URI |
| `printer` / `target` / `pool` | string | Tidak | Printer tujuan |
| `doc_name` | string | Tidak | Bawaan `DirectPrint_Raw` |

```json
{ "printer": "receipt", "data": "\u001b@Halo Dunia\n\n\n\u001dV\u0000", "doc_name": "Struk" }
```

---

## 6.3 `POST /api/print/image`

| Field | Tipe | Wajib | Keterangan |
|-------|------|-------|------------|
| `image_data` | string | **Ya** | PNG/JPG/BMP sebagai data URI, `base64:...`, atau Base64 polos |
| `printer` / `target` / `pool` | string | Tidak | Printer tujuan |
| `doc_name` | string | Tidak | Bawaan `DirectPrint_Image` |

Endpoint ini menerima `options` yang sama dengan `/api/print/pdf`, termasuk
`mode: "zpl"` untuk mencetak gambar ke printer label, serta `label_width_dots`
untuk menskalakan gambar ke lebar label sebelum dikonversi.

---

## 6.4 Endpoint Cetak Lainnya

| Endpoint | Metode | Parameter | Keterangan |
|----------|--------|-----------|------------|
| `/api/cashdrawer/open` | POST | `{ printer, pin }` | `pin` = 2 (bawaan) atau 5 |
| `/api/print/test-receipt` | POST | `?printer=` | Struk ESC/POS contoh |
| `/api/print/test-label` | POST | `?printer=` | Label ZPL contoh |
| `/api/print/history` | GET | — | 100 job terakhir |
| `/api/print/pdf-to-zpl` | POST | sama dengan `/api/print/pdf` | Mengubah PDF menjadi ZPL **tanpa mencetak** |
| `/api/printers` | GET | — | Daftar printer + pool |
| `/api/printers/pools` | GET / POST | — | Baca / simpan pemetaan pool |

### Bentuk `/api/print/history`

```json
{
  "status": "success",
  "history": [
    {
      "id": 7,
      "type": "PDF",
      "printer": "Godex G500 GZPL",
      "time": "2026-09-19 10:42:11",
      "success": true,
      "message": "PDF berhasil dicetak (1 halaman)",
      "bytes": 18342
    }
  ]
}
```

Riwayat disimpan di memori (`deque`, maksimal 100) dan hilang saat bridge
dijalankan ulang.

---

## 6.5 WebSocket `ws://127.0.0.1:18212/ws`

Rute yang diterima: `/ws`, `/`, `/printer`, `/serial/DISPLAY`, `/serial/WEIGH`.

### Aksi Cetak

```json
{
  "action":  "print",
  "printer": "asset_label",
  "type":    "pdf",
  "data":    "http://192.168.3.25/produksi/ProduksiPDF/PRD-2026-0012.pdf",
  "docName": "Produksi_PRD-2026-0012",
  "options": { "dpi": 203 }
}
```

`type` dapat berupa `raw` (bawaan), `pdf`, atau `image`.

Respons:

```json
{
  "action": "print",
  "status": "success",
  "printer": "Godex G500 GZPL",
  "message": "PDF berhasil dicetak (1 halaman)",
  "bytes": 18342
}
```

`options` diteruskan sepenuhnya, dan kunci render juga boleh diletakkan di level
atas pesan (`"mode": "zpl"`, `"dpi": 203`, `"qty": 2`).

### Format Kompatibel `whb_print.js` (ERPNext)

Pesan yang memuat `file_content`, atau `type` bernilai `asset_label`/`pdf`,
ditangani sebagai cetak PDF — **di sini `qty` didukung**:

```json
{
  "type": "asset_label",
  "file_content": "JVBERi0xLjQK...",
  "url": "Label ASSET-0001",
  "qty": 2
}
```

Pemetaan field:

| Field | Dipetakan ke |
|-------|--------------|
| `file_content` atau `data` | `pdf_data` |
| `url`, `docName` | `doc_name` |
| `printer`, `target`, `pool`, `type` | target printer (urut prioritas) |
| `qty` | jumlah pengulangan cetak (minimal 1) |

### Aksi WebSocket Lainnya

| `action` | Keterangan |
|----------|------------|
| `getPrinters` | Daftar printer + pool + printer bawaan |
| `openCashDrawer` | `{ printer, pin }` |
| `getWeight` | Berat timbangan saat ini |
| `zero`, `tare` | Perintah timbangan |
| `subscribeScale` / `unsubscribeScale` | Stream `scale_update` tiap 0,3 detik |
| `getSerialPorts` | Daftar port COM / ttyUSB |
| `ping` | Balasan `pong` |

---

## 6.6 SDK JavaScript

Unduh: `http://127.0.0.1:18212/api/download/hardware-bridge.js`

```html
<script src="http://127.0.0.1:18212/api/download/hardware-bridge.js"></script>
```

### Metode Statis (HTTP, dengan fallback port otomatis)

```js
HardwareBridge.getPrinters();
HardwareBridge.printRaw(namaPrinter, dataRaw, docName);
HardwareBridge.printPdf(namaPrinter, pdfAtauUrl, docName, options);
HardwareBridge.printImage(namaPrinter, gambarBase64, docName);
HardwareBridge.openCashDrawer(namaPrinter, pin);
HardwareBridge.configure({ host, port, scalePort });
HardwareBridge.toast(pesan, warna);
```

> ❗ **Argumennya posisional, bukan objek.**
>
> ```js
> // ❌ SALAH — objek menjadi nama printer, pdf_data menjadi undefined
> HardwareBridge.printPdf({ printer: 'asset_label', pdf_data: url });
>
> // ✅ BENAR
> HardwareBridge.printPdf('asset_label', url, 'Label', { mode: 'zpl', dpi: 203 });
> ```

Nilai kembalian metode statis adalah **body JSON apa adanya**, jadi periksa
`res.status === 'success'` dan baca `res.detail` saat gagal.

### Instance (WebSocket, dengan fallback HTTP)

```js
const bridge = new HardwareBridge({ host: '127.0.0.1', port: 18212 });
await bridge.connect();                       // false bila WS tidak tersedia
await bridge.printPdf('asset_label', url, 'Label', { dpi: 203 });
```

Bila `connect()` gagal, metode instance otomatis memakai `fetch` HTTP.

---

## 6.7 Deteksi Bridge Aktif

```js
async function bridgeAktif(timeoutMs = 1500) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
        const r = await fetch('http://127.0.0.1:18212/api/status', { signal: ctrl.signal });
        return r.ok;
    } catch {
        return false;
    } finally {
        clearTimeout(t);
    }
}

if (!await bridgeAktif()) {
    alert('Hardware Bridge belum berjalan. Jalankan Run_HardwareBridge.bat terlebih dahulu.');
}
```

`GET /api/status` mengembalikan versi, sistem operasi, printer bawaan, jumlah
printer, dan status seluruh timbangan.
