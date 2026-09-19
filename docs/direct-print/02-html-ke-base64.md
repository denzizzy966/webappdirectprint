# 2. Cetak dari HTML yang Dikonversi ke Base64

Panduan ini menjawab kebutuhan: **"Saya punya HTML (faktur / label / surat jalan),
saya ubah jadi Base64, lalu saya kirim ke direct print."**

---

## 2.1 Aturan Dasar yang Wajib Dipahami

> ⛔ **HTML mentah yang di-Base64-kan TIDAK bisa dicetak lewat `/api/print/pdf`.**

Bridge memeriksa empat byte pertama hasil decode. Bila bukan `%PDF-`, permintaan
ditolak dengan HTTP 500 dan pesan yang menyebut penyebabnya:

```
Data yang dikirim adalah HTML, bukan PDF. Render HTML menjadi PDF terlebih
dahulu (dompdf, html2pdf.js, atau jsPDF), baru kirim Base64 hasilnya.
```

Pemeriksaan ini sengaja ada karena PyMuPDF versi baru diam-diam ikut merender
HTML pada halaman bawaan 400 × 600 pt — ukuran yang tidak ada hubungannya dengan
label 60 × 25 mm, sehingga hasil cetaknya pasti salah. Lebih baik ditolak dengan
jelas daripada menghabiskan gulungan label.

Contoh yang **SALAH**:

```js
// ❌ JANGAN — ini mem-Base64-kan teks HTML, bukan PDF
const b64 = btoa(document.getElementById('struk').innerHTML);
await HardwareBridge.printPdf('asset_label', b64);
```

HTML harus **dirender** menjadi salah satu format yang dimengerti bridge:

| Target render | Endpoint | Cocok untuk |
|---------------|----------|-------------|
| HTML → **PDF** (di browser) | `/api/print/pdf` | Label, faktur, surat jalan — **paling direkomendasikan** |
| HTML → **PDF** (di server Laravel/PHP) | `/api/print/pdf` (Base64 atau URL) | Dokumen resmi, arsip, cetak ulang |
| HTML → **PNG** (canvas) | `/api/print/image` | Struk/label sederhana, tampilan harus sama persis dengan layar |
| Teks → **ESC/POS** | `/api/print/raw` | Struk kasir thermal (paling cepat & paling hemat) |

> 🏷️ **Printer label (Godex GZPL, Zebra)?** Setelah HTML menjadi PDF, kirim
> dengan `options: { mode: "zpl", dpi: 203 }` supaya PDF-nya diubah menjadi
> perintah ZPL raster dan dikirim lewat jalur RAW — jalur yang jauh lebih andal
> pada printer label. Lihat [08-printer-label-zpl.md](08-printer-label-zpl.md).

---

## 2.2 Metode A — HTML ke PDF di Browser dengan `html2pdf.js` ✅ Rekomendasi

Paling praktis: tidak butuh perubahan di sisi server sama sekali.

### Pemasangan

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
<script src="http://127.0.0.1:18212/api/download/hardware-bridge.js"></script>
```

> Jika PC klien offline, unduh `html2pdf.bundle.min.js` dan taruh di folder aset
> aplikasi web Anda.

### Fungsi Siap Pakai

```html
<div id="areaCetak" style="width:60mm; font-family:Arial, sans-serif;">
  <h3 style="margin:0;">PT AMANI PRODUKSI</h3>
  <div>No. Produksi : PRD-2026-0012</div>
  <div>Item        : Kopi Arabika 250g</div>
  <div>Berat       : 250,00 g</div>
  <div>Tanggal     : 19/09/2026</div>
</div>

<button onclick="cetakHtmlKeLabel()">🖨️ Cetak Label</button>

<script>
/**
 * Render elemen HTML menjadi PDF, ubah ke Base64, kirim ke direct print.
 *
 * @param {string} selector  Selector elemen HTML yang akan dicetak
 * @param {string} printer   Nama printer fisik ATAU alias pool (mis. 'asset_label')
 * @param {object} kertas    Ukuran kertas dalam milimeter { lebar, tinggi }
 */
