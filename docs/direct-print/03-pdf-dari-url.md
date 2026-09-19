# 3. Cetak PDF Langsung dari URL Server

Panduan ini menjawab kebutuhan konkret:

```js
'http://192.168.3.25/produksi/ProduksiPDF/' + data + '.pdf'
```

Yaitu berkas PDF yang sudah tersedia di server internal dan tinggal dicetak
tanpa dialog di PC operator produksi.

---

## 3.1 Yang Paling Penting: Siapa yang Mengunduh Berkasnya?

> 🔑 **Bridge (Python) yang mengunduh PDF dari `192.168.3.25`, bukan browser.**

```
Browser                Hardware Bridge (PC operator)          Server 192.168.3.25
   │                            │                                      │
   │ POST /api/print/pdf        │                                      │
   │ { pdf_data: "http://..." } │                                      │
   ├───────────────────────────►│                                      │
   │                            │ requests.get(url, timeout=15)        │
   │                            ├─────────────────────────────────────►│
   │                            │◄─────────────────────────────────────┤
   │                            │        bytes PDF                     │
   │                            │                                      │
   │                            │ PyMuPDF → GDI → 🖨️ Printer           │
   │◄───────────────────────────┤                                      │
   │  { status: "success" }     │                                      │
```

Konsekuensinya:

| Hal | Akibat |
|-----|--------|
| **CORS** | Tidak berlaku. Tidak perlu mengatur `Access-Control-Allow-Origin` pada `192.168.3.25` |
| **Jangkauan jaringan** | **PC operator** harus bisa menjangkau `192.168.3.25`, walaupun browser bisa |
| **Login / sesi** | Cookie sesi browser **tidak ikut terkirim**. URL harus bisa diakses tanpa autentikasi |
| **Ukuran berkas** | Tidak dibatasi Base64, jauh lebih efisien untuk PDF besar |
| **Mixed content** | Unduhan HTTP oleh bridge aman. Yang tetap kena aturan mixed content adalah panggilan browser ke `http://127.0.0.1:18212` (lihat §3.7) |

---

## 3.2 Contoh Minimal

```js
const noProduksi = 'PRD-2026-0012';

const res = await fetch('http://127.0.0.1:18212/api/print/pdf', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        printer:  'asset_label',
        pdf_data: 'http://192.168.3.25/produksi/ProduksiPDF/' + noProduksi + '.pdf',
        doc_name: 'Produksi_' + noProduksi,
        options:  { dpi: 203 }
    })
});

const json = await res.json();
console.log(json.status, json.result || json.detail);
```

Dengan SDK `hardware-bridge.js` (lebih ringkas, sudah ada fallback port 12212):

```js
await HardwareBridge.printPdf(
    'asset_label',
    'http://192.168.3.25/produksi/ProduksiPDF/' + noProduksi + '.pdf',
    'Produksi_' + noProduksi,
    { dpi: 203 }
);
```

---

## 3.3 Fungsi Produksi Siap Pakai

Versi lengkap dengan penyandian URL, validasi, percobaan ulang, dan pesan galat
berbahasa Indonesia. Salin apa adanya ke aplikasi web Anda.

```js
/**
 * Cetak PDF produksi langsung dari server internal 192.168.3.25.
 *
 * @param {string} noProduksi  Nomor produksi, contoh 'PRD-2026-0012'
 * @param {object} opsi        { printer, dpi, basis, percobaan, jeda, docName }
 * @returns {Promise<object>}  Objek result dari bridge
 */
async function cetakPdfProduksi(noProduksi, opsi = {}) {
    const {
        printer   = 'asset_label',                                   // alias pool atau nama printer fisik
        dpi       = 203,                                             // 203 = thermal label, 300 = laser A4
        basis     = 'http://192.168.3.25/produksi/ProduksiPDF/',
        percobaan = 2,                                               // jumlah percobaan ulang bila gagal
        jeda      = 1200,                                            // jeda antar percobaan (ms)
        docName   = null
    } = opsi;

    if (!noProduksi) throw new Error('Nomor produksi kosong.');

    // encodeURIComponent penting bila nomor mengandung spasi, '/', '#', atau '&'
    const url = basis + encodeURIComponent(noProduksi) + '.pdf';

    let galatTerakhir = null;

    for (let i = 1; i <= percobaan; i++) {
        try {
            const ctrl  = new AbortController();
            const timer = setTimeout(() => ctrl.abort(), 30000);   // bridge sendiri timeout 15 dtk saat mengunduh

            const res = await fetch('http://127.0.0.1:18212/api/print/pdf', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                signal:  ctrl.signal,
                body: JSON.stringify({
                    printer:  printer,
                    pdf_data: url,
                    doc_name: docName || ('Produksi_' + noProduksi),
                    options:  { dpi: dpi }
                })
            });
            clearTimeout(timer);

            const json = await res.json();

            if (res.ok && json.status === 'success') {
                return json.result;              // { success, printer, job_id, message, bytes_sent }
            }

            // HTTP 500 dari bridge: pesan asli ada di json.detail
            galatTerakhir = new Error(json.detail || json.message || ('HTTP ' + res.status));

        } catch (e) {
            galatTerakhir = (e.name === 'AbortError')
                ? new Error('Bridge tidak merespons dalam 30 detik.')
                : new Error('Hardware Bridge tidak aktif di 127.0.0.1:18212 — ' + e.message);
        }

        if (i < percobaan) await new Promise(r => setTimeout(r, jeda));
    }

    throw galatTerakhir;
}
```

