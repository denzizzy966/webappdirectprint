# 8. Mode ZPL Raster — Cetak PDF/Base64 ke Printer Label

Panduan ini untuk kasus: **PDF Base64 gagal terus dicetak, padahal template ZPL
di tab Custom RAW berhasil.**

---

## 8.1 Kenapa PDF Gagal di Printer Label

Printer label seperti **Godex G500 GZPL** dan **Zebra ZDesigner** bekerja dengan
bahasa **ZPL**. Driver Windows-nya menyediakan lapisan GDI, tetapi lapisan itu
sering tidak lengkap atau gagal saat dipakai mencetak dokumen:

```
Gagal mencetak PDF ke 'Godex G500 GZPL': CreatePrinterDC ...
```

Sementara itu, perintah ZPL mentah lewat `/api/print/raw` selalu berhasil,
karena byte-nya dikirim apa adanya ke printer tanpa melewati GDI.

**Mode ZPL Raster menyatukan keduanya:** PDF dirender menjadi bitmap, bitmap
diubah menjadi perintah ZPL `^GFA`, lalu dikirim lewat jalur RAW yang sudah
terbukti bekerja.

```
PDF Base64 ──► PyMuPDF (raster @203 dpi) ──► bitmap 1-bit ──► ^GFA hex
                                                                  │
                                              jalur RAW yang sama dengan
                                              template ZPL Custom RAW
                                                                  ▼
                                                            🖨️ Godex G500
```

---

## 8.2 Cara Memakainya

### Dari Dashboard Sandbox

`http://127.0.0.1:18212` → kartu **Sandbox** → tab **Cetak Base64 PDF**:

1. Tempel string Base64 (atau klik **Muat Sampel Label 60x25**).
2. **Mode Cetak** → pilih **ZPL Raster ^GFA (Godex / Zebra)**.
3. **DPI** → `203` untuk printer label thermal.
4. **Qty** → jumlah rangkap.
5. Klik **Cetak Base64 PDF (Silent Print)**.

Tombol **🔍 Pratinjau Perintah ZPL** mengubah PDF menjadi ZPL lalu memuatnya ke
tab **Custom RAW** tanpa mencetak — perintahnya bisa diperiksa dulu, lalu
dicetak dengan tombol **Cetak RAW Langsung**.

### Dari Kode

```js
await fetch('http://127.0.0.1:18212/api/print/pdf', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        printer:  'asset_label',
        pdf_data: base64Pdf,
        doc_name: 'Label_PRD-2026-0012',
        options:  { mode: 'zpl', dpi: 203, qty: 1 }
    })
});
```

---

## 8.3 Tiga Nilai `mode`

| `mode` | Perilaku |
|--------|----------|
| `auto` | **Bawaan.** Memakai ZPL bila nama atau driver printer mengandung `zpl`, `gzpl`, `ezpl`, `zdesigner`, `zebra`, `godex`, `zt###`, `gk###`, atau `gx###`. Selain itu memakai driver |
| `zpl` | Selalu ZPL raster, apa pun printernya |
| `driver` | Selalu jalur driver grafis (Windows GDI / CUPS), seperti perilaku versi sebelumnya |

Dengan `auto`, printer bernama `Godex G500 GZPL` **otomatis** memakai jalur ZPL —
tanpa perlu mengubah kode aplikasi yang sudah ada.

Bila `mode: "auto"` memilih ZPL tetapi konversinya gagal, bridge otomatis kembali
ke jalur driver dan mencatatnya di log. Dengan `mode: "zpl"`, kegagalan
dikembalikan sebagai galat agar masalahnya terlihat.

---

## 8.4 Opsi Lengkap Mode ZPL

| Opsi | Tipe | Bawaan | Keterangan |
|------|------|--------|------------|
| `mode` | string | `auto` | `auto` / `zpl` / `driver` |
| `dpi` | int | `203` | Resolusi render. **Harus sama dengan dpi printer** |
| `qty` | int | `1` | Jumlah rangkap. Diterjemahkan menjadi `^PQ` |
| `threshold` | int | `128` | Ambang hitam-putih 1–254. Lebih kecil = hasil lebih tipis |
| `dither` | bool | `false` | Dithering Floyd-Steinberg. **Jangan aktifkan untuk barcode** |
| `darkness` | int | — | Kegelapan pemanas (`^MD`), −30..30 |
| `speed` | int | — | Kecepatan cetak (`^PR`) |
| `rotate` | string | `N` | `N` / `R` (90°) / `I` (180°) / `B` (270°), lewat `^PO` |
| `offset_x` | int | `0` | Geser horizontal dalam dot (`^FO`) |
| `offset_y` | int | `0` | Geser vertikal dalam dot (`^FO`) |