async function cetakHtmlSebagaiPdf(selector, printer, kertas = { lebar: 60, tinggi: 25 }) {
    const el = document.querySelector(selector);
    if (!el) throw new Error('Elemen ' + selector + ' tidak ditemukan');

    // 1. HTML -> PDF (objek jsPDF) -> string data URI Base64
    const worker = html2pdf().set({
        margin: 0,
        image:  { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 3, useCORS: true, backgroundColor: '#ffffff' },
        jsPDF:  {
            unit:        'mm',
            format:      [kertas.lebar, kertas.tinggi],
            orientation: kertas.lebar >= kertas.tinggi ? 'landscape' : 'portrait'
        }
    }).from(el);

    const base64Pdf = await worker.outputPdf('datauristring');
    // hasil: "data:application/pdf;filename=generated.pdf;base64,JVBERi0xLjQK..."

    // 2. Kirim ke Hardware Bridge
    const res = await fetch('http://127.0.0.1:18212/api/print/pdf', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            printer:  printer,
            pdf_data: base64Pdf,          // data URI diterima apa adanya
            doc_name: 'Label_HTML_' + Date.now(),
            options:  { dpi: 203 }        // 203 dpi = printer thermal label
        })
    });

    const json = await res.json();
    if (!res.ok || json.status !== 'success') {
        throw new Error(json.detail || json.message || 'Gagal mencetak');
    }
    return json.result;
}

async function cetakHtmlKeLabel() {
    try {
        const r = await cetakHtmlSebagaiPdf('#areaCetak', 'asset_label', { lebar: 60, tinggi: 25 });
        alert('✅ Terkirim ke printer: ' + r.printer);
    } catch (e) {
        alert('❌ ' + e.message);
    }
}
</script>
```

### Catatan `outputPdf()`

| Argumen | Hasil | Siap dikirim? |
|---------|-------|---------------|
| `'datauristring'` | `data:application/pdf;filename=...;base64,JVBER...` | ✅ Ya, bridge memotong di `;base64,` |
| `'datauri'` | sama seperti di atas | ✅ Ya |
| `'blob'` | objek `Blob` | Perlu dikonversi dulu (lihat §2.5) |
| `'arraybuffer'` | `ArrayBuffer` | Perlu dikonversi dulu (lihat §2.5) |

---

## 2.3 Metode B — HTML ke PDF dengan jsPDF + html2canvas

Dipakai bila Anda butuh kontrol penuh atas posisi/ukuran gambar di halaman PDF.

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.2/jspdf.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>

<script>
async function cetakHtmlJsPdf(selector, printer) {
    const el = document.querySelector(selector);

    // 1. HTML -> canvas -> PNG data URI
    const canvas = await html2canvas(el, { scale: 3, backgroundColor: '#ffffff' });
    const imgData = canvas.toDataURL('image/png');

    // 2. Susun PDF A4 potret
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' });

    const lebarHal  = pdf.internal.pageSize.getWidth();   // 210 mm
    const tinggiImg = (canvas.height * lebarHal) / canvas.width;
    pdf.addImage(imgData, 'PNG', 0, 0, lebarHal, tinggiImg);

    // 3. PDF -> Base64 murni (tanpa prefiks)
    const base64 = pdf.output('datauristring').split(';base64,')[1];

    // 4. Kirim dengan prefiks eksplisit agar deteksi bridge pasti benar
    return await HardwareBridge.printPdf(
        printer,
        'base64:' + base64,
        'Faktur_HTML',
        { dpi: 300 }                       // 300 dpi untuk printer laser/inkjet A4
    );
}
</script>
```

> ℹ️ **Kenapa memakai prefiks `base64:`?**
> Bridge mengenali empat format. Memberi prefiks eksplisit (`base64:` atau data URI
> lengkap) menghilangkan ketergantungan pada heuristik "panjang lebih dari 80 karakter"
> untuk Base64 polos, dan membuat pesan galat lebih mudah dibaca.

---

## 2.4 Metode C — HTML ke PDF di Server (Laravel / dompdf / wkhtmltopdf) ✅ Produksi

Paling andal untuk dokumen resmi: hasil cetak identik di semua PC, tidak
bergantung font/zoom browser operator.

### Sisi Laravel (controller)

