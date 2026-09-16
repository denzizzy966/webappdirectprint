# 📖 Dokumentasi Penggunaan Hardware Bridge
### Silent Direct Printing (ESC/POS, ZPL, PDF) & Integrasi Multi-Timbangan Digital (RS232/Serial)

Dokumentasi ini menjelaskan cara mengintegrasikan **Hardware Bridge** ke dalam aplikasi web (Laravel Blade, Livewire, Vue, React, ERPNext, atau HTML polos) untuk menangani pencetakan kasir tanpa dialog print browser serta pembacaan timbangan digital multi-perangkat.

---

## 📑 Daftar Isi
1. [Arsitektur & Keunggulan](#1-arsitektur--keunggulan)
2. [Konfigurasi Timbangan di `bridge_config.json`](#2-konfigurasi-timbangan-di-bridge_configjson)
3. [Menentukan Timbangan Apabila Ada 2 (atau Lebih) Timbangan Aktif](#3-menentukan-timbangan-apabila-ada-2-atau-lebih-timbangan-aktif)
   - [Metode 1: Parameter Langsung di Kode (Direct Parameter)](#metode-1-parameter-langsung-di-kode-direct-parameter)
   - [Metode 2: Dropdown Dinamis Pilihan Operator (`populateScaleSelect`)](#metode-2-dropdown-dinamis-pilihan-operator-populatescaleselect)
   - [Metode 3: Modal Dialog Pop-up Interaktif (`timbangDialog`)](#metode-3-modal-dialog-pop-up-interaktif-timbangdialog)
   - [Metode 4: Otomatis (Auto Fallback ke Timbangan Fisik Aktif)](#metode-4-otomatis-auto-fallback-ke-timbangan-fisik-aktif)
4. [Panduan Integrasi ke Laravel (Blade & Livewire)](#4-panduan-integrasi-ke-laravel-blade--livewire)
5. [Panduan Integrasi ke ERPNext](#5-panduan-integrasi-ke-erpnext)
6. [Referensi Lengkap Fungsi SDK JavaScript](#6-referensi-lengkap-fungsi-sdk-javascript)
7. [Panduan Silent Direct Printing](#7-panduan-silent-direct-printing)
8. [Halaman Demo Interaktif (`cara-pakai.html`)](#8-halaman-demo-interaktif-cara-pakaihtml)

---

## 1. Arsitektur & Keunggulan

Hardware Bridge berjalan secara lokal di background PC klien (Windows: Port `18212` / System Tray; Linux: Systemd service).

```
┌────────────────────────────────────────────────────────────┐
│                    Browser / Client PC                     │
│  ┌────────────────────────┐    ┌────────────────────────┐  │
│  │ Laravel / ERPNext / UI │    │  Hardware Bridge SDK   │  │
│  │ (Blade / Livewire/ Vue)│<──>│  hardware-bridge.js    │  │
│  └────────────────────────┘    └───────────┬────────────┘  │
│                                            │ HTTP / WS     │
│                                            ▼               │
│                               ┌─────────────────────────┐  │
│                               │ Hardware Bridge Daemon  │  │
│                               │ (127.0.0.1:18212)       │  │
│                               └────────────┬────────────┘  │
└────────────────────────────────────────────┼───────────────┘
                                             │
             ┌───────────────────────────────┴───────────────────────────────┐
             ▼                                                               ▼
┌─────────────────────────┐                                     ┌─────────────────────────┐
│   Printer Kasir/Label   │                                     │ Timbangan Digital RS232 │
│ - Thermal ESC/POS (USB) │                                     │ - Timbangan Gram (COM5) │
│ - Barcode ZPL / Godex   │                                     │ - Timbangan Koli (COM3) │
│ - Driver Dokumen PDF    │                                     │ - Mettler, Shinko, A&D  │
└─────────────────────────┘                                     └─────────────────────────┘
```

- **Drop-in Replacement:** 100% kompatibel dengan script `TimbanganSvc` (`window.TimbanganSvc = HardwareBridge`).
- **Tanpa Dependensi:** SDK murni Vanilla JS, tidak memerlukan library eksternal (jQuery, Axios, Bootstrap tidak wajib).
- **Reaktif:** Memicu standard DOM event `input` dan `change` dengan bubbling, sehingga data langsung tersinkronisasi ke `wire:model` Livewire dan `v-model` Vue.
- **Bebas Kunci Port COM saat Startup:** Opsi `enable_scale_at_startup: false` menjamin port serial COM tidak dikunci secara permanen saat komputer baru menyala.

---

## 2. Konfigurasi Timbangan di `bridge_config.json`

Buka file konfigurasi `bridge_config.json`. Anda dapat mendaftarkan satu, dua, atau banyak timbangan dengan port dan baudrate masing-masing:

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 18212,
    "enable_scale_at_startup": false,
    "enable_tray": true
  },
  "scales": [
    {
      "name": "Timbangan Gram",
      "port": "COM5",
      "protocol": "mettler",
      "baud": 9600,
      "databits": 8,
      "parity": "N",
      "stopbits": 1,
      "autoconnect": true
    },
    {
      "name": "Timbangan Koli",
      "port": "COM3",
      "protocol": "shinko",
      "baud": 9600,
      "databits": 8,
      "parity": "N",
      "stopbits": 1,
      "autoconnect": true
    }
  ]
}
```

> **Di Linux (Ubuntu / Linux Mint):** Gantilah `"COM5"` dan `"COM3"` dengan nama port serial Linux, misalnya `"/dev/ttyUSB0"` dan `"/dev/ttyUSB1"`.

---

## 3. Menentukan Timbangan Apabila Ada 2 (atau Lebih) Timbangan Aktif

Jika di meja kasir / gudang terhubung **2 timbangan aktif sekaligus** (misalnya `Timbangan Gram` pada `COM5` dan `Timbangan Koli` pada `COM3`), terdapat **4 cara praktis** untuk menentukannya di aplikasi web:

---

### Metode 1: Parameter Langsung di Kode (Direct Parameter)
Cara ini paling tepat jika form atau tombol sudah memiliki tujuan spesifik (misal Tombol Timbang Gram di bagian perhiasan/material kecil, dan Tombol Timbang Koli di bagian koli/pengiriman paket).

Cukup tambahkan opsi `{ scale: '...' }` ke fungsi SDK:

```javascript
// 1. Timbang stabil ke input berat gram
HardwareBridge.timbangKeInput('#input_gram', { 
    scale: 'Timbangan Gram',  // Nama timbangan
    alerts: true              // Tampilkan toast status
});

// 2. Timbang stabil ke input berat koli/paket
HardwareBridge.timbangKeInput('#input_koli', { 
    scale: 'Timbangan Koli',
    alerts: true 
});

// 3. Atau tentukan langsung lewat nomor port COM
HardwareBridge.timbangKeInput('#input_berat', { 
    scale: 'COM5' 
});
```

> **Keunggulan Matching Cerdas:** Pencocokan `scale` bersifat toleran. Anda dapat memasukkan:
> 1. Nama lengkap: `'Timbangan Gram'`
> 2. Huruf besar/kecil bebas: `'timbangan gram'`
> 3. Nomor port: `'COM5'` atau `'/dev/ttyUSB0'`
> 4. Potongan kata (substring): `'gram'` atau `'koli'`

---

### Metode 2: Dropdown Dinamis Pilihan Operator (`populateScaleSelect`)
Cara ini sangat ramah pengguna (user-friendly) karena operator dapat memilih timbangan yang ingin dipakai lewat dropdown `<select>`, lalu menekan tombol timbang.

**Langkah 1: Siapkan HTML Form**
```html
<div class="form-group">
    <label>Pilih Timbangan Aktif:</label>
    <select id="pilihTimbangan" class="form-control"></select>
</div>

<div class="form-group">
    <label>Hasil Timbang:</label>
    <input type="text" id="berat" class="form-control" placeholder="0.00">
    <button type="button" class="btn btn-primary mt-2" onclick="timbangSesuaiPilihan()">
        ⚖️ Ambil Berat Stabil
    </button>
</div>
```

**Langkah 2: Inisialisasi Dropdown dengan JavaScript**
```javascript
// Otomatis mengambil daftar timbangan terhubung dan mengisi elemen <select>
HardwareBridge.populateScaleSelect('#pilihTimbangan', {
    selected: 'Timbangan Gram', // (Opsional) Pilihan awal
    onChange: function(scaleName) {
        console.log('Operator memilih timbangan:', scaleName);
    }
});

function timbangSesuaiPilihan() {
    const scaleDipilih = document.querySelector('#pilihTimbangan').value;
    HardwareBridge.timbangKeInput('#berat', {
        scale: scaleDipilih,
        alerts: true,
        decimals: 2
    });
}
```

---

### Metode 3: Modal Dialog Pop-up Interaktif (`timbangDialog`)
Jika Anda memanggil `HardwareBridge.timbangDialog()`, SDK secara otomatis memeriksa timbangan yang online:
- Jika terdeteksi lebih dari 1 timbangan, **dropdown pemilih timbangan langsung muncul di dalam dialog modal**!
- Angka live real-time berganti sesuai timbangan yang dipilih.
- Operator menekan tombol **"Gunakan Berat (stabil)"**, dan data akan dikembalikan ke callback aplikasi Anda.

```javascript
HardwareBridge.timbangDialog(function (gram, scaleObject) {
    console.log("Diambil dari:", scaleObject.name, "Port:", scaleObject.port);
    document.querySelector('#berat').value = gram.toFixed(2);
}, {
    title: '⚖️ Penimbangan Barang Masuk',
    stable_timeout: 10
});
```

---

### Metode 4: Otomatis (Auto Fallback ke Timbangan Fisik Aktif)
Jika Anda tidak menyertakan parameter `scale` (atau bernilai `null`):
```javascript
HardwareBridge.timbangKeInput('#berat');
```
Sistem akan:
1. Otomatis memilih timbangan fisik pertama yang berstatus `connected: true`.
2. Mengabaikan Simulator Virtual jika ada timbangan fisik yang terhubung.
3. Jika timbangan utama mati atau kabelnya terlepas, sistem otomatis mengalihkan pembacaan ke timbangan online berikutnya.

---

## 4. Panduan Integrasi ke Laravel (Blade & Livewire)

### A. Memasang Script di Blade
Salin berkas `static/js/hardware-bridge.js` ke folder `public/js/hardware-bridge.js` aplikasi Laravel Anda.
Muat pada layout utama Anda:

```html
<!-- resources/views/layouts/app.blade.php -->
<script src="{{ asset('js/hardware-bridge.js') }}"></script>
```

### B. Contoh Form Laravel Livewire (Otomatis Tersinkron ke `wire:model`)
Karena fungsi `HardwareBridge.timbangKeInput` memicu event JavaScript standar `input` dan `change` dengan `bubbles: true`, komponen Livewire akan langsung memperbarui properti PHP tanpa memerlukan binding tambahan.

**Blade View: `resources/views/livewire/transaksi-gudang.blade.php`**
```html
<div class="card p-4">
    <h4>Penerimaan Barang Gudang</h4>

    <!-- Pemilih Timbangan -->
    <div class="mb-3">
        <label class="form-label">Timbangan Aktif:</label>
        <select id="scale-selector" class="form-select"></select>
    </div>

    <!-- Input Berat Terikat ke Livewire -->
    <div class="mb-3">
        <label class="form-label">Berat Bersih (gram):</label>
        <div class="input-group">
            <input type="text" id="input-berat-livewire" wire:model="berat_bersih" class="form-control" readonly>
            <button type="button" class="btn btn-success" onclick="ambilTimbangan()">
                ⚖️ Timbang Stabil
            </button>
        </div>
        <small class="text-muted">
            Live Stream: <b id="live-stream-text">--</b> &bull; Status Bridge: <span id="status-badge"></span>
        </small>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function () {
    // 1. Tampilkan status koneksi Hardware Bridge
    HardwareBridge.attachIndicator('#status-badge');

    // 2. Isi dropdown timbangan
    HardwareBridge.populateScaleSelect('#scale-selector', {
        onChange: function (selectedScale) {
            // Ubah live stream sesuai timbangan terpilih
            HardwareBridge.liveWeight('#live-stream-text', { scale: selectedScale });
        }
    });

    // 3. Mulai live reading default
    HardwareBridge.liveWeight('#live-stream-text');
});

function ambilTimbangan() {
    const scale = document.querySelector('#scale-selector').value;
    HardwareBridge.timbangKeInput('#input-berat-livewire', {
        scale: scale,
        alerts: true,
        decimals: 2
    });
}
</script>
```

---

## 5. Panduan Integrasi ke ERPNext

Tambahkan script berikut pada **Client Script** DocType Anda (misal `Stock Entry`, `Purchase Receipt`, atau `Sales Invoice`):

```javascript
frappe.ui.form.on('Stock Entry Detail', {
    form_render: function(frm, cdt, cdn) {
        // Muat library HardwareBridge jika belum termuat
        if (!window.HardwareBridge) {
            frappe.require('/assets/js/hardware-bridge.js');
        }
    }
});

// Tambahkan Custom Button pada Form Dokumen
frappe.ui.form.on('Stock Entry', {
    refresh: function(frm) {
        frm.add_custom_button(__('⚖️ Timbang Stabil'), function() {
            // Tampilkan dialog timbang interaktif
            HardwareBridge.timbangDialog(function(gram, scaleObj) {
                frappe.show_alert({
                    message: __('Berat diterima: {0} g dari {1}', [gram, scaleObj.name]),
                    indicator: 'green'
                });
                
                // Isi ke field DocType
                frm.set_value('total_outgoing_value', gram);
                frm.refresh_field('total_outgoing_value');
            }, {
                title: 'Timbang Barang Masuk'
            });
        }, __('Aksi Perangkat'));
    }
});
```

---

## 6. Referensi Lengkap Fungsi SDK JavaScript

Objek global: `HardwareBridge` atau `TimbanganSvc` (keduanya identik).

| Fungsi | Parameter | Nilai Balik | Kegunaan |
|---|---|---|---|
| `timbangKeInput(target, opts)` | `target` (selector string atau elemen HTML)<br>`opts`: `{ scale, alerts, stable_timeout, decimals, to_gram }` | `Promise<number>` (berat) | Mengambil nilai stabil dan mengisi input form. Memicu event input & change. |
| `liveWeight(target, opts)` | `target` (selector string atau elemen)<br>`opts`: `{ scale, decimals, suffix, interval, onUpdate }` | `Function stop()` | Menampilkan angka live real-time pada label / span. |
| `populateScaleSelect(targetSelect, opts)` | `targetSelect` (elemen `<select>`)<br>`opts`: `{ selected, onChange }` | `Promise<Array>` | Mengisi `<select>` secara dinamis dengan seluruh timbangan yang sedang terhubung. |
| `timbangDialog(onUse, opts)` | `onUse(gram, scale)`<br>`opts`: `{ title, scale, stable_timeout }` | `void` | Membuka dialog modal dengan display angka besar dan pemilih multi-timbangan otomatis. |
| `attachIndicator(target)` | `target` (selector string atau elemen) | `Function stop()` | Menampilkan badge status koneksi bridge & port timbangan. |
| `listScales()` | *tanpa parameter* | `Promise<Array>` | Mengambil daftar seluruh timbangan beserta berat saat ini, kestabilan, dan status port. |
| `getWeight(scale)` | `scale` (string nama/port) | `Promise<Object>` | Membaca berat saat ini secara instan tanpa menunggu stabil. |
| `stableRead(scale, timeout)` | `scale` (string)<br>`timeout` (detik, default 10) | `Promise<Object>` | Menunggu hingga timbangan stabil dan mengembalikan hasil pembacaan. |
| `pickScale(preferred)` | `preferred` (string) | `Promise<Object>` | Memilih timbangan terbaik berdasar preferensi nama/port atau otomatis pertama yang terhubung. |
| `toGram(weight, unit)` | `weight` (number), `unit` (string) | `number` | Mengonversi satuan berat (kg, g, mg) ke satuan gram. |

---

## 7. Panduan Silent Direct Printing

Hardware Bridge mendukung pencetakan langsung tanpa dialog browser:

### 1. Cetak Struk Kasir Thermal (ESC/POS Raw)
```javascript
// Ambil printer default atau tertentu
const printers = await HardwareBridge.getPrinters();
const printerKasir = printers.default_raw || "EPSON TM-T82";

// Kirim data mentah ESC/POS (teks biasa atau base64)
const strukText = "\x1B\x40" +                       // Reset printer
                  "\x1B\x61\x01TOKO MAJU JAYA\n" +    // Center align
                  "\x1B\x61\x00Kasir: Budi\n" +       // Left align
                  "Barang A     Rp 25.000\n" +
                  "Barang B     Rp 15.000\n" +
                  "--------------------------------\n" +
                  "Total        Rp 40.000\n\n\n" +
                  "\x1D\x56\x00";                     // Potong kertas (Cut)

await HardwareBridge.printRaw(printerKasir, strukText, "Struk_Penjualan");
```

### 2. Cetak Dokumen Faktur / Surat Jalan PDF
```javascript
// Data PDF berupa Base64 ("data:application/pdf;base64,...") atau URL file
const pdfBase64 = "JVBERi0xLjQKJ...";
await HardwareBridge.printPdf("EPSON L3110", pdfBase64, "Faktur_Penjualan");
```

### 3. Membuka Laci Kasir (Cash Drawer)
```javascript
// Mengirimkan sinyal kick-pulse ke printer struk (Pin 2 atau Pin 5)
await HardwareBridge.openCashDrawer("EPSON TM-T82", 2);
```

---

## 8. Halaman Demo Interaktif (`cara-pakai.html`)

Anda dapat mencoba seluruh fitur di atas secara langsung dengan membuka file **`laravel/cara-pakai.html`** pada browser.
Jika Hardware Bridge sedang berjalan di PC Anda, halaman tersebut dapat langsung:
- Menampilkan live streaming berat dari timbangan fisik / virtual.
- Menjalankan pengetesan tombol timbang stabil pada form.
- Menguji perpindahan antara 2 timbangan aktif via dropdown.
- Menguji pencetakan silent ke printer kasir terpasang.

Akses via URL web server bridge:
👉 **`http://127.0.0.1:18212/static/cara-pakai.html`**

---

## 9. Console Interaktif & Diagnostic Timbangan (Dashboard Bridge)

Pada antarmuka Web UI Hardware Bridge (`http://127.0.0.1:18212` tab **Timbangan Digital**), terdapat console diagnostic lengkap yang memudahkan teknisi dan developer menguji timbangan:

### 1. Mode Simulator (`SIM`) — Uji Coba Tanpa Hardware Fisik
- Pada dropdown **Port**, pilih **`SIM — Simulator Mode (mock data)`**.
- Klik **Connect**.
- Bridge akan langsung menyimulasikan aliran data timbangan secara real-time (`S S 123.45 g`).
- Cocok digunakan saat development di laptop yang tidak terhubung ke timbangan fisik RS232/COM.

### 2. Pilihan Protokol & Presets
- **Mettler MT-SICS:** Preset Baud `9600`, Frame `8/None`. Tombol cepat: Zero (`Z`), Tare (`T`), Baca Stabil (`S`), Baca Langsung (`SI`), Start Continuous (`SIR`), Stop (`@`).
- **Shinko / ViBRA:** Preset Baud `9600`, Frame `8/None`. Tombol cepat: Zero (`Z`), Tare (`T`), Baca Stabil (`O8`), Baca Langsung (`O9`), Start Continuous (`O1`), Stop (`O0`).
- **A&D:** Preset Baud `2400`, Frame `7/Even`. Tombol cepat: Zero (`Z`), Tare (`T`), Baca Stabil (`S`), Baca Langsung (`Q`), Start Continuous (`SIR`), Stop (`C`).

### 3. Pindai Baud Rate Otomatis (Scan Baud)
- Jika Anda menghubungkan timbangan baru dan tidak mengetahui baud rate-nya, cukup pilih port COM timbangan lalu klik tombol **🔍 Scan Baud**.
- Bridge akan otomatis menguji kecepatan `9600`, `4800`, `2400`, `1200`, dan `19200` hingga menemukan respons yang valid.

### 4. Live Serial Monitor (Terminal RX/TX)
- **Monitoring Lalu Lintas:** Menampilkan setiap byte data yang dikirim (**TX >**) dan diterima (**RX <**) secara transparan.
- **Tampilkan Hex:** Centang kotak `tampilkan hex` untuk melihat representasi byte heksadesimal dari pesan serial.
- **Autoscroll:** Menjaga terminal selalu bergeser ke baris pesan terbaru.
- **Statistik:** Menampilkan total baris diterima, total byte, dan kecepatan transfer data (byte/detik).

### 5. Tombol "Lepas Port" (Port Sharing untuk Delphi / Web Serial)
- Klik tombol **⏸️ Lepas Port** untuk membebaskan port COM secara instan tanpa perlu mematikan bridge.
- Port COM langsung dapat dibuka oleh aplikasi legacy (seperti Delphi) atau browser via Web Serial API.
- Klik **▶️ Sambung Lagi** untuk menghubungkan kembali timbangan ke bridge.

