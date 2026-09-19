# 🪟 Panduan Instalasi & Penggunaan Windows 10 / 11
### WebApp Hardware Bridge Universal

Direktori ini berisi seluruh perkakas eksekusi dan automasi untuk sistem operasi **Windows 10 & 11**.

---

## 📁 Berkas di Folder Ini:

| Berkas | Fungsi / Deskripsi |
|---|---|
| **`run.bat`** | Menjalankan server bridge langsung di jendela konsol CMD (cocok untuk pengujian/debug). |
| **`run_background.vbs`** | Menjalankan server bridge di latar belakang (*background*) dengan ikon System Tray (tanpa jendela hitam CMD). |
| **`install_autostart.bat`** | Memasang shortcut auto-start di folder Startup Windows agar otomatis aktif saat komputer dinyalakan. |
| **`uninstall_autostart.bat`** | Mencopot shortcut auto-start dari folder Startup Windows. |
| **`build_exe.bat`** | Mengompilasi source code menjadi berkas binary mandiri (`dist\HardwareBridge\HardwareBridge.exe`). |

---

## 🚀 Cara Penggunaan Singkat:

### 1. Pengujian Pertama Kali (Konsol)
Klik ganda **`run.bat`**.  
Jendela CMD akan terbuka dan otomatis mengunduh dependensi Python. Buka browser di `http://127.0.0.1:18212`.

### 2. Penggunaan Sehari-Hari untuk Kasir (Background + System Tray)
Klik ganda **`run_background.vbs`**.  
Tidak akan ada jendela hitam CMD yang mengganggu kasir. Ikon aplikasi akan muncul di pojok kanan bawah dekat jam (System Tray).

### 3. Pemasangan Otomatis saat Komputer Dinyalakan (Auto-Start)
Klik kanan **`install_autostart.bat`** -> Pilih **"Run as administrator"** (atau klik ganda).  
Aplikasi otomatis dibuatkan shortcut di folder Startup Windows.

### 4. Membuat Executable `.exe` Mandiri
Klik ganda **`build_exe.bat`**.  
Hasil build binary mandiri berada di `..\dist\HardwareBridge\HardwareBridge.exe`.

---

## 🛠️ Catatan Port & Timbangan:
- **Port Default:** `18212` (atau fallback ke `12212`).
- **Pindah Port COM USB:** Hardware Bridge memiliki fitur *Auto-Resolve* berdasarkan serial number chip adapter USB (e.g. `BMCBE14A312`). Jika Anda memindahkan colokan USB dari `COM5` ke `COM1`, bridge akan otomatis mendeteksinya tanpa perlu setelan manual.
- **Port Terkunci oleh Delphi (*Access is denied*):** Tekan tombol **`⏸️ Lepas Port (Delphi)`** di dashboard, atau aktifkan mode `"sharing_mode": "on_demand"` di `bridge_config.json`.

*Untuk panduan lengkap, lihat: [../03-instalasi.md](../03-instalasi.md)*