### Hubungan DPI dengan Ukuran Label

Ukuran label ZPL diambil **langsung dari ukuran halaman PDF**, jadi tidak perlu
diisi manual. Pada 203 dpi, 1 mm = 8 dot:

| Ukuran PDF | Ukuran ZPL @203 dpi | Perintah |
|------------|---------------------|----------|
| 60 × 25 mm (170,08 × 70,87 pt) | 480 × 200 dot | `^PW480^LL200` |
| 100 × 50 mm | 800 × 400 dot | `^PW800^LL400` |
| 50 × 30 mm | 400 × 240 dot | `^PW400^LL240` |

> ⚠️ **DPI harus cocok dengan printer.** Mengirim raster 300 dpi ke printer
> 203 dpi menghasilkan label yang tercetak ~1,5× lebih besar dan terpotong.
> Godex G500 dan sebagian besar printer label thermal memakai **203 dpi**.

---

## 8.5 Menyesuaikan dengan dompdf

Setelan dompdf yang Anda pakai sudah pas:

```php
$pdf = Pdf::loadHtml($html);
$customPaper = array(0, 0, 60 * 2.83465, 25 * 2.83465);   // 170,08 x 70,87 pt
$pdf->setPaper($customPaper, 'landscape');
$hasilpdf = $pdf->output();

return response()->json([
    'status'     => 200,
    'pdf_base64' => base64_encode($hasilpdf),
]);
```

PDF 170,08 × 70,87 pt di atas menghasilkan tepat **480 × 200 dot** pada 203 dpi.

> Catatan: dengan `setPaper($customPaper, 'landscape')`, dompdf **menukar** sisi
> panjang dan pendek. Bila hasil cetak tampak berputar 90°, hilangkan
> `'landscape'` atau tukar angka lebar dan tingginya.

---

## 8.6 Migrasi dari `printService.submit`

Kode lama Anda:

```js
function printPDF(base64Data) {
    printService.submit({
        type: 'BARCODE',
        url: 'barcode.pdf',
        qty: 1,
        file_content: base64Data
    });
}
```

### Opsi 1 — Tanpa Ubah Kode Sama Sekali

Format itu **sudah didukung** oleh bridge, baik lewat WebSocket maupun HTTP:

| Field lama | Dipetakan ke |
|------------|--------------|
| `file_content` | sumber PDF (`pdf_data`) |
| `url` | `doc_name` |
| `type` | target printer; `BARCODE` cocok dengan pool `barcode` |
| `qty` | jumlah rangkap (`^PQ` pada mode ZPL) |

Syaratnya hanya satu: `bridge_config.json` punya pool `barcode` yang mengarah ke
printer Anda.

```json
{ "printers": { "pools": { "barcode": "Godex G500 GZPL" } } }
```

Karena nama printer mengandung `GZPL`, mode `auto` langsung memilih jalur ZPL.

### Opsi 2 — Versi HTTP yang Eksplisit

```js
async function printPDF(base64Data, qty = 1) {
    const res = await fetch('http://127.0.0.1:18212/api/print/pdf', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            printer:  'barcode',
            pdf_data: base64Data,
            doc_name: 'barcode.pdf',
            options:  { mode: 'zpl', dpi: 203, qty: qty }
        })
    });
    const json = await res.json();
    if (!res.ok || json.status !== 'success') {
        throw new Error(json.detail || 'Gagal mencetak label');
    }
    return json.result;
}
```

### Rangkaian Lengkap dengan Laravel

```js
async function cetakLabelDariHtml(htmlLabel, qty = 1) {
    // 1. HTML -> PDF di server (dompdf), kembalikan Base64
    const r = await fetch('/cetak/label-pdf', {
        method:  'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]').content
        },
        credentials: 'same-origin',
        body: JSON.stringify({ html: htmlLabel })
    });
    const { pdf_base64 } = await r.json();

    // 2. Base64 -> ZPL -> printer label
    return await printPDF(pdf_base64, qty);
}
```

---

## 8.7 Endpoint Pratinjau `/api/print/pdf-to-zpl`