### Pemakaian

```js
document.getElementById('btnCetak').addEventListener('click', async () => {
    const no = document.getElementById('noProduksi').value.trim();
    try {
        const r = await cetakPdfProduksi(no, { printer: 'asset_label', dpi: 203 });
        alert('✅ Tercetak di ' + r.printer + ' (' + r.bytes_sent + ' bytes)');
    } catch (e) {
        alert('❌ Gagal cetak: ' + e.message);
    }
});
```

---

## 3.4 Cetak Banyak Dokumen (Batch)

Kirim **berurutan** (`await` di dalam loop), bukan `Promise.all`. Spooler
memproses satu job per DC, dan urutan cetak fisik lebih mudah ditebak.

```js
/**
 * @param {string[]} daftarNo  contoh: ['PRD-0001', 'PRD-0002', 'PRD-0003']
 */
async function cetakBatchProduksi(daftarNo, opsi = {}) {
    const hasil = { sukses: [], gagal: [] };

    for (const no of daftarNo) {
        try {
            await cetakPdfProduksi(no, opsi);
            hasil.sukses.push(no);
        } catch (e) {
            hasil.gagal.push({ no: no, pesan: e.message });
        }
        // beri jeda agar antrean printer label tidak menumpuk
        await new Promise(r => setTimeout(r, 400));
    }

    console.table(hasil.gagal);
    return hasil;
}
```

### Cetak Satu Dokumen Beberapa Rangkap

Tidak ada parameter `qty` pada endpoint HTTP — panggil berulang:

```js
async function cetakRangkap(noProduksi, qty = 2, opsi = {}) {
    for (let i = 0; i < qty; i++) {
        await cetakPdfProduksi(noProduksi, {
            ...opsi,
            docName: 'Produksi_' + noProduksi + '_copy' + (i + 1)
        });
    }
}
```

> ℹ️ Parameter `qty` **tersedia** pada jalur WebSocket (kompatibilitas
> `whb_print.js` ERPNext) — lihat [06-referensi-api-print.md](06-referensi-api-print.md) §6.4.

---

## 3.5 Menyusun URL dengan Benar

Pola lama `'http://192.168.3.25/produksi/ProduksiPDF/' + data + '.pdf'` aman
selama `data` hanya berisi huruf, angka, `-`, dan `_`. Begitu ada spasi atau
karakter khusus, URL rusak dan bridge melaporkan `404`.

```js
// ❌ Rapuh
const url = 'http://192.168.3.25/produksi/ProduksiPDF/' + data + '.pdf';

// ✅ Aman
const url = 'http://192.168.3.25/produksi/ProduksiPDF/'
          + encodeURIComponent(data) + '.pdf';

// ✅ Lebih rapi dengan URL API — sekaligus memvalidasi bentuk URL
const url = new URL(
    'produksi/ProduksiPDF/' + encodeURIComponent(data) + '.pdf',
    'http://192.168.3.25/'
).href;
```

Perbandingan hasil:

