# 📚 Dokumentasi WebApp Hardware Bridge Universal

Seluruh dokumentasi proyek ini terkumpul di folder `docs/`. Berkas di luar folder
ini hanya `README.md` (halaman muka repositori) dan `windows/portable/BACA_SAYA.txt`
(catatan singkat yang ikut di dalam paket portable Windows).

Folder `docs/` ini juga ikut dibundel ke dalam `HardwareBridge_Windows_x64_Portable.zip`,
sehingga PC kasir tetap punya dokumentasi lengkap walau sedang offline.

---

## 🚀 Mulai dari Mana?

| Kebutuhan Anda | Buka |
|----------------|------|
| "Saya ingin langsung mencetak dari aplikasi web saya" | [direct-print/](direct-print/) |
| "Kirim HTML yang dikonversi ke Base64 ke printer" | [direct-print/02-html-ke-base64.md](direct-print/02-html-ke-base64.md) |
| "Cetak PDF dari `http://192.168.3.25/produksi/ProduksiPDF/...`" | [direct-print/03-pdf-dari-url.md](direct-print/03-pdf-dari-url.md) |
| "PDF gagal dicetak di printer label Godex / Zebra" | [direct-print/08-printer-label-zpl.md](direct-print/08-printer-label-zpl.md) |
| "Bagaimana cara memasang bridge di PC kasir Windows?" | [platform/windows.md](platform/windows.md) |
| "Bagaimana cara memasang bridge di PC kasir Linux?" | [platform/linux.md](platform/linux.md) |
| "Panduan instalasi lengkap kedua platform" | [03-instalasi.md](03-instalasi.md) |
| "Kenapa harus dipasang di PC klien, bukan di server?" | [01-arsitektur.md](01-arsitektur.md) |
| "Saya mau membaca timbangan digital dari browser" | [06-timbangan-serial.md](06-timbangan-serial.md) |
| "Cetak tidak jalan, harus cek apa?" | [08-troubleshooting.md](08-troubleshooting.md) |

---

## 📑 Daftar Lengkap

### Dokumen Utama

| No | Berkas | Isi |
|----|--------|-----|
| 01 | [01-arsitektur.md](01-arsitektur.md) | Mengapa bridge berjalan di PC klien, perbandingan dengan cetak dari sisi server |
| 02 | [02-quickstart.md](02-quickstart.md) | Menjalankan bridge dan mencetak pertama kali dalam 5 menit |
| 03 | [03-instalasi.md](03-instalasi.md) | Panduan instalasi & deployment lengkap (Windows 10/11 dan Linux Mint 22 / Ubuntu 22) |
| 04 | [04-konfigurasi.md](04-konfigurasi.md) | Referensi seluruh parameter `bridge_config.json` |
| 05 | [05-api-reference.md](05-api-reference.md) | Seluruh endpoint REST & WebSocket (printer, timbangan, sistem) |
| 06 | [06-timbangan-serial.md](06-timbangan-serial.md) | Timbangan digital RS232/serial, multi-timbangan, protokol, port sharing |
| 07 | [07-sdk-javascript.md](07-sdk-javascript.md) | Referensi `hardware-bridge.js` untuk browser / Laravel / Vue / React |
| 08 | [08-troubleshooting.md](08-troubleshooting.md) | Masalah umum bridge, port, timbangan, dan jaringan |

### 🖨️ Direct Print (Silent Print)

