# 💻 Referensi SDK JavaScript (`hardware-bridge.js`)

SDK tunggal untuk cetak langsung **dan** membaca timbangan dari browser.
Berkas: [`static/js/hardware-bridge.js`](../static/js/hardware-bridge.js).

---

## 1. Pemasangan

```html
<!-- Dari bridge yang berjalan di PC klien -->
<script src="http://127.0.0.1:18212/api/download/hardware-bridge.js"></script>

<!-- Atau salin ke folder aset aplikasi Anda (disarankan untuk produksi) -->
<script src="/js/hardware-bridge.js"></script>
```

Mendukung UMD: AMD, CommonJS, dan global `window`. Saat dimuat sebagai global,
`window.TimbanganSvc` didaftarkan sebagai alias supaya kode lama yang memakai
`TimbanganSvc` tetap jalan tanpa perubahan.

```js
import HardwareBridge from './hardware-bridge.js';   // bundler
const HardwareBridge = require('./hardware-bridge'); // CommonJS
```

---

## 2. Konfigurasi

```js
HardwareBridge.configure({
    host:      '127.0.0.1',
    port:      18212,
    scalePort: 12212,          // hanya bila timbangan memakai port terpisah
    serviceUrl:'http://127.0.0.1:18212',
    scaleUrl:  'http://127.0.0.1:12212'
});

HardwareBridge.setPort(18212);
HardwareBridge.setScalePort(12212);
```

| Properti | Bawaan | Keterangan |
|----------|--------|------------|
| `HardwareBridge.SERVICE_URL` | `http://127.0.0.1:18212` | Alamat dasar bridge |
| `HardwareBridge.SCALE_SERVICE_URL` | `null` | Alamat khusus timbangan bila portnya dipisah |
| `HardwareBridge.MAX_AGE_S` | `5` | Umur maksimal data berat sebelum dianggap basi |
| `HardwareBridge.STABLE_TIMEOUT_S` | `10` | Timeout bawaan pembacaan stabil |
| `HardwareBridge.onError` | `null` | Fungsi penangan galat. Bila `null`, SDK menampilkan toast |

Bila endpoint cetak gagal di port utama, SDK otomatis mencoba `12212` dan
menyimpan alamat yang berhasil.

---

## 3. API Cetak (Statis, lewat HTTP)

```js
HardwareBridge.getPrinters();
HardwareBridge.printRaw(namaPrinter, dataRaw, docName);
HardwareBridge.printPdf(namaPrinter, pdfAtauUrl, docName, options);
HardwareBridge.printImage(namaPrinter, gambarBase64, docName);
HardwareBridge.openCashDrawer(namaPrinter, pin);
```

| Metode | Parameter | Bawaan |
|--------|-----------|--------|
| `printRaw` | `(printerName, rawData, docName)` | `docName = 'DirectPrint_Raw'` |
| `printPdf` | `(printerName, pdfDataOrUrl, docName, options)` | `docName = 'DirectPrint_PDF'`, `options = {}` |
| `printImage` | `(printerName, imageBase64, docName)` | `docName = 'DirectPrint_Image'` |
| `openCashDrawer` | `(printerName, pin)` | `pin = 2` |

> ❗ **Semua argumen posisional, bukan objek.**
>
> ```js
> // ❌ SALAH
> HardwareBridge.printPdf({ printer: 'asset_label', pdf_data: url });
>
> // ✅ BENAR
> HardwareBridge.printPdf('asset_label', url, 'Label Produksi', { mode: 'zpl', dpi: 203 });
> ```

Nilai kembalian adalah **body JSON apa adanya** dari bridge:

```js
const r = await HardwareBridge.printPdf('asset_label', url, 'Label', { dpi: 203 });
if (r.status === 'success') {
    console.log('Tercetak di', r.result.printer);
} else {
    console.error(r.detail || r.message);
}
```

Panduan lengkap cetak: [direct-print/](direct-print/).

---

## 4. API Timbangan (Statis)