| Nilai `data` | Tanpa encode | Dengan `encodeURIComponent` |
|--------------|--------------|------------------------------|
| `PRD-2026-0012` | `.../PRD-2026-0012.pdf` ✅ | `.../PRD-2026-0012.pdf` ✅ |
| `PRD 2026 12` | `.../PRD 2026 12.pdf` ❌ | `.../PRD%202026%2012.pdf` ✅ |
| `A/B-001` | `.../A/B-001.pdf` ❌ (jadi subfolder) | `.../A%2FB-001.pdf` ✅ |
| `LOT#5` | `.../LOT` ❌ (`#` memotong URL) | `.../LOT%235.pdf` ✅ |

### Simpan Alamat Basis di Satu Tempat

Jangan menyebar IP `192.168.3.25` ke seluruh berkas JavaScript. Letakkan di satu
konstanta atau di Blade agar gampang diganti saat server pindah.

```html
<!-- Laravel Blade -->
<meta name="pdf-base-url" content="{{ config('app.pdf_base_url') }}">
```

```js
const PDF_BASE = document.querySelector('meta[name="pdf-base-url"]')?.content
              || 'http://192.168.3.25/produksi/ProduksiPDF/';
```

---

## 3.6 Memastikan Server PDF Bisa Dijangkau

Jalankan perintah ini **di PC operator tempat bridge berjalan** (bukan di server
aplikasi, bukan di PC Anda).

### Windows PowerShell

```powershell
# 1. Server hidup dan port 80 terbuka?
Test-NetConnection 192.168.3.25 -Port 80

# 2. Berkas PDF benar-benar ada dan bisa diunduh?
Invoke-WebRequest -Uri "http://192.168.3.25/produksi/ProduksiPDF/PRD-2026-0012.pdf" `
                  -OutFile "$env:TEMP\uji.pdf"
Get-Item "$env:TEMP\uji.pdf" | Select-Object Length

# 3. Isinya benar PDF? (empat byte pertama harus %PDF)
Get-Content "$env:TEMP\uji.pdf" -Encoding Byte -TotalCount 4 |
    ForEach-Object { [char]$_ }