```php
<?php
namespace App\Http\Controllers;

use Barryvdh\DomPDF\Facade\Pdf;

class CetakProduksiController extends Controller
{
    /** Kembalikan PDF sebagai Base64 untuk dikirim ke Hardware Bridge. */
    public function base64(string $noProduksi)
    {
        $pdf = Pdf::loadView('produksi.label', [
            'produksi' => \App\Models\Produksi::where('no_produksi', $noProduksi)->firstOrFail(),
        ])->setPaper([0, 0, 170.08, 70.87], 'landscape'); // 60 x 25 mm dalam satuan pt

        return response()->json([
            'nama'   => $noProduksi,
            'base64' => base64_encode($pdf->output()),
        ]);
    }
}
```

```php
// routes/web.php
Route::get('/produksi/{no}/label-base64', [CetakProduksiController::class, 'base64']);
```

### Sisi Browser

```js
async function cetakLabelDariServer(noProduksi, printer = 'asset_label') {
    // 1. Ambil Base64 dari server aplikasi (bukan dari bridge)
    const r = await fetch('/produksi/' + encodeURIComponent(noProduksi) + '/label-base64', {
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'          // ikut sertakan sesi login Laravel
    });
    if (!r.ok) throw new Error('Gagal mengambil PDF dari server: HTTP ' + r.status);
    const { base64 } = await r.json();

    // 2. Kirim ke bridge di PC operator
    const res = await fetch('http://127.0.0.1:18212/api/print/pdf', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            printer:  printer,
            pdf_data: 'base64:' + base64,
            doc_name: 'Label_' + noProduksi,
            options:  { dpi: 203 }
        })
    });
    const json = await res.json();
    if (!res.ok || json.status !== 'success') {
        throw new Error(json.detail || 'Gagal mencetak');
    }
    return json.result;
}
```

> 💡 **Kapan pakai Base64, kapan pakai URL?**
> Gunakan **Base64** bila berkas PDF berada di balik login/sesi (browser yang punya
> cookie, bukan bridge). Gunakan **URL** bila berkas bisa diambil tanpa autentikasi
> dari jaringan lokal → lihat [03-pdf-dari-url.md](03-pdf-dari-url.md).

---

## 2.5 Utilitas Konversi Base64 (Blob / File / ArrayBuffer)

Tiga sumber PDF yang umum ditemui, beserta cara mengubahnya ke Base64:

```js
/** Blob atau File (misal hasil <input type="file"> atau pdf.output('blob')) */
function blobKeBase64(blob) {
    return new Promise((resolve, reject) => {
        const fr = new FileReader();
        fr.onload  = () => resolve(fr.result);   // "data:application/pdf;base64,JVBER..."
        fr.onerror = reject;
        fr.readAsDataURL(blob);
    });
}

/** ArrayBuffer / Uint8Array — aman untuk berkas besar (dipotong per 32 KB) */
function bufferKeBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let biner = '';
    const CHUNK = 0x8000;                        // 32768, hindari "Maximum call stack size exceeded"
    for (let i = 0; i < bytes.length; i += CHUNK) {
        biner += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
    }
    return btoa(biner);
}

/** Unduh PDF lewat browser (ikut sesi login), lalu kirim ke bridge sebagai Base64 */
async function urlKeBase64(url) {
    const r = await fetch(url, { credentials: 'include' });
    if (!r.ok) throw new Error('HTTP ' + r.status + ' saat mengambil ' + url);
    return await blobKeBase64(await r.blob());
}
```

Contoh gabungan — ambil PDF terproteksi sesi lalu cetak:

```js
const dataUri = await urlKeBase64('/produksi/PRD-2026-0012/label.pdf');
await HardwareBridge.printPdf('asset_label', dataUri, 'Label_PRD-2026-0012', { dpi: 203 });
```

---

## 2.6 Metode D — HTML ke Gambar (`/api/print/image`)

Bila hasil cetak harus persis seperti tampilan layar dan tidak perlu format PDF.

```js
async function cetakHtmlSebagaiGambar(selector, printer) {
    const canvas = await html2canvas(document.querySelector(selector), {
        scale: 3,
        backgroundColor: '#ffffff'
    });

    const res = await fetch('http://127.0.0.1:18212/api/print/image', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            printer:    printer,
            image_data: canvas.toDataURL('image/png'),   // data:image/png;base64,...
            doc_name:   'Cetak_Gambar_HTML'
        })
    });
    const json = await res.json();
    if (!res.ok || json.status !== 'success') throw new Error(json.detail || 'Gagal');
    return json.result;
}
```

Format `image_data` yang diterima: data URI (`data:image/png;base64,...`),
prefiks `base64:...`, atau Base64 polos.

