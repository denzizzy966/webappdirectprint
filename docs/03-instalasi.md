# 📖 Buku Panduan Instalasi & Deployment (Installer Guide)
### WebApp Hardware Bridge Universal — Windows 10/11 & Linux Mint 22 / Ubuntu 22

Dokumen ini berisi panduan langkah demi langkah cara memasang (*install*), mengonfigurasi, menjalankan otomatis (*auto-start / systemd service*), dan mengelola **WebApp Hardware Bridge Universal** pada sistem operasi **Windows** dan **Linux**.

---

## 📑 Daftar Isi
1. [Arsitektur & Mengapa Harus di Client PC](#-arsitektur--mengapa-harus-di-client-pc)
2. [Persyaratan Sistem (Prerequisites)](#-persyaratan-sistem-prerequisites)
3. [Panduan Instalasi Windows 10 / 11](#-panduan-instalasi-windows-10--11)
   - [Cara A — Paket Portable, sekali klik (Disarankan)](#cara-a--paket-portable-sekali-klik-disarankan)
   - [Cara B — Jalankan dari Kode Sumber](#cara-b--jalankan-dari-kode-sumber)
   - [Membangun Paket Portable Sendiri (`build_portable.bat`)](#membangun-paket-portable-sendiri-build_portablebat)
   - [Mencopot Hardware Bridge di Windows](#mencopot-hardware-bridge-di-windows)
   - [Troubleshooting & Solusi Masalah Windows](#troubleshooting--solusi-masalah-windows)
4. [Panduan Instalasi Linux Mint 22 / Ubuntu 22](#-panduan-instalasi-linux-mint-22--ubuntu-22)
   - [Metode 1: Pemasangan Otomatis Systemd Service (`install.sh`)](#metode-1-pemasangan-otomatis-systemd-service-installsh)
   - [Metode 2: Menjalankan Sementara di Konsol (`run.sh`)](#metode-2-menjalankan-sementara-di-konsol-runsh)
   - [Metode 3: Membangun Binary Executable Linux ELF (`build_linux.sh`)](#metode-3-membangun-binary-executable-linux-elf-build_linuxsh)
   - [Pengelolaan Service Systemd (Status, Restart, Logs)](#pengelolaan-service-systemd-status-restart-logs)
   - [Mencopot Service Linux (`uninstall.sh`)](#mencopot-service-linux-uninstallsh)
   - [Troubleshooting & Solusi Masalah Linux](#troubleshooting--solusi-masalah-linux)
5. [Konfigurasi Port & Hardware (`bridge_config.json`)](#-konfigurasi-port--hardware-bridge_configjson)
6. [Verifikasi Setelah Instalasi](#-verifikasi-setelah-instalasi)

---

## 🏗️ Arsitektur & Mengapa Harus di Client PC?

> **Tanya:** Apakah service ini bisa dipasang di server ERPNext (VPS Cloud / Docker / WSL)? Atau wajib di PC Client kasir?

* **Wajib di Client PC:**
  Printer thermal kasir (USB) dan timbangan digital (RS-232 / USB serial) terhubung secara fisik dengan kabel ke komputer lokal di meja kasir. Server ERPNext di cloud atau WSL tidak memiliki akses kabel fisik ke perangkat kasir tersebut. Selain itu, browser kasir dibatasi oleh *browser sandbox* keamanan sehingga tidak diizinkan mengakses port USB/COM komputer tanpa perantara daemon lokal.
* **Service Bridge:**
  Berfungsi sebagai agen lokal di PC kasir yang membuka port HTTP & WebSocket (`127.0.0.1:18212` atau `12212`). Halaman web kasir (ERPNext, POS, dsb.) mengirimkan perintah cetak atau meminta berat timbangan ke bridge ini, dan bridge akan meneruskannya ke driver printer atau port serial timbangan secara instan dan tanpa dialog browser.

---

## 📋 Persyaratan Sistem (Prerequisites)

### 🪟 Windows 10 / 11:
1. **Python 3.10+ — HANYA bila Anda menjalankan dari kode sumber.**
   * Pastikan opsi **"Add Python to PATH"** dicentang saat instalasi Python.
   * **Pengguna paket portable tidak perlu Python sama sekali.** Python, seluruh
     pustaka, dashboard, dan dokumentasi sudah ikut di dalam ZIP.
2. **Driver USB Serial Converter:**
   * Prolific PL2303 / PL2303GS (bawaan Windows Update atau driver resmi Prolific).
   * CH340 / CH341 (untuk timbangan murah / adapter biru CH340).
   * FTDI FT232R / Silicon Labs CP2102.
3. **Driver Printer Windows:**
   * Printer terpasang di *Devices & Printers* Windows dan bisa mencetak Test Page.

### 🐧 Linux Mint 22 / Ubuntu 22 LTS:
1. **Python 3.10+** dan `python3-venv` (`sudo apt install python3 python3-venv python3-pip`).
2. **CUPS Printing System** (`sudo apt install cups cups-client libcups2-dev`).
3. **Akses root / sudo** untuk registrasi service systemd dan udev rules.

---

## 🪟 Panduan Instalasi Windows 10 / 11

Ada dua jalur. **Untuk PC kasir / produksi, pakai Cara A.**

| Kebutuhan | Jalur |
|---|---|
| Memasang di PC kasir / produksi | **Cara A — Paket Portable** (tanpa Python, tanpa internet) |
| Mengembangkan / mengubah kode Python | Cara B — Jalankan dari kode sumber |

---

### Cara A — Paket Portable, sekali klik (Disarankan)

Ini padanan Windows dari `sudo bash linux/install.sh`. Satu berkas ZIP, satu
klik, semuanya beres: auto-start terpasang, service jalan, dashboard terbuka.

#### Langkah 1 — Ekstrak ZIP

Klik kanan `HardwareBridge_Windows_x64_Portable.zip` → **Extract All… / Ekstrak Semua**.

> ⚠️ **Jangan klik `INSTALL.bat` langsung dari dalam ZIP.** Windows hanya
> *mengintip* isi ZIP; berkas pendukung belum benar-benar ada di disk sehingga
> installer pasti gagal. Installer mendeteksi kesalahan ini dan memberi tahu Anda,
> tetapi lebih baik diekstrak dari awal.

Saran lokasi: `C:\HardwareBridge`

#### Langkah 2 — Klik ganda `INSTALL.bat`

Tidak perlu hak Administrator. Installer berjalan enam tahap:

| Tahap | Yang dikerjakan |
|---|---|
| **1/6** | Memastikan `HardwareBridge.exe` ada; mendeteksi ZIP yang belum diekstrak dan mode kode sumber |
| **2/6** | Membuat `bridge_config.json` bawaan Windows bila belum ada, membuat folder `logs\`, membaca nomor port dari konfigurasi |
| **3/6** | Menghentikan instance lama (`taskkill`) supaya port tidak bentrok dengan diri sendiri |
| **4/6** | Memasang shortcut auto-start di folder Startup Windows + shortcut dashboard di Desktop |
| **5/6** | Menjalankan bridge di System Tray |
| **6/6** | **Memverifikasi** `/api/status` benar-benar menjawab, memeriksa port utama maupun port cadangan `12212` |

Bila sukses, muncul ringkasan seperti ini lalu dashboard terbuka sendiri:

```
==========================================================
  PEMASANGAN SELESAI - HARDWARE BRIDGE SUDAH BERJALAN
==========================================================
  Status      : Aktif / Online
  System Tray : Ikon hijau di pojok kanan bawah dekat jam
  Dashboard   : http://127.0.0.1:18212
  WebSocket   : ws://127.0.0.1:18212/ws
  Auto-start  : AKTIF, otomatis nyala tiap login Windows
  Berkas log  : C:\HardwareBridge\logs\hardware_bridge.log
==========================================================
```

Bila gagal, installer menyebutkan penyebab yang paling mungkin (antivirus, port
bentrok, izin tulis) lengkap dengan langkah perbaikannya.

#### Langkah 3 — Atur printer & timbangan

Dashboard sudah terbuka di `http://127.0.0.1:18212`. Atur printer default, alias
pool, dan port COM timbangan lewat antarmuka web — tidak perlu menyunting JSON
secara manual.

#### Isi paket portable

| Berkas | Fungsi |
|---|---|
| **`INSTALL.bat`** | **Pasang sekali klik**: auto-start + jalankan + verifikasi |
| `UNINSTALL.bat` | Copot auto-start, hentikan service, hapus aturan firewall |
| `Jalankan.bat` | Jalankan sekali saja tanpa memasang auto-start |
| `Cek_Status.bat` | Cek hidup/tidak, port aktif, ringkasan `/api/status`, 20 baris log terakhir |
| `Jalankan_Konsol.bat` | Mode diagnosa: restart bridge lalu tampilkan log real-time |
| `Izinkan_Akses_LAN.bat` | **Opsional**, buka Windows Firewall agar bisa diakses PC lain |
| `Jalankan_Diam.vbs` | Penolong runner senyap (dipakai otomatis) |
| `bridge_config.json` | Setelan printer, timbangan, port |
| `BACA_SAYA.txt` | Panduan singkat di dalam paket |
| `HardwareBridge.exe` + `_internal\` | Aplikasi & pustakanya — jangan dipisahkan |
| `docs\`, `sdk\` | Dokumentasi lengkap & SDK JavaScript, tersedia offline |

#### Pengelolaan sehari-hari (padanan systemd)

| Linux | Windows (paket portable) |
|---|---|
| `sudo bash linux/install.sh` | klik ganda `INSTALL.bat` |
| `sudo bash linux/uninstall.sh` | klik ganda `UNINSTALL.bat` |
| `sudo systemctl status hardware-bridge` | klik ganda `Cek_Status.bat` |
| `sudo systemctl restart hardware-bridge` | klik kanan ikon tray → **Restart Service** |
| `sudo systemctl stop hardware-bridge` | klik kanan ikon tray → **Hentikan Service** |
| `journalctl -u hardware-bridge -f` | klik ganda `Jalankan_Konsol.bat` |
| `bash linux/run.sh` | klik ganda `Jalankan.bat` |

#### Akses dari komputer lain (opsional)

Bila aplikasi web dibuka dari PC lain dalam satu jaringan, jalankan
`Izinkan_Akses_LAN.bat`. Skrip meminta hak Administrator lewat UAC, membuka port
di Windows Firewall **hanya untuk profil Private dan Domain** (profil Public
sengaja tidak dibuka), lalu menampilkan alamat IP komputer tersebut.

Pastikan juga `"host"` pada `bridge_config.json` bernilai `"0.0.0.0"`.

---

### Cara B — Jalankan dari Kode Sumber

Untuk pengembangan, atau bila Anda ingin mengubah kode Python.

| Berkas di `windows/` | Fungsi |
|---|---|
| `run.bat` | Pasang dependensi lalu jalankan di jendela CMD (log terlihat langsung) |
| `run_background.vbs` | Jalankan di latar belakang dengan ikon tray, tanpa jendela CMD |
| `install_autostart.bat` | Pasang auto-start yang menunjuk ke `run_background.vbs` |
| `uninstall_autostart.bat` | Copot auto-start tersebut |
| `build_portable.bat` | Bangun `.exe` + rakit ZIP portable siap bagi |

```cmd
windows\run.bat
```

Skrip memeriksa Python, memasang `requirements.txt`, lalu menjalankan bridge di
port `18212`. Tekan `Ctrl + C` untuk berhenti.

---

### Membangun Paket Portable Sendiri (`build_portable.bat`)

Untuk mendistribusikan ke PC kasir lain tanpa menginstal Python di sana:

```cmd
windows\build_portable.bat
```

Skrip ini mengerjakan empat tahap:

1. Mengompilasi `HardwareBridge.exe` dengan PyInstaller (memasang PyInstaller
   otomatis bila belum ada).
2. Merakit isi paket: binary + seluruh isi `windows\portable\` + `docs\` + SDK.
3. Memampatkan menjadi `HardwareBridge_Windows_x64_Portable.zip` di root proyek.
4. Menampilkan ringkasan ukuran dan isi paket.

> **Ingin mengubah isi paket portable?** Sunting berkas di `windows\portable\`
> (teks installer, konfigurasi bawaan, `BACA_SAYA.txt`), lalu jalankan ulang
> `build_portable.bat`. Folder itu satu-satunya sumber kebenaran isi paket —
> tidak ada salinan lain yang perlu disamakan manual.

---

### Mencopot Hardware Bridge di Windows

**Paket portable:** klik ganda `UNINSTALL.bat`. Skrip menghentikan service,
menghapus shortcut auto-start dan shortcut Desktop, serta menghapus aturan
firewall bila pernah dipasang.

`bridge_config.json` dan folder `logs\` **sengaja tidak dihapus** agar setelan
printer dan timbangan Anda tidak hilang. Ingin membuang total? Hapus saja
foldernya.

**Mode kode sumber:** klik ganda `windows\uninstall_autostart.bat`.

---

### Troubleshooting & Solusi Masalah Windows

#### 1. `[ERROR] HardwareBridge.exe TIDAK DITEMUKAN` saat menjalankan `INSTALL.bat`:
* **Penyebab:** `INSTALL.bat` diklik langsung dari dalam berkas ZIP.
* **Solusi:** Klik kanan ZIP → **Extract All…**, buka folder hasil ekstrak, baru
  jalankan `INSTALL.bat` dari sana.

#### 2. Ikon System Tray tidak muncul / bridge tidak mau hidup:
* Klik ganda **`Jalankan_Konsol.bat`** untuk melihat log real-time.
* Penyebab tersering adalah Windows Defender memblokir `HardwareBridge.exe`.
  Buka **Windows Security → Virus & threat protection → Manage settings →
  Exclusions → Add folder**, lalu pilih folder Hardware Bridge.

#### 3. Dashboard tidak bisa dibuka di port `18212`:
* Bridge otomatis pindah ke port cadangan `12212` bila `18212` sedang dipakai
  aplikasi lain (misal service Java bridge lawas). Lihat baris `[Port]` di log.
* `Cek_Status.bat` memeriksa kedua port sekaligus dan menyebutkan mana yang aktif.

#### 4. Port Serial Timbangan `Access is denied` (Error 13):
* **Penyebab:** Port COM sedang dibuka secara eksklusif oleh aplikasi lain (misal
  program kasir Delphi lawas, HyperTerminal, atau tab browser lain).
* **Solusi:**
  - Tekan tombol **`⏸️ Lepas Port (Delphi)`** di dashboard bridge.
  - Atau ubah `"sharing_mode"` di `bridge_config.json` menjadi `"on_demand"`.
    Pada mode ini port COM otomatis dilepas bila tidak ada transaksi timbangan
    selama `idle_release_seconds` (bawaan 4 detik).

#### 5. Kabel USB timbangan dicabut & dicolokkan ke lubang USB lain:
* **Fitur Auto-Resolve:** isi `"usb_serial"` pada `bridge_config.json` dengan
  serial number adapter USB Anda (misal `BMCBE14A312`). Bila port berpindah dari
  `COM5` ke `COM1`, bridge otomatis mendeteksi dan mengikuti tanpa ubah konfigurasi.
* Bila timbangan tidak bergerak, klik **`▶️ Sambungkan`** atau **`0️⃣ ZERO`** di dashboard.

#### 6. Driver Prolific PL2303 menampilkan tanda seru kuning (Code 10):
* **Penyebab:** Chip PL2303 clone/lawas tidak didukung driver Windows 11 terbaru.
* **Solusi:** Pasang driver Prolific versi 3.3.2 (2008), atau ganti ke kabel USB
  Serial chipset FTDI / CH340.

#### 7. Aplikasi web di komputer lain tidak bisa memanggil bridge:
* Jalankan **`Izinkan_Akses_LAN.bat`** (klik "Yes" pada dialog UAC).
* Pastikan `"host"` pada `bridge_config.json` bernilai `"0.0.0.0"`, bukan `"127.0.0.1"`.

---

## 🐧 Panduan Instalasi Linux Mint 22 / Ubuntu 22

Seluruh script automasi untuk Linux terletak di folder [`linux/`](../linux/).

```
webappdirectprint/
└── linux/
    ├── install.sh                  <-- Installer otomatis systemd + udev
    ├── run.sh                      <-- Runner sementara di terminal konsol
    ├── uninstall.sh                <-- Pencopot service systemd & udev
    ├── build_linux.sh              <-- Kompilasi binary mandiri Linux ELF
    ├── hardware-bridge.service     <-- Template unit file systemd
    └── 99-hardware-bridge.rules    <-- Aturan Udev port serial & printer USB
```

### Metode 1: Pemasangan Otomatis Systemd Service (`install.sh`)
Metode standar untuk mesin produksi (Linux Mint / Ubuntu). Service akan otomatis berjalan di latar belakang sebagai daemon systemd dan selalu aktif saat booting (*auto-restart on failure*).

1. Buka Terminal di direktori proyek `webappdirectprint`:
   ```bash
   cd /path/to/webappdirectprint
   ```
2. Berikan izin eksekusi pada seluruh script:
   ```bash
   chmod +x linux/*.sh
   ```
3. Jalankan installer dengan hak akses `sudo`:
   ```bash
   sudo bash linux/install.sh
   ```
4. **Apa yang dilakukan installer ini secara otomatis?**
   - Menginstal paket sistem: `python3`, `python3-venv`, `cups`, `cups-client`, `libcups2-dev`, `build-essential`.
   - Mengaktifkan service percetakan CUPS (`systemctl enable --now cups`).
   - Membuat Virtual Environment Python di `venv/` dan menginstal seluruh pustaka `requirements.txt`.
   - Memasang aturan Udev `/etc/udev/rules.d/99-hardware-bridge.rules` agar port serial (`/dev/ttyUSB*`, `/dev/ttyACM*`) dan printer USB memiliki hak akses `0666` tanpa memerlukan `sudo`.
   - Mendaftarkan user kasir Anda ke dalam grup `dialout` dan `lp`.
   - Mendaftarkan dan mengaktifkan service systemd `/etc/systemd/system/hardware-bridge.service`.
   - Memulai service secara instan.
5. Verifikasi di browser:
   Akses **`http://127.0.0.1:18212`** (atau `http://127.0.0.1:12212`).

---

### Metode 2: Menjalankan Sementara di Konsol (`run.sh`)
Jika Anda hanya ingin mencoba atau melakukan debugging di terminal Linux:

```bash
chmod +x linux/run.sh
bash linux/run.sh
```

---

### Metode 3: Membangun Binary Executable Linux ELF (`build_linux.sh`)
Jika Anda ingin menghasilkan file binary mandiri yang dapat didistribusikan tanpa instalasi Python:

```bash
chmod +x linux/build_linux.sh
bash linux/build_linux.sh
```
Binary hasil kompilasi akan berada di: `dist/hardware-bridge/hardware-bridge`.

---

### Pengelolaan Service Systemd (Status, Restart, Logs)

Gunakan perintah-perintah Linux standar berikut:

* **Melihat status service:**
  ```bash
  sudo systemctl status hardware-bridge
  ```
* **Memulai ulang (*Restart*) service:**
  ```bash
  sudo systemctl restart hardware-bridge
  ```
* **Menghentikan (*Stop*) service:**
  ```bash
  sudo systemctl stop hardware-bridge
  ```
* **Melihat log real-time (*Live Monitoring*):**
  ```bash
  journalctl -u hardware-bridge -f
  ```

---

### Mencopot Service Linux (`uninstall.sh`)
Jika Anda ingin menghapus service dan aturan udev dari sistem Linux:

```bash
sudo bash linux/uninstall.sh
```

---

### Troubleshooting & Solusi Masalah Linux

#### 1. Port Serial Timbangan Tidak Muncul di `/dev/ttyUSB0` (Konflik `brltty`):
* **Penyebab:** Pada Ubuntu 22 / Linux Mint 22, paket braille display `brltty` sering kali otomatis mencaplok adapter serial CH340 / Prolific begitu dicolokkan ke USB.
* **Solusi:** Hapus atau matikan paket `brltty`:
  ```bash
  sudo apt remove --purge brltty
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```

#### 2. Permission Denied saat Membaca Port Serial:
* **Solusi:** Pastikan user Anda telah dimasukkan ke grup `dialout`:
  ```bash
  sudo usermod -aG dialout $USER
  ```
  *Catatan: Setelah menjalankan perintah ini, Anda harus Log Out lalu Log In kembali agar izin grup aktif.*

#### 3. Printer USB Tidak Terdeteksi di Dashboard:
* Pastikan printer terdaftar di CUPS:
  ```bash
  lpstat -p -d
  ```
* Jika belum terdaftar, tambahkan printer lewat antarmuka web CUPS di `http://localhost:631` atau menu *Printers* di Linux Mint.

---

## ⚙️ Konfigurasi Port & Hardware (`bridge_config.json`)

Lokasi berkas:

| Cara pakai | Lokasi `bridge_config.json` |
|---|---|
| Paket portable Windows | di samping `HardwareBridge.exe`, folder hasil ekstrak |
| Kode sumber (Windows/Linux) | root proyek: [`bridge_config.json`](../bridge_config.json) |

> Sebagian besar parameter bisa diubah lewat **Dashboard → Pengaturan** tanpa
> menyunting JSON. Sunting manual hanya bila Anda butuh opsi lanjutan.

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 18212,
    "scale_port": null,
    "cors_origins": ["*"],
    "enable_tray": true,
    "sharing_mode": "continuous",
    "idle_release_seconds": 4.0,
    "pause_auto_resume_seconds": 600,
    "enable_scale_at_startup": false
  },
  "printers": {
    "default_raw_printer": "EPSON TM-T82",
    "default_doc_printer": "Microsoft Print to PDF",
    "default_encoding": "cp437",
    "pools": {
      "receipt": "EPSON TM-T82",
      "label": "Godex G500 GZPL",
      "asset_label": "Godex G500 GZPL",
      "invoice": "Microsoft Print to PDF"
    },
    "network_printers": [
      { "name": "Printer Dapur", "ip": "192.168.1.200", "port": 9100, "type": "escpos" }
    ]
  },
  "scales": [
    {
      "name": "Mettler JE5002GE / Shinko",
      "usb_serial": "BMCBE14A312",
      "port": "COM1",
      "protocol": "auto",
      "baud": 9600,
      "databits": 8,
      "parity": "N",
      "stopbits": 1,
      "autoconnect": true
    },
    {
      "name": "Simulator Timbangan",
      "port": "SIM",
      "protocol": "mettler",
      "autoconnect": false
    }
  ]
}
```

### Penjelasan Parameter Kunci:
1. **`server.host`:**
   * `"0.0.0.0"` (bawaan): bridge bisa dipanggil dari PC lain di jaringan — di
     Windows tetap perlu menjalankan `Izinkan_Akses_LAN.bat` agar firewall membuka portnya.
   * `"127.0.0.1"`: bridge hanya bisa dipanggil dari PC itu sendiri (paling aman).
2. **`server.port`:**
   * Default: `18212`, dengan fallback otomatis ke `12212` bila port itu sedang dipakai.
   * Menghindari tabrakan port dengan service imTigger Java bridge lawas.
3. **`server.sharing_mode`:**
   * `"continuous"`: Timbangan di-stream secara cepat dan terus menerus. Terdapat tombol *Pause* dan *Resume* di dashboard.
   * `"on_demand"`: Port serial hanya dibuka saat ada panggilan API membaca timbangan, lalu otomatis dilepas setelah `idle_release_seconds` (misal 4 detik) agar software Delphi kasir bisa mengakses port COM tanpa bentrok.
4. **`server.enable_scale_at_startup`:**
   * `true` (Default): Port timbangan otomatis dibuka dan disambungkan saat service bridge dinyalakan.
   * `false`: Bridge **tidak membuka atau mengunci port COM** saat startup. Sangat berguna untuk komputer atau aplikasi yang masih menghubungkan timbangan langsung via JavaScript peramban (**Web Serial API di Chrome / Edge**), sehingga port serial tetap bebas dan tidak bentrok (*Access is denied*). Pengaturan ini juga dapat diaktifkan/dinonaktifkan langsung lewat 1 klik di Dashboard Timbangan / Pengaturan.
5. **`scales[].usb_serial`:**
   * Masukkan Serial Number adapter USB Anda (misal `BMCBE14A312`). Sistem akan **otomatis melacak colokan USB mana pun yang digunakan**, sehingga meskipun kabel dicolokkan ke port USB lain, bridge tetap otomatis terhubung!
6. **`scales[].protocol`:**
   * Pilihan: `"auto"`, `"shinko"`, `"mettler"`, `"and"`. Disarankan `"auto"` untuk auto-detect format stream data.
7. **`printers.pools`:**
   * Alias printer, misal `receipt`, `label`, `asset_label`, `invoice`.
   * Aplikasi web cukup menyebut aliasnya; tiap PC memetakan alias itu ke nama
     printer fisiknya sendiri. Kode aplikasi jadi tidak terikat nama printer per PC.
8. **`printers.network_printers`:**
   * Printer LAN/Wi-Fi yang dipanggil langsung lewat TCP port `9100`, tanpa driver Windows/CUPS.

---

## ✅ Verifikasi Setelah Instalasi

Setelah instalasi selesai (baik di Windows maupun Linux):

1. **Buka Dashboard Browser:**
   Akses: 👉 **`http://127.0.0.1:18212`** (atau port konfigurasi Anda).
2. **Verifikasi Timbangan Digital:**
   * Amati panel **LCD Digital** di tab *Timbangan Digital*.
   * Berat harus menampilkan angka secara dinamis (misal `0.00 g`).
   * Badge status harus bertuliskan **🟢 ONLINE** dan **STABIL (STABLE)**.
   * Letakkan beban di timbangan atau tekan tombol **`0️⃣ ZERO`** / **`⚖️ TARE`** untuk memverifikasi responsifitasnya.
3. **Verifikasi Printer Thermal:**
   * Buka tab *Pengujian Printer*.
   * Pilih nama printer kasir Anda dari dropdown.
   * Klik tombol **`🧾 Uji Cetak Struk (ESC/POS)`**.
   * Printer kasir akan langsung mencetak struk kasir pengujian tanpa memunculkan kotak dialog browser.
4. **Integrasi ERPNext & Web App:**
   * Unduh SDK JS langsung dari dashboard di tab *Dokumentasi & SDK* atau lewat URL:
     `http://127.0.0.1:18212/api/download/hardware-bridge.js`
   * Pasang script client di ERPNext sesuai petunjuk di [`docs/integrasi/erpnext.md`](integrasi/erpnext.md).