```

### Linux

```bash
curl -I http://192.168.3.25/produksi/ProduksiPDF/PRD-2026-0012.pdf
curl -s http://192.168.3.25/produksi/ProduksiPDF/PRD-2026-0012.pdf | head -c 4   # harus %PDF
```

### Uji Langsung Lewat Bridge (tanpa menyentuh aplikasi web)

```powershell
$body = @{
    printer  = "asset_label"
    pdf_data = "http://192.168.3.25/produksi/ProduksiPDF/PRD-2026-0012.pdf"
    doc_name = "Uji_URL"
    options  = @{ dpi = 203 }
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:18212/api/print/pdf" `
                  -Method Post -ContentType "application/json" -Body $body
```

```bash
curl -X POST http://127.0.0.1:18212/api/print/pdf \
  -H "Content-Type: application/json" \
  -d '{"printer":"asset_label","pdf_data":"http://192.168.3.25/produksi/ProduksiPDF/PRD-2026-0012.pdf","doc_name":"Uji_URL","options":{"dpi":203}}'
```

Atau lewat **Dashboard Bridge** → `http://127.0.0.1:18212` → kartu **Sandbox**
→ tab **Cetak dari Berkas / URL** → tempel URL-nya → **Cetak**.

---

## 3.7 Bila Aplikasi Web Anda Berjalan di HTTPS

Browser modern memblokir permintaan `http://127.0.0.1:18212` dari halaman
`https://`. Tiga opsi, urut dari yang paling praktis:

1. **Sajikan halaman produksi lewat HTTP** di jaringan internal (paling sederhana,
   sesuai dengan server PDF yang juga HTTP).
2. **Izinkan pengecualian di Chrome/Edge** untuk domain aplikasi:
   `chrome://settings/content/insecureContent` → **Add** → masukkan asal aplikasi Anda.
3. **Pasang sertifikat** pada bridge dan akses lewat `https://127.0.0.1:18212`
   (butuh sertifikat yang dipercaya di setiap PC klien).

> Catatan: pembatasan ini **hanya** mengenai panggilan browser → bridge.
> Unduhan bridge → `http://192.168.3.25` tidak terpengaruh sama sekali.

---

## 3.8 Batasan Jalur URL yang Perlu Diketahui

| Batasan | Nilai / Perilaku | Solusi |
|---------|------------------|--------|
| Timeout unduh | **15 detik** (tetap, `requests.get(..., timeout=15)`) | Perkecil PDF, atau kirim sebagai Base64 dari browser |
| Autentikasi | Tidak ada header/cookie/Basic Auth yang dikirim | Buka akses folder PDF untuk LAN, atau pakai Base64 |
| Sertifikat HTTPS | Mengikuti perilaku bawaan `requests` — sertifikat self-signed **ditolak** | Gunakan HTTP di LAN, atau pasang CA di PC klien |
| Pengalihan (redirect) | Diikuti otomatis oleh `requests` | — |
| Skema `file://` | Tidak dikenali sebagai URL | Kirim path lokal langsung, mis. `C:\\share\\label.pdf` |
| Path UNC jaringan | Didukung sebagai path berkas | `\\\\192.168.3.25\\produksi\\ProduksiPDF\\X.pdf` |
| Jenis konten | Tidak diperiksa | Server harus benar-benar mengembalikan PDF, bukan halaman HTML "404" |

### Jalur Alternatif: Berbagi Folder (UNC)

Bila HTTP tidak tersedia namun folder di-share:

```js
await HardwareBridge.printPdf(
    'asset_label',
    '\\\\192.168.3.25\\produksi\\ProduksiPDF\\PRD-2026-0012.pdf',
    'Produksi_PRD-2026-0012'
);
```

Bridge akan membacanya lewat cabang "path berkas". Pastikan akun Windows yang
menjalankan bridge punya izin baca ke share tersebut.

---

## 3.9 Contoh Integrasi Laravel Blade

```blade
{{-- resources/views/produksi/index.blade.php --}}
<meta name="pdf-base-url" content="http://192.168.3.25/produksi/ProduksiPDF/">
<script src="http://127.0.0.1:18212/api/download/hardware-bridge.js"></script>

<table class="table">
  @foreach ($daftarProduksi as $p)
    <tr>
      <td>{{ $p->no_produksi }}</td>
      <td>{{ $p->nama_item }}</td>
      <td>
        <button type="button"
                class="btn btn-sm btn-primary btn-cetak"
                data-no="{{ $p->no_produksi }}">🖨️ Cetak Label</button>
      </td>
    </tr>
  @endforeach
</table>

<script>
const PDF_BASE = document.querySelector('meta[name="pdf-base-url"]').content;

document.querySelectorAll('.btn-cetak').forEach(btn => {
    btn.addEventListener('click', async () => {
        const no = btn.dataset.no;
        const labelAsli = btn.textContent;

        btn.disabled = true;
        btn.textContent = '⏳ Mencetak...';
        try {
            const r = await HardwareBridge.printPdf(
                'asset_label',
                PDF_BASE + encodeURIComponent(no) + '.pdf',
                'Produksi_' + no,
                { dpi: 203 }
            );
            if (r.status !== 'success') throw new Error(r.detail || r.message || 'Gagal');
            HardwareBridge.toast('✅ Label ' + no + ' terkirim ke printer', '#16a34a');
        } catch (e) {
            HardwareBridge.toast('❌ ' + e.message, '#cd2b2b');
        } finally {
            btn.disabled = false;
            btn.textContent = labelAsli;
        }
    });
});
</script>
```

---

## 3.10 Galat Umum pada Jalur URL

| Pesan `detail` dari bridge | Penyebab | Solusi |
|----------------------------|----------|--------|
| `Gagal mengunduh PDF dari URL: 404 Client Error` | Berkas belum dibuat / nama salah / huruf besar-kecil tidak sama | Buka URL-nya di browser PC operator |
| `Gagal mengunduh PDF dari URL: ... Read timed out` | PDF terlalu besar atau server lambat (batas 15 detik) | Perkecil PDF, atau kirim Base64 dari browser |
| `Gagal mengunduh PDF dari URL: ... Connection refused` | PC operator tidak bisa menjangkau `192.168.3.25` | Cek VLAN, firewall, dan `Test-NetConnection` |
| `Gagal mengunduh PDF dari URL: 401/403` | Folder PDF butuh login | Buka akses untuk LAN, atau pakai Base64 (§2.4) |
| `Gagal mencetak PDF ke '...': Failed to open stream` | Server mengembalikan HTML (halaman galat), bukan PDF | Periksa 4 byte pertama respons harus `%PDF` |
| `Failed to fetch` di konsol browser | Bridge mati, atau halaman HTTPS memblokir localhost | Jalankan bridge, lalu lihat §3.7 |

Daftar lengkap: [07-troubleshooting-print.md](07-troubleshooting-print.md).