| Berkas | Isi |
|--------|-----|
| [direct-print/README.md](direct-print/README.md) | Ringkasan & peta seluruh panduan cetak |
| [direct-print/01-konsep-dan-alur.md](direct-print/01-konsep-dan-alur.md) | Alur data browser → bridge → printer, format data yang diterima |
| [direct-print/02-html-ke-base64.md](direct-print/02-html-ke-base64.md) | **HTML → Base64 → cetak** (html2pdf, jsPDF, dompdf, html2canvas, ESC/POS) |
| [direct-print/03-pdf-dari-url.md](direct-print/03-pdf-dari-url.md) | **Cetak PDF dari URL server**, contoh `192.168.3.25/produksi/ProduksiPDF/` |
| [direct-print/04-raw-escpos-zpl.md](direct-print/04-raw-escpos-zpl.md) | ESC/POS, ZPL, TSPL, laci kasir, printer jaringan 9100 |
| [direct-print/05-printer-target-pool.md](direct-print/05-printer-target-pool.md) | Memilih printer: nama fisik, alias pool, urutan resolusi |
| [direct-print/06-referensi-api-print.md](direct-print/06-referensi-api-print.md) | Referensi payload & respons endpoint cetak |
| [direct-print/07-troubleshooting-print.md](direct-print/07-troubleshooting-print.md) | Daftar galat cetak beserta solusinya |
| [direct-print/08-printer-label-zpl.md](direct-print/08-printer-label-zpl.md) | **Mode ZPL Raster** untuk printer label Godex / Zebra |

### 🔌 Integrasi

| Berkas | Isi |
|--------|-----|
| [integrasi/erpnext.md](integrasi/erpnext.md) | Client Script ERPNext, POS Awesome, kompatibilitas `whb_print.js` |
| [integrasi/laravel.md](integrasi/laravel.md) | Blade, Livewire, Vue/Inertia, dompdf |

### 💻 Catatan Per Platform

| Berkas | Isi |
|--------|-----|
| [platform/windows.md](platform/windows.md) | **Paket portable sekali klik**, auto-start, `Cek_Status.bat`, build ZIP |
| [platform/linux.md](platform/linux.md) | `install.sh`, systemd service, udev rules |

---

## 🗺️ Peta Berkas Proyek

```
webappdirectprint/
├── app.py                     Titik masuk: FastAPI + uvicorn + system tray
├── bridge_config.json         Konfigurasi printer, pool, timbangan, port
├── app/
│   ├── config.py              ConfigManager, BASE_DIR, nilai bawaan
│   ├── api/
│   │   ├── routes_http.py     Seluruh endpoint REST /api/*
│   │   └── routes_ws.py       WebSocket /ws (kompatibel whb_print.js)
│   ├── printer/
│   │   ├── printer_manager.py Resolusi printer, format data, pemilihan mode
│   │   ├── pdf_to_zpl.py      Konversi PDF/gambar menjadi ZPL raster ^GFA
│   │   ├── win_spooler.py     Windows: Win32 Spooler + PyMuPDF + GDI
│   │   ├── cups_linux.py      Linux: perintah lp / CUPS
│   │   ├── network_socket.py  Printer jaringan TCP 9100
│   │   └── escpos_builder.py  Pembangun perintah ESC/POS & ZPL
│   └── serial_scale/          Timbangan serial & protokolnya
├── static/
│   ├── js/hardware-bridge.js  SDK JavaScript untuk aplikasi web
│   ├── js/app.js              Logika dashboard bawaan
│   └── cara-pakai.html        Halaman demo interaktif
├── templates/index.html       Dashboard bridge
├── erpnext/                   Client Script siap pakai untuk ERPNext
├── laravel/                   Salinan SDK & demo untuk proyek Laravel
├── windows/
│   ├── portable/              📦 Isi paket portable (INSTALL.bat dll) - sumber kebenaran
│   ├── build_portable.bat     Bangun .exe + rakit ZIP portable siap bagi
│   └── run.bat , ...          Menjalankan dari kode sumber (pengembangan)
├── linux/                     install.sh, systemd service, udev rules, wheels offline
└── docs/                      📚 Folder ini (ikut dibundel ke paket portable)
```

---

## 🔗 Tautan Cepat

| Sumber Daya | Alamat |
|-------------|--------|
| Dashboard bridge | `http://127.0.0.1:18212` |
| Halaman demo interaktif | `http://127.0.0.1:18212/static/cara-pakai.html` |
| Dokumentasi API otomatis (Swagger) | `http://127.0.0.1:18212/docs` |
| Unduh SDK JavaScript | `http://127.0.0.1:18212/api/download/hardware-bridge.js` |
| Unduh paket lengkap SDK + panduan | `http://127.0.0.1:18212/api/download/all-scripts.zip` |
| Berkas log | `logs/hardware_bridge.log` |