---

## 2.7 Metode E — Struk Thermal: HTML ke ESC/POS (`/api/print/raw`)

Untuk struk kasir 58/80 mm, merender HTML ke PDF adalah pemborosan. Kirim
perintah ESC/POS langsung — jauh lebih cepat dan hasilnya lebih tajam.

```js
const ESC = '\x1B', GS = '\x1D';
const baris = (kiri, kanan, lebar = 42) =>
    kiri + ' '.repeat(Math.max(1, lebar - kiri.length - kanan.length)) + kanan + '\n';

function strukDari(data) {
    let s = '';
    s += ESC + '@';                       // inisialisasi printer
    s += ESC + 'a' + '\x01';              // rata tengah
    s += ESC + 'E' + '\x01' + 'PT AMANI PRODUKSI\n' + ESC + 'E' + '\x00';
    s += 'Jl. Raya Produksi No. 25\n';
    s += ESC + 'a' + '\x00';              // rata kiri
    s += '-'.repeat(42) + '\n';
    data.item.forEach(it => {
        s += it.nama + '\n';
        s += baris('  ' + it.qty + ' x ' + it.harga.toLocaleString('id-ID'),
                   (it.qty * it.harga).toLocaleString('id-ID'));
    });
    s += '-'.repeat(42) + '\n';
    s += baris('TOTAL', data.total.toLocaleString('id-ID'));
    s += '\n\n\n';
    s += GS + 'V' + '\x00';               // potong kertas penuh
    return s;
}

await HardwareBridge.printRaw('receipt', strukDari(dataTransaksi), 'Struk_Kasir');
```

Detail lengkap perintah ESC/POS & ZPL: [04-raw-escpos-zpl.md](04-raw-escpos-zpl.md).

---

## 2.8 Perbandingan Metode

| Metode | Kecepatan | Ketepatan Tata Letak | Butuh Ubah Server | Cocok untuk |
|--------|-----------|----------------------|-------------------|-------------|
| A. html2pdf.js | Sedang | Baik | Tidak | Label & faktur umum |
| B. jsPDF + html2canvas | Sedang | Baik (kontrol penuh) | Tidak | Tata letak khusus |
| C. dompdf / wkhtmltopdf (server) | Lambat (+1 request) | **Terbaik & konsisten** | Ya | Dokumen resmi produksi |
| D. html2canvas ke image | Cepat | Persis seperti layar | Tidak | Struk/label sederhana |
| E. ESC/POS RAW | **Tercepat** | Terbatas teks | Tidak | Struk kasir thermal |

---

## 2.9 Batas Ukuran Data Base64

| Hal | Nilai | Catatan |
|-----|-------|---------|
| Pembengkakan Base64 | +33% | PDF 1 MB menjadi ~1,37 MB string JSON |
| Batas ukuran body di bridge | Tidak dibatasi eksplisit | Dibatasi RAM PC klien |
| Timeout helper `HardwareBridge.api()` | 8 detik | Ubah lewat argumen `timeoutMs` bila PDF besar |
| Timeout respons WebSocket SDK | 10 detik | Untuk PDF besar, gunakan jalur HTTP (`fetch`) |

Untuk PDF di atas ~3 MB, lebih baik pakai **URL** daripada Base64 →
[03-pdf-dari-url.md](03-pdf-dari-url.md).

---

## 2.10 Daftar Periksa Sebelum Melapor Masalah

- [ ] Base64 yang dikirim benar-benar **PDF** — hasil decode diawali `%PDF-`.
      Uji cepat di browser: `window.open(dataUri)` harus menampilkan PDF.
- [ ] Prefiks dipakai eksplisit (`data:application/pdf;base64,` atau `base64:`).
- [ ] Tidak ada karakter di luar alfabet Base64. Spasi/newline dibuang otomatis
      oleh bridge, tetapi karakter lain tetap menggagalkan decode.
- [ ] `dpi` ditaruh di dalam `options`, bukan di level atas JSON.
- [ ] Ukuran kertas label sudah diatur di **driver printer Windows**.
- [ ] Base64-nya sudah diuji tempel di **Dashboard Bridge → Sandbox → Cetak Base64 PDF**
      (`http://127.0.0.1:18212`) untuk memastikan datanya valid sebelum menyalahkan
      kode aplikasi.
