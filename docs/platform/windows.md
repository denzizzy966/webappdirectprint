# 🪟 Panduan Windows 10 / 11
### WebApp Hardware Bridge Universal

Ada **dua cara** memakai bridge di Windows. Pilih salah satu sesuai kebutuhan:

| Anda ingin… | Pakai ini |
|---|---|
| **Memasang di PC kasir / produksi** | **Paket Portable** — `HardwareBridge_Windows_x64_Portable.zip` |
| Mengembangkan atau mengubah kode | Jalankan dari kode sumber — folder `windows/` |

Kalau ragu, pakai **Paket Portable**.

---

## 📦 Cara 1 — Paket Portable (Disarankan)

Paket portable setara dengan `install.sh` di Linux: satu klik, semuanya beres.
Tidak butuh Python, tidak butuh internet.

### Tiga langkah

**1. Ekstrak dulu**

Klik kanan `HardwareBridge_Windows_x64_Portable.zip` → **Extract All…**

> ⚠️ Jangan klik `INSTALL.bat` dari dalam ZIP. Windows hanya *mengintip* isi ZIP,
> berkas pendukung belum benar-benar ada di disk, dan installer akan gagal.

Saran lokasi ekstrak: `C:\HardwareBridge`

**2. Klik ganda `INSTALL.bat`**

Installer akan otomatis:

| Tahap | Yang dikerjakan |
|---|---|
| 1/6 | Memastikan `HardwareBridge.exe` benar-benar ada (mendeteksi ZIP yang belum diekstrak) |
| 2/6 | Membuat `bridge_config.json` bawaan Windows + folder `logs\`, lalu membaca nomor port |
| 3/6 | Menghentikan instance lama agar tidak dobel |
| 4/6 | Memasang auto-start di folder Startup + shortcut dashboard di Desktop |
| 5/6 | Menjalankan bridge di System Tray |
| 6/6 | Memverifikasi `/api/status` benar-benar menjawab (port utama & cadangan `12212`) |

Kalau berhasil, muncul ringkasan status dan dashboard terbuka sendiri di browser.
Kalau gagal, installer menyebutkan penyebab yang paling mungkin beserta solusinya.

**3. Atur printer & timbangan lewat Dashboard**

Dashboard terbuka otomatis di `http://127.0.0.1:18212`.

Selesai — bridge menyala sendiri setiap kali Windows login.

### Isi paket portable

