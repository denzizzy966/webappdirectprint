# ⚡ WebApp Hardware Bridge Universal (Direct Print & Scale Connector)

Aplikasi **Hardware Bridge Universal** lintas platform (**Windows 10/11** dan **Linux Mint 22 / Ubuntu 22**) untuk menghubungkan aplikasi web (**ERPNext**, sistem POS, web invoice generator, atau browser) dengan perangkat keras lokal:
1. **Silent Direct Printing**: Mencetak struk kasir (**ESC/POS**), label barcode (**ZPL / TSPL**), berkas **PDF**, dan gambar langsung ke printer fisik tanpa memunculkan dialog cetak browser (`Ctrl+P`).
2. **Pembaca Serial Port Timbangan Digital**: Membaca bobot real-time dari timbangan industri & laboratorium (**Mettler Toledo MT-SICS**, **Shinko / ViBRA**, **A&D**, serta **Simulator Virtual**) dengan penanganan cerdas *hotplug*, deteksi saklar off, dan *cooperative port locking* (kompatibel berdampingan dengan software Delphi / browser).
3. **Kompatibilitas Penuh**: Menyediakan antarmuka **WebSocket** (port `12212` kompatibel dengan [webapp-hardware-bridge](https://github.com/imTigger/webapp-hardware-bridge)) dan **REST API HTTP** lengkap dengan Dashboard Web interaktif.

---

## 📚 Dokumentasi

Seluruh dokumentasi terkumpul di folder **[`docs/`](docs/)**.

| Kebutuhan | Dokumen |
|-----------|---------|
| 🗂️ Indeks seluruh dokumentasi | **[docs/README.md](docs/README.md)** |
| 🚀 Mencetak pertama kali dalam 5 menit | [docs/02-quickstart.md](docs/02-quickstart.md) |
| 🖨️ **Panduan Direct Print lengkap** | **[docs/direct-print/](docs/direct-print/)** |
| &nbsp;&nbsp;↳ HTML dikonversi ke Base64 lalu dicetak | [docs/direct-print/02-html-ke-base64.md](docs/direct-print/02-html-ke-base64.md) |
| &nbsp;&nbsp;↳ Cetak PDF dari URL server (mis. `192.168.3.25/produksi/ProduksiPDF/`) | [docs/direct-print/03-pdf-dari-url.md](docs/direct-print/03-pdf-dari-url.md) |
| &nbsp;&nbsp;↳ ESC/POS, ZPL, TSPL, laci kasir | [docs/direct-print/04-raw-escpos-zpl.md](docs/direct-print/04-raw-escpos-zpl.md) |
| 🏗️ Arsitektur (kenapa di PC klien) | [docs/01-arsitektur.md](docs/01-arsitektur.md) |
| 📦 Instalasi & deployment | [docs/03-instalasi.md](docs/03-instalasi.md) |
| ⚙️ Referensi `bridge_config.json` | [docs/04-konfigurasi.md](docs/04-konfigurasi.md) |
| 📡 Referensi API REST & WebSocket | [docs/05-api-reference.md](docs/05-api-reference.md) |
| ⚖️ Timbangan digital serial | [docs/06-timbangan-serial.md](docs/06-timbangan-serial.md) |
| 💻 SDK JavaScript | [docs/07-sdk-javascript.md](docs/07-sdk-javascript.md) |
| 🛠️ Troubleshooting | [docs/08-troubleshooting.md](docs/08-troubleshooting.md) |
| 🔌 Integrasi ERPNext / Laravel | [docs/integrasi/](docs/integrasi/) |

---

## 🏗️ Mengapa Harus Berjalan di Client PC? (Jawaban Arsitektur)

> **Apakah bisa dari sisi server ERPNext atau hanya bisa di Client PC?**

1. **Untuk Printer USB & Timbangan Kabel RS232:**  
   **MUTLAK HARUS di Client PC (atau Mini PC / Raspberry Pi kasir).**  
   Server ERPNext (di Cloud VPS, Docker, atau WSL) tidak memiliki kabel fisik ke meja kasir. Peramban kasir juga dibatasi oleh *browser sandbox* sehingga tidak bisa langsung mengakses port USB/COM lokal tanpa bridge.
2. **Untuk Printer Jaringan (Ethernet LAN / Wi-Fi Raw Port 9100):**  
   Bisa dilakukan dari server ERPNext *jika dan hanya jika* server ERPNext berada di subnet LAN lokal yang sama dengan printer.
3. *Baca analisis lengkap di dokumen [docs/01-arsitektur.md](docs/01-arsitektur.md).*

---

## 🌟 Fitur Utama

- **Silent RAW Print (ESC/POS, ZPL, TSPL):**
  - Kirim string plain text, hex, atau base64 langsung ke spooler Windows (`win32print`) atau Linux CUPS (`lp -o raw`).
  - Auto potong kertas (*paper cut*) dan pulsa pembuka laci kasir (*kick cash drawer*).
- **Silent PDF Printing:**
  - Di Windows: Menggunakan rendering raster *PyMuPDF* & *Win32 GDI* langsung ke Device Context printer.
  - Di Linux: Menggunakan filter native subsystem CUPS.
- **Serial Scale Engine (Timbangan Digital):**
  - Multi-protokol: Mettler Toledo (`SI`, `S`, `SIR`), Shinko/ViBRA (`O9`, `O8`), A&D (`Q`, `S`), Generic Plain.
  - **Mode Simulator (`SIM`):** Uji coba langsung tanpa memerlukan timbangan fisik.
  - **Hotplug Resilient:** Handle serial Windows/Linux ditutup seketika saat kabel USB dicabut untuk mencegah zombie port & *Access Denied*.
  - **Mode On-Demand (Auto-Release):** Port serial dilepas otomatis saat idle agar software lain (seperti Delphi) bebas mengakses port COM tanpa bentrok.
- **Dashboard Web Interaktif:**
  - Buka di `http://127.0.0.1:12212`.
  - Dilengkapi LCD Display timbangan real-time, tombol Zero & Tare, pengujian 1-klik struk kasir, label ZPL, dan deteksi port hardware.

---

## 📖 Panduan Instalasi Lengkap (Installer Guide)
> Untuk panduan langkah-demi-langkah, instalasi service background, auto-start Windows, systemd Linux, dan troubleshooting, silakan baca:  
> 👉 **[docs/03-instalasi.md](docs/03-instalasi.md)**

---

## 🚀 Panduan Cepat Menjalankan (Quick Start)

### A. Versi Windows 10 / 11

1. **Jalankan Lewat Konsol:**
   Klik ganda berkas:
   ```cmd
   windows\run.bat
   ```
2. **Jalankan di Background (Tanpa Jendela CMD Hitam):**
   Klik ganda berkas:
   ```cmd
   windows\run_background.vbs
   ```
3. **Pasang Auto-Start (Otomatis Aktif saat Windows Dinyalakan):**
   Klik kanan `windows\install_autostart.bat` -> **Run as administrator** (atau klik ganda).
4. **Membangun File `.exe` Mandiri (Standalone Executable):**
   Jalankan:
   ```cmd
   windows\build_exe.bat
   ```

---

### B. Versi Linux Mint 22 / Ubuntu 22

1. **Pemasangan Lengkap (Systemd Service + Aturan Udev Port Serial):**
   Jalankan perintah berikut di terminal Linux:
   ```bash
   chmod +x linux/*.sh
   sudo bash linux/install.sh
   ```
   *Script akan otomatis menginstal paket sistem, CUPS, dependensi python, memasang udev rules `/etc/udev/rules.d/99-hardware-bridge.rules`, dan mengaktifkan service systemd `hardware-bridge.service`.*

2. **Perintah Pengelolaan di Linux:**
   - Cek Status: `sudo systemctl status hardware-bridge`
   - Restart: `sudo systemctl restart hardware-bridge`
   - Lihat Log: `journalctl -u hardware-bridge -f`

3. **Jalankan Sementara di Konsol (Tanpa Service):**
   ```bash
   bash linux/run.sh
   ```

---

## 🔌 Integrasi dengan ERPNext

Integrasi ke ERPNext sangat mudah:
1. Buka ERPNext -> Ketik **Client Script** di Awesome Bar -> Klik **New**.
2. Pilih DocType target: `POS Invoice` atau `Sales Invoice`.
3. Salin isi script dari berkas [`erpnext/erpnext_hardware_bridge.js`](file:///D:/Workspaces-gemini/webappdirectprint/erpnext/erpnext_hardware_bridge.js).
4. Centang **Enabled** dan klik **Save**.
5. Tombol **"Cetak Struk (Direct Print)"** dan **"Timbang Item Aktif"** akan langsung muncul di dokumen transaksi Anda!
6. *Lihat panduan lengkap di [docs/integrasi/erpnext.md](docs/integrasi/erpnext.md).*

---

## 💻 Penggunaan SDK JavaScript (`hardware-bridge.js`)

Untuk integrasi ke aplikasi web buatan sendiri (misal React, Vue, PHP, atau `client-and-invoice-generator`):

```html
<!-- Muat SDK dari service bridge lokal -->
<script src="http://127.0.0.1:12212/static/js/hardware-bridge.js"></script>
<script>
  async function testBridge() {
    const bridge = new HardwareBridge();
    await bridge.connect();

    // 1. Silent Print Struk Kasir
    await bridge.printRaw("EPSON TM-T82", "Halo Dunia Kasir!\n\n\n\x1dV\x00");

    // 2. Silent Print Berkas PDF (Base64 atau URL)
    await bridge.printPdf("Printer Kantor", "http://example.com/invoice.pdf");

    // 3. Membaca Timbangan
    const res = await bridge.getWeight();
    console.log("Berat:", res.weight, res.unit, "Stabil:", res.stable);

    // 4. Buka Laci Kasir
    await bridge.openCashDrawer();
  }
</script>
```

---

## 📡 Referensi REST API HTTP (`:18212` / `:12212`)

| Method | Endpoint | Keterangan |
|---|---|---|
| `GET` | `/api/printers` | Daftar seluruh printer lokal (Windows/CUPS) & Jaringan |
| `POST` | `/api/print/raw` | Cetak data mentah (ESC/POS, ZPL, text) |
| `POST` | `/api/print/pdf` | Cetak PDF silent (Base64 atau URL) |
| `POST` | `/api/print/image` | Cetak gambar (Base64) |
| `POST` | `/api/cashdrawer/open` | Buka laci kasir (kick drawer pin 2/5) |
| `POST` | `/api/print/test-receipt` | Cetak struk pengujian ESC/POS |
| `POST` | `/api/print/test-label` | Cetak label pengujian ZPL |
| `GET` | `/api/scales` | Daftar timbangan terdaftar beserta status & beratnya |
| `GET` | `/api/weight` | Membaca berat saat ini |
| `POST` | `/api/scale/stable-read` | Meminta pembacaan bobot yang **DIJAMIN STABIL** |
| `POST` | `/api/scale/zero` | Kirim perintah Zero (Nol) ke timbangan |
| `POST` | `/api/scale/tare` | Kirim perintah Tare ke timbangan |
| `POST` | `/api/scale/pause` | Lepas port serial sementara (untuk Delphi) |
| `POST` | `/api/scale/resume` | Sambungkan kembali port serial |
| `GET` | `/api/serial/ports` | Pindai port serial fisik (COM / ttyUSB) |
| `GET` | `/api/stream` | Server-Sent Events (SSE) streaming data berat |
| `GET` | `/api/download/hardware-bridge.js` | **Download SDK JS Universal** untuk web browser |
| `GET` | `/api/download/erpnext-client-script.js` | **Download Script ERPNext Client Script** |
| `GET` | `/api/download/erpnext-pos-script.js` | **Download Script ERPNext POS Auto-Print** |
| `GET` | `/api/download/all-scripts.zip` | **Download Paket Komplit Semua Script (.ZIP)** |

---

## 🔌 Referensi WebSocket (`ws://127.0.0.1:12212/ws`)

Mendukung format pesan JSON standar `imTigger/webapp-hardware-bridge`:
- `{"action": "getPrinters"}`
- `{"action": "print", "printer": "...", "type": "raw"|"pdf"|"image", "data": "..."}`
- `{"action": "openCashDrawer", "printer": "..."}`
- `{"action": "getSerialPorts"}`
- `{"action": "getWeight", "scale": "..."}`
- `{"action": "subscribeScale"}` (Streaming realtime)
