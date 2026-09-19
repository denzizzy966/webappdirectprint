# 7. Troubleshooting Direct Print

---

## 7.1 Urutan Pemeriksaan Cepat

Kerjakan dari atas; sebagian besar masalah selesai di tiga langkah pertama.

1. **Bridge hidup?** Buka `http://127.0.0.1:18212` di PC operator. Dashboard harus
   tampil. Bila tidak, jalankan `Run_HardwareBridge.bat` atau periksa ikon tray.
2. **Printer terdeteksi?** `http://127.0.0.1:18212/api/printers` harus memuat nama
   printer Anda.
3. **Printer merespons?** Dashboard → Sandbox → **Cetak Struk Contoh** atau
   **Cetak Label ZPL Contoh**. Kalau ini gagal, masalahnya di driver/kabel, bukan
   di aplikasi web.
4. **Data valid?** Tempel Base64 atau URL di Sandbox. Kalau berhasil di sandbox
   tapi gagal dari aplikasi, masalahnya di payload aplikasi.
5. **Baca log:** `logs/hardware_bridge.log` di folder instalasi bridge.

---

## 7.2 Galat di Sisi Browser

| Gejala di Console | Penyebab | Solusi |
|-------------------|----------|--------|
| `Failed to fetch` / `ERR_CONNECTION_REFUSED` | Bridge mati, atau port bukan 18212/12212 | Jalankan bridge; cek port di `bridge_config.json` dan tray |
| `Mixed Content: ... blocked` | Halaman HTTPS memanggil `http://127.0.0.1` | Pakai HTTP, atau izinkan insecure content untuk domain aplikasi |
| `net::ERR_BLOCKED_BY_CLIENT` | Diblokir ekstensi (adblock/privacy) | Nonaktifkan ekstensi pada domain aplikasi |
| `res.ok === false`, `json.detail` terisi | Bridge merespons tetapi cetak gagal | Baca `json.detail` — lihat tabel §7.3 |
| Tidak ada galat, tetapi tidak keluar cetakan | Job masuk antrean namun printer offline/pause | Cek antrean Windows: Devices and Printers → See what's printing |

### Mendiagnosis Mixed Content

```js
console.log(window.location.protocol);   // "https:" → akan diblokir
```

Chrome/Edge: `chrome://settings/content/insecureContent` → **Allowed to show
insecure content** → **Add** → masukkan asal aplikasi Anda (mis.
`https://erp.perusahaan.local`).

---

## 7.3 Galat dari Bridge (`json.detail`)

### Jalur PDF dari URL

| Pesan | Penyebab | Solusi |
|-------|----------|--------|
| `Gagal mengunduh PDF dari URL: 404 Client Error` | Berkas belum ada / nama salah / beda huruf besar-kecil | Buka URL di browser **PC operator** |
| `... Read timed out` | PDF besar atau server lambat (batas 15 detik) | Perkecil PDF, atau kirim Base64 |
| `... Connection refused` / `Max retries exceeded` | PC operator tidak bisa menjangkau server | `Test-NetConnection 192.168.3.25 -Port 80` |
| `... 401` / `... 403` | Berkas di balik autentikasi | Buka akses LAN, atau pakai Base64 (browser yang punya sesi) |
| `... SSLError / CERTIFICATE_VERIFY_FAILED` | HTTPS dengan sertifikat self-signed | Pakai HTTP di LAN, atau pasang CA di PC klien |

### Jalur PDF dari Base64

| Pesan | Penyebab | Solusi |
|-------|----------|--------|
| `Gagal mencetak PDF ke '...': Failed to open stream` | Isinya bukan PDF (HTML, halaman galat, gambar) | Pastikan hasil decode diawali `%PDF-` |
| `Gagal mencetak PDF ke '...': cannot open broken document` | Base64 terpotong / transfer tidak lengkap | Cek panjang string sebelum dikirim |
| `Gagal membaca data PDF atau berkas: ...` | Base64 pendek yang gagal decode dan juga bukan path berkas | Tambahkan prefiks `base64:` |
| `Invalid base64-encoded string` | Ada karakter di luar alfabet Base64 | Buang spasi/newline; jangan URL-encode Base64-nya |

Uji cepat validitas Base64 di konsol browser:

```js
const b64 = '...';                          // tanpa prefiks
const bin = atob(b64.replace(/\s+/g, ''));
console.log(bin.slice(0, 5));               // harus "%PDF-"
```

### Umum

