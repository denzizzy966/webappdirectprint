# 📖 Panduan Integrasi ERPNext dengan Hardware Bridge

Panduan ini menjelaskan cara menghubungkan aplikasi web **ERPNext (v13, v14, atau v15)** dengan printer kasir (ESC/POS), label printer (ZPL/TSPL), dan timbangan digital melalui **WebApp Hardware Bridge**.

---

## 1. Konsep Arsitektur

```
┌─────────────────────────────────────────────────────────────┐
│  Server ERPNext (Cloud VPS / Docker / WSL / Ubuntu Server)   │
│  - Database MariaDB                                         │
│  - Python Frappe Backend                                    │
│  - Web Frontend (HTML/JS)                                   │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / HTTP
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  PC Kasir / Komputer Pengguna (Windows 10/11 / Linux Mint)  │
│  ┌─────────────────────────┐     ┌───────────────────────┐  │
│  │   Browser Web Kasir     │     │ Hardware Bridge       │  │
│  │   (Tab ERPNext)         │────►│ (Local Service :12212)│  │
│  └─────────────────────────┘     └───────────┬───────────┘  │
│                                              │              │
│       ┌──────────────────────────────────────┴────────┐     │
│       ▼ USB Cable                                     ▼ COM │
│  ┌───────────────────────┐              ┌────────────────┐  │
│  │ Printer Struk Thermal │              │ Timbangan RS232│  │
│  └───────────────────────┘              └────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

> **Catatan Penting:**  
> Server ERPNext **tidak memiliki kabel fisik** ke meja kasir Anda. Oleh karena itu, script di browser kasir mengirim perintah ke **Hardware Bridge yang berjalan di komputer lokal kasir** (`http://127.0.0.1:12212`).

---

## 2. Cara Pasang di ERPNext (Client Script)

### Langkah 1: Buka Menu Client Script
1. Login ke ERPNext sebagai Administrator atau pengguna dengan hak akses *System Manager*.
2. Pada Awesome Search Bar di bagian atas, ketik **Client Script** lalu tekan Enter.
3. Klik tombol biru **+ Add Client Script**.

### Langkah 2: Konfigurasi Form
- **DocType**: Pilih `POS Invoice` (atau `Sales Invoice` / `Delivery Note`).
- **Apply To**: `Form`
- **Enabled**: Centang (Aktifkan).
- **Script**: Salin dan tempel kode dari berkas [`erpnext_hardware_bridge.js`](file:///D:/Workspaces-gemini/webappdirectprint/erpnext/erpnext_hardware_bridge.js).
- Klik **Save**.

### Langkah 3: Uji Coba di ERPNext
1. Buka salah satu dokumen **POS Invoice**.
2. Anda akan melihat menu baru di tombol **Aksi Cepat**:
   - `🖨️ Cetak Struk (Direct Print)`: Mencetak struk thermal seketika tanpa membuka dialog browser (`Ctrl+P`).
   - `💵 Buka Laci Kasir`: Mengirim pulsa kick drawer ke printer kasir.
   - `⚖️ Timbang Item Aktif`: Membaca bobot dari timbangan digital dan mengisinya ke kolom Quantity.

---

## 3. Penanganan Mixed Content (HTTPS ERPNext vs HTTP Localhost)

Jika ERPNext Anda diakses melalui HTTPS (misal `https://erp.perusahaan.com`):

1. **Spesifikasi W3C Private Network Access:**
   Peramban berbasis Chromium (Google Chrome, Microsoft Edge, Brave) mengizinkan koneksi dari origin HTTPS publik ke `http://127.0.0.1` atau `http://localhost` secara lokal.
2. **Jika Browser Memblokir (Insecure Content):**
   - Klik ikon **Gembok / Setelan Situs** di sebelah kiri URL bar browser.
   - Pada opsi **Insecure content (Konten tidak aman)**, ubah dari *Block* menjadi **Allow (Izinkan)**.
   - Atau gunakan koneksi **WebSocket** (`ws://127.0.0.1:12212`) yang didukung langsung oleh SDK `hardware-bridge.js`.

---

## 4. Format Perintah Struk Kustom (ESC/POS)

Anda dapat menyesuaikan format struk kasir pada fungsi `directPrintInvoice`:
- Ubah lebar karakter: `char_width = 40` (untuk kertas 80mm) atau `32` (untuk kertas 58mm).
- Tambahkan logo toko dengan encoding Base64 atau perintah cetak gambar `/api/print/image`.
- Potong kertas: `\x1d\x56\x42\x00` (GS V 66 0).
- Buka laci kasir: `\x1b\x70\x00\x19\xfa` (ESC p 0 25 250).

---

## 5. Fitur Printer Pool & Target Alias (imTigger Compatible)

Sama seperti pada imTigger `webapp-hardware-bridge`, Anda **tidak perlu meng-hardcode nama printer fisik** di kode ERPNext Anda.

### Cara Kerja:
1. Script ERPNext hanya mengirim nama alias/pool target:
   - `"printer": "asset_label"` (untuk label aset / barcode)
   - `"printer": "receipt"` (untuk struk kasir)
   - `"printer": "invoice"` (untuk faktur penjualan PDF / A4)
   - Atau kompatibel langsung dengan format `whb_print.js` (`{"type": "asset_label", "file_content": "..."}`).
2. **Dashboard Hardware Bridge** (`http://127.0.0.1:18212` -> Tab **Pengaturan**) memetakan alias target tersebut ke printer fisik yang terpasang di komputer kasir/packing (misalnya `"Godex G500 GZPL"` atau `"EPSON TM-T82"`).
3. Jika komputer berganti printer atau driver, Anda cukup mengubah pemetaan di Dashboard Web Bridge tanpa mengubah 1 baris kode pun di ERPNext!