| Metode | Keterangan |
|--------|------------|
| `listScales()` | Array seluruh timbangan beserta statusnya |
| `getWeight(scale)` | Berat saat ini, instan |
| `stableRead(scale, timeoutS)` | Menunggu sampai berat stabil |
| `pickScale(preferred, opts)` | Memilih timbangan: cocokkan nama/port/substring, atau ambil timbangan fisik pertama yang online |
| **`ensureScaleReady(opts)`** | **Menyambungkan timbangan tanpa operator perlu membuka dashboard bridge** |
| `toGram(value, unit, legacy)` | Konversi satuan ke gram |

```js
const daftar = await HardwareBridge.listScales();
const s      = await HardwareBridge.pickScale('Shinko 1');
const r      = await HardwareBridge.stableRead(s.name, 15);
if (r.ok) console.log(r.weight, r.unit);
```

### `ensureScaleReady(opts)` — tanpa buka dashboard

Bila `enable_scale_at_startup` bernilai `false`, bridge sengaja **tidak membuka
port COM** saat startup supaya port tetap bebas untuk aplikasi Delphi atau Web
Serial API. Efek sampingnya: semua timbangan berstatus `connected: false`,
sehingga dropdown kosong dan `pickScale()` melempar *"Timbangan tidak terhubung"*
sampai ada orang membuka `http://127.0.0.1:18212` dan menekan **Sambungkan**.

`ensureScaleReady()` menghapus langkah manual itu. Fungsi ini menyalakan opsi
tersebut lewat `POST /api/scale/startup-config`, lalu menunggu watchdog membuka
port. Setelan ikut tersimpan ke `bridge_config.json`, jadi **penantian ini hanya
terjadi sekali per PC** — mulai restart berikutnya timbangan sudah tersambung
sendiri sejak bridge dinyalakan.

| Opsi | Bawaan | Keterangan |
|------|--------|------------|
| `timeout` | `8` | Batas tunggu port terbuka, dalam detik |
| `allowSim` | `false` | Anggap siap walau yang aktif hanya Simulator |
| `autoEnable` | `true` | Izinkan menyalakan `enable_scale_at_startup` |
| `force` | `false` | Ulangi walau percobaan sebelumnya di halaman ini gagal |

```js
// Cukup panggil sekali saat halaman dimuat
await HardwareBridge.ensureScaleReady();

// Alias bahasa Indonesia, fungsinya sama persis
await HardwareBridge.pastikanTimbanganSiap();
```

**Anda biasanya tidak perlu memanggilnya sendiri.** `pickScale()`,
`timbangKeInput()`, `populateScaleSelect()`, `liveWeight()`, dan
`timbangDialog()` sudah memanggilnya otomatis ketika mendapati belum ada
timbangan fisik yang terhubung. Matikan perilaku ini dengan `autoEnsure: false`:

```js
await HardwareBridge.timbangKeInput('#berat', {
    scale:      'Shinko 1',
    autoEnsure: false      // jangan sentuh setelan bridge, biarkan gagal apa adanya
});
```

Catatan perilaku:

- Kalau timbangan sudah terhubung, biayanya hanya **satu GET ringan** — tidak ada
  penantian sama sekali.
- Beberapa pemanggilan paralel digabung menjadi **satu** permintaan ke bridge.
- Kalau setelah dicoba tetap tidak ada timbangan fisik (mis. PC itu memang tanpa
  timbangan), percobaan tidak diulang terus-menerus sehingga operator tidak
  menunggu berulang kali tiap menekan tombol.

> ⚠️ **Kapan sebaiknya `autoEnsure: false`?** Bila di PC itu ada aplikasi lain
> (mis. program kasir Delphi) yang memakai port COM yang sama. Membuka port dari
> bridge akan membuat aplikasi tersebut kena `Access is denied`. Untuk kasus itu
> gunakan `"sharing_mode": "on_demand"` di `bridge_config.json` — lihat
> [06-timbangan-serial.md](06-timbangan-serial.md).

### Pembantu Antarmuka

| Metode | Keterangan |
|--------|------------|
| `timbangKeInput(target, opts)` | Baca berat stabil lalu isi ke elemen input |
| `liveWeight(target, opts)` | Tampilkan berat live; mengembalikan fungsi untuk menghentikan |
| `populateScaleSelect(select, opts)` | Isi `<select>` dengan timbangan yang terhubung (auto-sambung bila kosong) |
| `attachIndicator(target)` | Indikator status koneksi timbangan |
| `timbangDialog(onUse, opts)` | Dialog modal penimbangan interaktif |
| `toast(pesan, warna)` | Notifikasi pojok kanan bawah |