| Pesan | Penyebab | Solusi |
|-------|----------|--------|
| `Backend printer tidak aktif` | `pywin32` (Windows) atau CUPS (Linux) gagal dimuat | `pip install pywin32`; di Linux pastikan `lp` tersedia |
| `Tidak ada printer yang dipilih atau default printer tidak ditemukan` | `printer` kosong dan tidak ada printer bawaan | Isi `printer`, atau atur `default_raw_printer` |
| `Gagal mencetak RAW ke '...': (1801, 'OpenPrinter', ...)` | Nama printer tidak persis | Salin nama dari `/api/printers` |
| `Gagal mencetak PDF ke '...': CreatePrinterDC` | Driver printer bermasalah / printer offline | Cetak halaman uji dari Windows |

---

## 7.4 Masalah Hasil Cetak

| Gejala | Penyebab | Solusi |
|--------|----------|--------|
| Label 60×25 tercetak di tengah kertas A4 | Ukuran kertas tidak diatur di driver | Devices and Printers → Printing Preferences → atur 60×25 mm |
| Hasil cetak terpotong di kanan/bawah | PDF lebih besar dari area cetak | Samakan ukuran halaman PDF dengan ukuran label |
| Hasil cetak buram / bergerigi | DPI terlalu rendah | Kirim `options: { dpi: 203 }` untuk thermal, `300` untuk laser |
| Cetakan lambat, berkas spool besar | DPI terlalu tinggi (PDF dirasterisasi jadi bitmap) | Turunkan `dpi`; 203 sudah cukup untuk label thermal |
| Perintah ZPL tercetak sebagai teks `^XA^FO...` | Printer memakai driver grafis, bukan ZPL | Pasang ulang sebagai "Godex G500 GZPL" / Generic Text |
| Teks selalu di atas, tidak bisa turun | Bridge memakai `dest_y = 0` (rata atas, tengah horizontal) | Atur margin di dalam PDF-nya |
| Karakter Indonesia jadi simbol aneh (RAW) | Encoding tidak cocok | Ubah `printers.default_encoding` ke `cp850` atau `utf-8` |
| Teks pendek RAW tercetak sebagai sampah | Teks ikut ter-decode sebagai Base64 | Awali dengan `\x1B@` atau newline, lihat [04-raw-escpos-zpl.md](04-raw-escpos-zpl.md) §4.1 |

---

## 7.5 Port & Jaringan

| Gejala | Solusi |
|--------|--------|
| Port 18212 dipakai aplikasi lain | Bridge otomatis pindah ke 12212 dan sebaliknya. Lihat log `[Port] Beralih otomatis...` |
| Tidak tahu port aktif | Arahkan kursor ke ikon tray, atau `netstat -ano \| findstr 18212` |
| Ingin memakai port lain | Ubah `server.port` di `bridge_config.json`, lalu `HardwareBridge.configure({ port: 9000 })` di aplikasi |
| Bridge diakses dari PC lain | `server.host` sudah `0.0.0.0`. Buka firewall Windows untuk port tersebut. **Hanya untuk jaringan internal tepercaya** |

---

## 7.6 Membaca Log

```powershell
# 20 baris terakhir
Get-Content .\logs\hardware_bridge.log -Tail 20

# Pantau langsung sambil mencoba cetak
Get-Content .\logs\hardware_bridge.log -Wait -Tail 5

# Saring hanya baris cetak
Select-String -Path .\logs\hardware_bridge.log -Pattern "print|printer" -CaseSensitive:$false | Select-Object -Last 30
```

Baris yang perlu dicari:

```
[WinSpooler] PDF print berhasil ke 'Godex G500 GZPL' (1 halaman)
[WinSpooler] Gagal mencetak PDF ke 'Godex G500 GZPL': ...
[PrinterManager] Menggunakan backend: Windows Spooler
```

---

## 7.7 Template Laporan Masalah

Sertakan informasi berikut agar cepat ditelusuri:

```
1. Versi bridge          : (dari GET /api/status)
2. Sistem operasi        : Windows 11 Pro 24H2 / Linux Mint 22
3. Printer & driver      : Godex G500 GZPL (nama persis dari /api/printers)
4. Jalur yang dipakai    : URL / Base64 / RAW
5. Payload yang dikirim  : (JSON, potong Base64-nya jadi 100 karakter pertama)
6. Respons bridge        : (json.detail atau json.result lengkap)
7. Potongan log          : 20 baris terakhir logs/hardware_bridge.log
8. Sudah dicoba di       : Dashboard Sandbox? berhasil / gagal
```