Mengubah PDF menjadi ZPL **tanpa mencetak**. Berguna untuk memeriksa hasil
konversi, atau bila perintah ZPL-nya ingin dikirim sendiri lewat `/api/print/raw`.

```bash
curl -X POST http://127.0.0.1:18212/api/print/pdf-to-zpl \
  -H "Content-Type: application/json" \
  -d '{"pdf_data":"JVBERi0xLjcK...","options":{"dpi":203}}'
```

```json
{
  "status": "success",
  "labels": 1,
  "pdf_bytes": 3267,
  "zpl_bytes": 24057,
  "zpl": "^XA^PW480^LL200^LH0,0^PON^FO0,0^GFA,12000,12000,60,0000...^FS^XZ"
}
```

Menerima parameter yang sama dengan `/api/print/pdf` (`pdf_data`, `file_content`,
`url`, `options`).

---

## 8.8 Bentuk Perintah ZPL yang Dihasilkan

```
^XA                                  mulai label
^PW480                               lebar cetak (dot)
^LL200                               panjang label (dot)
^LH0,0                               titik asal
^PON                                 orientasi (dari options.rotate)
^FO0,0                               posisi gambar
^GFA,12000,12000,60,<hex>            grafik: total,total,byte per baris,data
^FS                                  akhir field
^PQ3                                 jumlah cetak (hanya bila qty > 1)
^XZ                                  akhir label
```

PDF multi-halaman menghasilkan beberapa blok `^XA ... ^XZ` berurutan — satu
label per halaman.

Ukuran perintah kira-kira **2 karakter hex per byte raster**: label 60 × 25 mm
pada 203 dpi ≈ 12.000 byte raster ≈ 24 KB teks ZPL.

---

## 8.9 Masalah pada Mode ZPL

| Gejala | Penyebab | Solusi |
|--------|----------|--------|
| Hasil cetak hitam semua | Polaritas atau latar transparan | Render PDF dengan latar putih; turunkan `threshold` |
| Teks tipis / putus-putus | Ambang terlalu rendah | Naikkan `threshold` ke 176 atau 210, atau naikkan `darkness` |
| Barcode tidak bisa dipindai | Dithering menyebar titik | Pastikan `dither: false` (bawaan); pakai 203 dpi persis |
| Label tercetak ~1,5× terlalu besar | DPI render 300 di printer 203 | Set `dpi: 203` |
| Label terpotong di kanan | Lebar PDF melebihi lebar printer | Sesuaikan ukuran kertas dompdf dengan lebar label fisik |
| Cetakan berputar 90° | `setPaper(..., 'landscape')` menukar sisi | Hilangkan `'landscape'`, atau pakai `options.rotate: "R"` |
| `Ukuran label ... melebihi batas aman 4096 dot` | DPI terlalu tinggi untuk halaman sebesar itu | Turunkan `dpi` |
| `Data yang dikirim adalah HTML, bukan PDF` | HTML di-Base64-kan langsung | Render HTML menjadi PDF dulu — lihat [02-html-ke-base64.md](02-html-ke-base64.md) |
| `PyMuPDF (fitz) tidak tersedia` | Dependensi hilang | `pip install pymupdf` |

---

## 8.10 Gambar ke ZPL

`/api/print/image` mengenali `mode` yang sama, sehingga tangkapan `html2canvas`
bisa langsung dicetak ke printer label:

```js
const canvas = await html2canvas(document.querySelector('#label'), { scale: 3 });

await fetch('http://127.0.0.1:18212/api/print/image', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        printer:    'asset_label',
        image_data: canvas.toDataURL('image/png'),
        doc_name:   'Label_Canvas',
        options:    { mode: 'zpl', threshold: 128, label_width_dots: 480 }
    })
});
```

`label_width_dots` mengubah skala gambar ke lebar label sebelum dikonversi —
berguna karena ukuran canvas jarang pas dengan lebar printer.

---

## 8.11 Printer Selain ZPL

| Bahasa printer | Dukungan mode raster |
|----------------|----------------------|
| ZPL II (Zebra, Godex GZPL/EZPL) | ✅ Didukung |
| ESC/POS (struk thermal) | ❌ Belum. Pakai `/api/print/raw`, lihat [04-raw-escpos-zpl.md](04-raw-escpos-zpl.md) |
| TSPL (TSC) | ❌ Belum. Kirim perintah `BITMAP` sendiri lewat `/api/print/raw` |
| Laser / inkjet | Tidak perlu — jalur driver sudah bekerja baik |