```js
// Isi input #berat dengan berat stabil dalam gram, 2 desimal
await HardwareBridge.timbangKeInput('#berat', {
    scale:          'Shinko 1',   // opsional; kosong = pilih otomatis
    stable_timeout: 15,
    decimals:       2,
    to_gram:        true,         // konversi kg/lb ke gram
    allow_zero:     false,
    alerts:         true
});

// Tampilan berat live
const stop = HardwareBridge.liveWeight('#berat-live', { decimals: 2, suffix: ' g' });
// stop();   // hentikan saat komponen dilepas

// Dialog modal
HardwareBridge.timbangDialog((gram, scale) => {
    document.querySelector('#berat').value = gram.toFixed(2);
});
```

Penjelasan mendalam (multi-timbangan, protokol, port sharing, Livewire):
[06-timbangan-serial.md](06-timbangan-serial.md).

---

## 5. Mode Instance (WebSocket)

Lebih cepat untuk cetak beruntun dan diperlukan untuk stream berat real-time.

```js
const bridge = new HardwareBridge({
    host:              '127.0.0.1',
    port:              18212,
    autoReconnect:     true,
    reconnectInterval: 3000
});

const terhubung = await bridge.connect();   // false bila WS tidak tersedia

await bridge.printPdf('asset_label', url, 'Label', { dpi: 203 });
await bridge.printRaw('receipt', dataEscPos, 'Struk');
await bridge.openCashDrawer('receipt', 2);

const w = await bridge.getWeight('Shinko 1');
const st = await bridge.getStableWeight('Shinko 1', 15);
```

Bila `connect()` gagal, seluruh metode instance otomatis memakai `fetch` HTTP —
kode aplikasi tidak perlu diubah.

### Callback

```js
bridge.onConnect(()  => console.log('Bridge tersambung'));
bridge.onDisconnect(() => console.log('Bridge terputus'));
bridge.onWeightChange(scales => {
    scales.forEach(s => console.log(s.name, s.weight, s.unit, s.stable));
});
```

`onWeightChange` mengaktifkan langganan `subscribeScale` dan menerima pembaruan tiap
0,3 detik.

`options` diteruskan sepenuhnya pada jalur WebSocket maupun HTTP, termasuk
`mode: 'zpl'` untuk printer label.

---

## 6. Penanganan Galat

```js
HardwareBridge.onError = (pesan) => {
    // ganti toast bawaan dengan notifikasi aplikasi Anda
    Swal.fire({ icon: 'error', title: 'Hardware Bridge', text: pesan });
};
```

Deteksi bridge aktif sebelum mengirim job:

```js
async function bridgeAktif(timeoutMs = 1500) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
        return (await fetch('http://127.0.0.1:18212/api/status', { signal: ctrl.signal })).ok;
    } catch {
        return false;
    } finally {
        clearTimeout(t);
    }
}
```

---

## 7. Pemanggilan Tingkat Rendah

```js
// GET
const printers = await HardwareBridge.api('/api/printers');

// POST (argumen kedua = body), argumen ketiga = timeout ms
const hasil = await HardwareBridge.api('/api/print/pdf', {
    printer:  'asset_label',
    pdf_data: url,
    doc_name: 'Label',
    options:  { dpi: 203 }
}, 30000);
```

Berguna untuk endpoint yang belum punya pembungkus khusus di SDK, misalnya
`/api/print/history` atau `/api/scale/scan-baud`. Timeout bawaan `api()` adalah
8 detik — naikkan untuk PDF besar.

---

## 8. Kompatibilitas `TimbanganSvc`

SDK ini adalah **pengganti langsung** `TimbanganSvc`. Kode lama seperti:

```js
TimbanganSvc.timbangKeInput('#berat');
TimbanganSvc.liveWeight('#display');
```

tetap berjalan tanpa perubahan, karena `window.TimbanganSvc` menunjuk ke objek
yang sama dengan `window.HardwareBridge`.
