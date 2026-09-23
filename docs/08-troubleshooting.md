# 🛠️ Troubleshooting Umum

Masalah **cetak** dibahas terpisah dan lebih rinci di
[direct-print/07-troubleshooting-print.md](direct-print/07-troubleshooting-print.md).
Halaman ini untuk bridge, port, timbangan, instalasi, dan jaringan.

---

## 1. Bridge Tidak Mau Jalan

| Gejala | Penyebab | Solusi |
|--------|----------|--------|
| Jendela konsol muncul lalu langsung tertutup | Galat Python saat startup | Jalankan `python app.py` dari terminal agar pesan galatnya terbaca |
| `ModuleNotFoundError: No module named 'win32print'` | pywin32 belum terpasang | `pip install pywin32` |
| `ModuleNotFoundError: No module named 'fitz'` | PyMuPDF belum terpasang | `pip install pymupdf` |
| `[Errno 98] Address already in use` | Port dipakai instance lain | Tutup instance lama, atau ubah `server.port` |
| Ikon tray tidak muncul | `pystray`/Pillow tidak tersedia, atau `--no-tray` | Cek log `[Tray] System tray dinonaktifkan...`. Bridge tetap jalan tanpa tray |
| Sudah jalan tapi dashboard kosong | Template Jinja2 tidak ditemukan pada build frozen | Cek folder `_internal/templates` di samping executable |

```bash
# Jalankan dengan log verbose
python app.py

# Cek proses & port yang dipakai (Windows)
netstat -ano | findstr "18212 12212"
tasklist | findstr HardwareBridge
```

---

## 2. Port

Bridge memakai `18212` dan otomatis berpindah ke `12212` bila terpakai (dan
sebaliknya). Perpindahan ini tercatat di log:

```
[Port] Port 18212 sedang dipakai oleh aplikasi lain!
[Port] Beralih otomatis ke port alternatif: 12212
```

| Situasi | Solusi |
|---------|--------|
| Tidak tahu port aktif | Arahkan kursor ke ikon tray, atau baca log `[Server] Berjalan di: ...` |
| Aplikasi web memakai port tetap | SDK sudah mencoba 12212 otomatis. Untuk port lain: `HardwareBridge.configure({ port: 9000 })` |
| Ingin memaksa satu port | Ubah `server.port` di `bridge_config.json`, pastikan port itu bebas |
| Timbangan ingin port sendiri | Isi `server.scale_port`, lalu `HardwareBridge.configure({ scalePort: ... })` |

---

## 3. Akses dari PC Lain

Bawaan `server.host` adalah `0.0.0.0`, jadi bridge sudah mendengarkan seluruh
antarmuka. Yang biasanya memblokir adalah Firewall Windows.

```powershell
# Izinkan port 18212 masuk (jalankan sebagai Administrator)
New-NetFirewallRule -DisplayName "Hardware Bridge 18212" `
                    -Direction Inbound -Protocol TCP -LocalPort 18212 -Action Allow
```

> ⚠️ Bridge **tidak punya autentikasi**. Siapa pun yang bisa menjangkau portnya
> dapat mencetak dan membaca timbangan. Buka akses hanya di jaringan internal
> tepercaya; bila tidak perlu, set `server.host` ke `127.0.0.1`.

---

## 4. Halaman HTTPS Tidak Bisa Memanggil Bridge

Browser memblokir permintaan `http://127.0.0.1` dari halaman `https://`
(mixed content).

| Opsi | Cara |
|------|------|
| Sajikan aplikasi lewat HTTP | Paling sederhana untuk jaringan internal |
| Izinkan insecure content | Chrome/Edge: `chrome://settings/content/insecureContent` → **Add** → asal aplikasi Anda |
| Pasang sertifikat di bridge | Butuh sertifikat tepercaya di tiap PC klien |

Catatan: pembatasan ini hanya untuk panggilan browser → bridge. Unduhan
bridge → server PDF internal tidak terpengaruh.

---

## 5. Timbangan

| Gejala | Penyebab | Solusi |
|--------|----------|--------|
| Timbangan tidak muncul di daftar | Belum didaftarkan di `bridge_config.json` | Tambahkan ke bagian `scales`, atau pakai `POST /api/connect` |
| `Timbangan '...' tidak ditemukan` (404) | Nama tidak cocok | Cek nama persis lewat `GET /api/scales` |
| Terhubung tapi berat selalu `null` | Baud/protokol salah | Dashboard → **Scan Baud**, atau coba protokol lain |
| `Access is denied` pada port COM | Port dipakai aplikasi lain (Delphi, terminal) | Tutup aplikasi itu, atau pakai **Lepas Port** di dashboard |
| Berat tidak pernah stabil | Ambang stabilitas protokol tidak terpenuhi | Naikkan `timeout`, atau pakai `/api/weight` (tanpa syarat stabil) |
| Ingin memakai Web Serial API browser | Bridge memegang port COM | Set `enable_scale_at_startup: false` (bawaan) |
| Data berat basi (`age` besar) | Polling terhenti | Cek `GET /api/state` untuk log RX/TX |

