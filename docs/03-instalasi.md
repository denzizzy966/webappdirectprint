# 📖 Buku Panduan Instalasi & Deployment (Installer Guide)
### WebApp Hardware Bridge Universal — Windows 10/11 & Linux Mint 22 / Ubuntu 22

Dokumen ini berisi panduan langkah demi langkah cara memasang (*install*), mengonfigurasi, menjalankan otomatis (*auto-start / systemd service*), dan mengelola **WebApp Hardware Bridge Universal** pada sistem operasi **Windows** dan **Linux**.

---

## 📑 Daftar Isi
1. [Arsitektur & Mengapa Harus di Client PC](#-arsitektur--mengapa-harus-di-client-pc)
2. [Persyaratan Sistem (Prerequisites)](#-persyaratan-sistem-prerequisites)
3. [Panduan Instalasi Windows 10 / 11](#-panduan-instalasi-windows-10--11)
   - [Metode 1: Menjalankan Langsung di Konsol (`run.bat`)](#metode-1-menjalankan-langsung-di-konsol-runbat)
   - [Metode 2: Menjalankan Latar Belakang / Silent Tray (`run_background.vbs`)](#metode-2-menjalankan-latar-belakang--silent-tray-run_backgroundvbs)
   - [Metode 3: Memasang Auto-Start Windows Booting (`install_autostart.bat`)](#metode-3-memasang-auto-start-windows-booting-install_autostartbat)
   - [Metode 4: Membangun Binary Standalone `.exe` (`build_exe.bat`)](#metode-4-membangun-binary-standalone-exe-build_exebat)
   - [Mencopot Auto-Start Windows (`uninstall_autostart.bat`)](#mencopot-auto-start-windows-uninstall_autostartbat)
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
1. **Python 3.10 atau lebih baru** (disarankan 3.10 / 3.11 / 3.12).
   * Pastikan saat instalasi Python mencentang opsi: **"Add Python to PATH"**.
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

Seluruh script automasi untuk Windows terletak di folder [`windows/`](file:///D:/Workspaces-gemini/webappdirectprint/windows).

```
webappdirectprint/
└── windows/
    ├── run.bat                 <-- Menjalankan langsung di jendela CMD
    ├── run_background.vbs      <-- Menjalankan di background (tanpa jendela CMD)
    ├── install_autostart.bat   <-- Memasang auto-start saat Windows booting/login
    ├── uninstall_autostart.bat <-- Mencopot shortcut auto-start
    └── build_exe.bat           <-- Mengompilasi menjadi berkas .exe mandiri
```

### Metode 1: Menjalankan Langsung di Konsol (`run.bat`)
Sangat cocok untuk pengujian awal atau *debugging* karena log aktivitas langsung terlihat di layar.

1. Buka folder `windows/`.
2. Klik ganda berkas **`run.bat`**.
3. Script akan otomatis:
   * Memeriksa apakah Python terpasang di sistem.
   * Mengunduh dependensi (`pip install -r requirements.txt`).
   * Menjalankan server bridge di port `18212` (atau fallback ke `12212`).
4. Buka peramban (*browser*) Anda dan akses:
   👉 **`http://127.0.0.1:18212`**
5. Tekan `Ctrl + C` di jendela konsol jika ingin menghentikan service.

---

### Metode 2: Menjalankan Latar Belakang / Silent Tray (`run_background.vbs`)
Sangat cocok untuk kasir sehari-hari agar tidak ada jendela hitam CMD yang mengganggu atau tidak sengaja tertutup oleh kasir.

1. Buka folder `windows/`.
2. Klik ganda berkas **`run_background.vbs`**.
3. Aplikasi akan berjalan di latar belakang (*background process*). Ikon Hardware Bridge akan muncul di **System Tray** pojok kanan bawah Windows (dekat jam).
4. Klik kanan pada ikon system tray untuk:
   * **Open Dashboard:** Membuka dashboard web di browser.
   * **Exit Bridge:** Menutup service bridge secara aman.

---

### Metode 3: Memasang Auto-Start Windows Booting (`install_autostart.bat`)
Gunakan metode ini agar setiap kali komputer kasir dinyalakan / login ke Windows, Hardware Bridge otomatis aktif di latar belakang.

1. Buka folder `windows/`.
2. Klik kanan pada berkas **`install_autostart.bat`** -> Pilih **"Run as administrator"** (atau cukup klik ganda).
3. Script akan membuat shortcut resmi di folder Startup Windows:
   `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\HardwareBridge.lnk`
4. Akan muncul pesan sukses:
   ```
   ===================================================
    Memasang Auto-Start Hardware Bridge saat Login
   ===================================================
   [SUKSES] Auto-Start berhasil dipasang!
   Hardware Bridge akan otomatis aktif setiap kali Anda menyalakan komputer.
   ```
5. Selesai! Mulai sekarang, kasir tidak perlu menjalankan script manual apa pun saat komputer dinyalakan.

---

### Metode 4: Membangun Binary Standalone `.exe` (`build_exe.bat`)
Jika Anda ingin mendistribusikan aplikasi ini ke PC kasir lain tanpa harus menginstal Python di komputer target:

1. Pastikan koneksi internet aktif.
2. Buka folder `windows/` dan klik ganda **`build_exe.bat`**.
3. Script akan otomatis menginstal `PyInstaller` dan memaketkan seluruh aplikasi, template web, aset static, dan dependensi menjadi folder binary mandiri.
4. Hasil kompilasi akan berada di:
   📂 **`dist\HardwareBridge\HardwareBridge.exe`**
5. Anda cukup menyalin (*copy*) seluruh folder `dist\HardwareBridge` ke komputer kasir mana pun dan membuat shortcut ke `HardwareBridge.exe`.

---

### Mencopot Auto-Start Windows (`uninstall_autostart.bat`)
Jika ingin menonaktifkan auto-start:
1. Buka folder `windows/`.
2. Klik ganda **`uninstall_autostart.bat`**.
3. Shortcut di folder Startup Windows akan dihapus secara bersih.

---

### Troubleshooting & Solusi Masalah Windows

#### 1. Port Serial Timbangan `Access is denied` (Error 13):
* **Penyebab:** Port COM sedang dibuka secara eksklusif oleh aplikasi lain (misal program kasir Delphi lawas, HyperTerminal, atau tab browser lain).
* **Solusi:**
  - Tekan tombol **`⏸️ Lepas Port (Delphi)`** di dashboard bridge.
  - Atau ubah mode port di `bridge_config.json` menjadi `"sharing_mode": "on_demand"`. Pada mode ini, port COM akan otomatis dilepas jika tidak ada transaksi timbangan dalam 4 detik.

#### 2. Kabel USB Timbangan Dicabut & Dicolokkan ke Lubang USB Lain:
* **Fitur Auto-Resolve:** Hardware Bridge sudah dilengkapi pelacak otomatis USB Serial Number (`BMCBE14A312`). Jika port berpindah dari `COM5` ke `COM1`, bridge akan otomatis mendeteksi dan berpindah port tanpa perlu ubah konfigurasi manual.
* Jika timbangan tidak bergerak, klik tombol **`▶️ Sambungkan`** atau **`0️⃣ ZERO`** pada dashboard.

#### 3. Driver Prolific PL2303 Menampilkan Tanda Seru Kuning (Code 10) di Device Manager:
* **Penyebab:** Versi chip PL2303 clone/lawas tidak didukung driver Windows 11 terbaru.
* **Solusi:** Pasang driver Prolific versi 3.3.2 (2008) atau gunakan kabel USB Serial chipset FTDI / CH340.

#### 4. Notifikasi Windows Defender / Antivirus:
* Tambahkan folder `webappdirectprint` ke dalam daftar pengecualian (*Exclusions*) di Windows Security.

---

## 🐧 Panduan Instalasi Linux Mint 22 / Ubuntu 22

Seluruh script automasi untuk Linux terletak di folder [`linux/`](file:///D:/Workspaces-gemini/webappdirectprint/linux).

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

File konfigurasi berada di root proyek: [`bridge_config.json`](file:///D:/Workspaces-gemini/webappdirectprint/bridge_config.json).

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 18212,
    "sharing_mode": "continuous",
    "idle_release_seconds": 4.0,
    "enable_scale_at_startup": true,
    "cors_origins": ["*"]
  },
  "printers": {
    "default_printer": "",
    "auto_cut": true,
    "open_cashdrawer": false
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
1. **`server.port`:**
   * Default: `18212` (atau fallback otomatis ke `12212` jika kosong).
   * Menghindari tabrakan port dengan service imTigger Java bridge lawas.
2. **`server.sharing_mode`:**
   * `"continuous"`: Timbangan di-stream secara cepat dan terus menerus. Terdapat tombol *Pause* dan *Resume* di dashboard.
   * `"on_demand"`: Port serial hanya dibuka saat ada panggilan API membaca timbangan, lalu otomatis dilepas setelah `idle_release_seconds` (misal 4 detik) agar software Delphi kasir bisa mengakses port COM tanpa bentrok.
3. **`server.enable_scale_at_startup`:**
   * `true` (Default): Port timbangan otomatis dibuka dan disambungkan saat service bridge dinyalakan.
   * `false`: Bridge **tidak membuka atau mengunci port COM** saat startup. Sangat berguna untuk komputer atau aplikasi yang masih menghubungkan timbangan langsung via JavaScript peramban (**Web Serial API di Chrome / Edge**), sehingga port serial tetap bebas dan tidak bentrok (*Access is denied*). Pengaturan ini juga dapat diaktifkan/dinonaktifkan langsung lewat 1 klik di Dashboard Timbangan / Pengaturan.
4. **`scales[].usb_serial`:**
   * Masukkan Serial Number adapter USB Anda (misal `BMCBE14A312`). Sistem akan **otomatis melacak colokan USB mana pun yang digunakan**, sehingga meskipun kabel dicolokkan ke port USB lain, bridge tetap otomatis terhubung!
5. **`scales[].protocol`:**
   * Pilihan: `"auto"`, `"shinko"`, `"mettler"`, `"and"`. Disarankan `"auto"` untuk auto-detect format stream data.

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