| Berkas | Fungsi |
|---|---|
| **`INSTALL.bat`** | **Pasang sekali klik**: auto-start + jalankan + verifikasi |
| `UNINSTALL.bat` | Copot auto-start, hentikan service, hapus aturan firewall |
| `Jalankan.bat` | Jalankan sekali saja, tanpa memasang auto-start |
| `Cek_Status.bat` | Cek bridge hidup/tidak, port aktif, + 20 baris log terakhir |
| `Jalankan_Konsol.bat` | Mode diagnosa: restart bridge lalu tampilkan log real-time |
| `Izinkan_Akses_LAN.bat` | **Opsional**, buka Windows Firewall agar bisa diakses PC lain |
| `Jalankan_Diam.vbs` | Penolong runner senyap (dipakai otomatis) |
| `bridge_config.json` | Setelan printer, timbangan, port |
| `BACA_SAYA.txt` | Panduan singkat di dalam paket |
| `HardwareBridge.exe` + `_internal\` | Aplikasi dan pustakanya — jangan dipisah |
| `docs\`, `sdk\` | Dokumentasi lengkap & SDK JavaScript, ikut offline |

### Padanan perintah Linux

| Linux | Windows (paket portable) |
|---|---|
| `sudo bash linux/install.sh` | klik ganda `INSTALL.bat` |
| `sudo bash linux/uninstall.sh` | klik ganda `UNINSTALL.bat` |
| `sudo systemctl status hardware-bridge` | klik ganda `Cek_Status.bat` |
| `sudo systemctl restart hardware-bridge` | klik kanan ikon tray → **Restart Service** |
| `journalctl -u hardware-bridge -f` | klik ganda `Jalankan_Konsol.bat` |
| `bash linux/run.sh` | klik ganda `Jalankan.bat` |

---

## 💻 Cara 2 — Jalankan dari Kode Sumber

Untuk pengembangan atau saat Anda ingin mengubah kode Python.

**Prasyarat:** Python 3.10+ dengan opsi **"Add Python to PATH"** dicentang saat instalasi.

| Berkas di `windows/` | Fungsi |
|---|---|
| `run.bat` | Pasang dependensi lalu jalankan di jendela CMD (log terlihat langsung) |
| `run_background.vbs` | Jalankan di latar belakang dengan ikon tray, tanpa jendela CMD |
| `install_autostart.bat` | Pasang auto-start yang menunjuk ke `run_background.vbs` |
| `uninstall_autostart.bat` | Copot auto-start tersebut |
| **`build_portable.bat`** | **Bangun `.exe` + rakit ZIP portable** siap bagi |

```cmd
windows\run.bat
```

### Membangun paket portable sendiri

```cmd
windows\build_portable.bat
```

Skrip ini menjalankan PyInstaller, lalu merakit hasilnya bersama seluruh isi
`windows\portable\`, `docs\`, dan SDK menjadi
`HardwareBridge_Windows_x64_Portable.zip` di root proyek.

> Ingin mengubah isi paket portable (misal menambah berkas atau mengubah teks
> installer)? Sunting berkas di `windows\portable\`, lalu jalankan ulang
> `build_portable.bat`.

---

## 🛠️ Masalah Umum di Windows

#### `HardwareBridge.exe tidak ditemukan` saat INSTALL.bat dijalankan
ZIP belum diekstrak. Klik kanan ZIP → **Extract All…**, lalu jalankan
`INSTALL.bat` dari folder hasil ekstrak.

#### Ikon tray tidak muncul / bridge tidak mau hidup
1. Klik ganda `Jalankan_Konsol.bat` dan baca log yang tampil.
2. Paling sering penyebabnya Windows Defender. Buka **Windows Security →
   Virus & threat protection → Manage settings → Exclusions → Add folder**,
   lalu pilih folder Hardware Bridge.

#### Dashboard tidak bisa dibuka di `18212`
Bridge otomatis pindah ke port cadangan `12212` bila `18212` sudah dipakai
aplikasi lain. `Cek_Status.bat` memeriksa kedua port sekaligus.

#### Port timbangan `Access is denied` (Error 13)
Port COM sedang dikunci eksklusif oleh aplikasi lain (umumnya program kasir
Delphi lawas). Tekan tombol **`⏸️ Lepas Port (Delphi)`** di dashboard, atau ubah
`"sharing_mode"` menjadi `"on_demand"` di `bridge_config.json` — port akan
dilepas otomatis setiap kali idle 4 detik.

#### Kabel USB timbangan dipindah ke lubang USB lain
Tidak masalah. Isi `"usb_serial"` pada `bridge_config.json` dengan serial number
adapter USB (misal `BMCBE14A312`); bridge melacaknya otomatis ke port COM mana
pun, `COM5` → `COM1` sekalipun.

#### Driver Prolific PL2303 bertanda seru kuning (Code 10)
Chip PL2303 clone/lawas tidak didukung driver Windows 11 terbaru. Pasang driver
Prolific versi 3.3.2 (2008), atau ganti kabel ke chipset FTDI / CH340.

#### Aplikasi web di PC lain tidak bisa memanggil bridge
Jalankan `Izinkan_Akses_LAN.bat` (minta hak Administrator) dan pastikan `"host"`
di `bridge_config.json` bernilai `"0.0.0.0"`.

---

*Panduan instalasi lengkap lintas platform: [../03-instalasi.md](../03-instalasi.md)*
*Padanan untuk Linux: [linux.md](linux.md)*