Diagnosis lengkap, protokol, dan console interaktif:
[06-timbangan-serial.md](06-timbangan-serial.md).

---

## 6. Auto-Start Tidak Berjalan

### Windows

| Gejala | Solusi |
|--------|--------|
| Ingin tahu kondisi bridge saat ini | Klik ganda `Cek_Status.bat` — menampilkan proses, status auto-start, port aktif, dan 20 baris log terakhir |
| Tidak jalan setelah reboot | Jalankan ulang `INSTALL.bat` (tidak perlu Administrator) |
| `INSTALL.bat` bilang `HardwareBridge.exe TIDAK DITEMUKAN` | ZIP belum diekstrak. Klik kanan ZIP → **Extract All…**, lalu jalankan dari folder hasil ekstrak |
| Terpasang tapi tetap tidak hidup | Klik ganda `Jalankan_Konsol.bat` untuk melihat log real-time; paling sering diblokir Windows Defender (tambahkan foldernya ke **Exclusions**) |
| Ingin memeriksa entri startup | Ketik `shell:startup` di Run — cari `HardwareBridge.lnk` |
| Ingin mencopot | `UNINSTALL.bat` |
| Menjalankan dari kode sumber, bukan paket portable | `windows\install_autostart.bat` / `windows\uninstall_autostart.bat` |

### Linux

```bash
systemctl --user status hardware-bridge      # atau: sudo systemctl status hardware-bridge
journalctl --user -u hardware-bridge -f
sudo systemctl restart hardware-bridge
```

| Gejala | Solusi |
|--------|--------|
| Service gagal start | `journalctl -u hardware-bridge -n 50` |
| Tidak bisa akses `/dev/ttyUSB0` | `sudo usermod -aG dialout $USER`, lalu logout-login |
| Perlu aturan udev | Salin `linux/99-hardware-bridge.rules` ke `/etc/udev/rules.d/` lalu `sudo udevadm control --reload` |

---

## 7. Membaca Log

Log tersimpan di `logs/hardware_bridge.log` (folder instalasi bridge).

```powershell
Get-Content .\logs\hardware_bridge.log -Tail 30
Get-Content .\logs\hardware_bridge.log -Wait -Tail 5      # pantau langsung
```

```bash
tail -n 30 logs/hardware_bridge.log
tail -f logs/hardware_bridge.log
```

Baris penanda yang berguna:

| Awalan | Arti |
|--------|------|
| `[START]` / `[STOP]` | Bridge dijalankan / dimatikan |
| `[Server] Berjalan di:` | Alamat & port aktif |
| `[Port]` | Perpindahan port otomatis |
| `[PrinterManager]` | Backend printer yang dipakai |
| `[WinSpooler]` / `[CUPS]` | Hasil tiap job cetak |
| `[Tray]` | Status system tray |
| `[ScaleServer]` | Listener port timbangan terpisah |

---

## 8. Perintah Diagnosis Cepat

```bash
# Bridge hidup?
curl http://127.0.0.1:18212/api/status

# Printer terdeteksi?
curl http://127.0.0.1:18212/api/printers

# Timbangan terdeteksi?
curl http://127.0.0.1:18212/api/scales

# Port serial fisik?
curl http://127.0.0.1:18212/api/serial/ports

# Konfigurasi aktif?
curl http://127.0.0.1:18212/api/config

# Riwayat cetak terakhir?
curl http://127.0.0.1:18212/api/print/history
```

---

## 9. Informasi untuk Laporan Masalah

```
1. Versi bridge      : (GET /api/status → version)
2. Sistem operasi    : (GET /api/status → os_details)
3. Cara menjalankan  : portable .exe / python app.py / systemd
4. Port aktif        : (log [Server] Berjalan di: ...)
5. Langkah reproduksi
6. Pesan galat       : dari konsol browser DAN dari json.detail
7. Potongan log      : 30 baris terakhir logs/hardware_bridge.log
8. bridge_config.json: (sensor bagian yang sensitif)
```
