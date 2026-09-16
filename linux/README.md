# 🐧 Panduan Instalasi & Penggunaan Linux Mint 22 / Ubuntu 22
### WebApp Hardware Bridge Universal

Direktori ini berisi seluruh skrip automasi instalasi dan service systemd untuk **Linux Mint 22** dan **Ubuntu 22 LTS**.

---

## 📁 Berkas di Folder Ini:

| Berkas | Fungsi / Deskripsi |
|---|---|
| **`install.sh`** | Installer otomatis 1-klik: pasang paket CUPS, dependensi python di venv, udev rules, dan daftarkan service systemd. |
| **`run.sh`** | Menjalankan server bridge secara manual di terminal Linux. |
| **`uninstall.sh`** | Menghentikan dan mencopot service systemd serta aturan udev secara bersih. |
| **`build_linux.sh`** | Mengompilasi aplikasi menjadi binary mandiri Linux ELF menggunakan PyInstaller. |
| **`hardware-bridge.service`** | Berkas unit service systemd untuk manajemen daemon background. |
| **`99-hardware-bridge.rules`** | Aturan udev untuk memberikan hak akses non-root ke port serial (`/dev/ttyUSB*`) dan printer USB. |

---

## 🚀 Cara Pemasangan Standar (Systemd Service):

1. **Jalankan installer dengan `sudo`:**
   ```bash
   chmod +x *.sh
   sudo bash install.sh
   ```
2. **Apa yang dilakukan installer?**
   - Menginstal paket sistem: `cups`, `libcups2-dev`, `python3-venv`, `build-essential`.
   - Mengaktifkan CUPS printing daemon.
   - Membuat Virtual Environment di `../venv` dan menginstal `requirements.txt`.
   - Mendaftarkan aturan udev `/etc/udev/rules.d/99-hardware-bridge.rules`.
   - Menambahkan user Anda ke grup `dialout` dan `lp`.
   - Mengaktifkan dan menyalakan service systemd `hardware-bridge.service`.
3. **Buka Dashboard:**
   Akses `http://127.0.0.1:18212` (atau `http://127.0.0.1:12212`).

---

## ⚙️ Perintah Pengelolaan Systemd:

- **Cek Status Service:**
  ```bash
  sudo systemctl status hardware-bridge
  ```
- **Restart Service:**
  ```bash
  sudo systemctl restart hardware-bridge
  ```
- **Hentikan Service:**
  ```bash
  sudo systemctl stop hardware-bridge
  ```
- **Pantau Log Real-time:**
  ```bash
  journalctl -u hardware-bridge -f
  ```

---

## 🗑️ Mencopot Service:
```bash
sudo bash uninstall.sh
```

---

## 🛠️ Catatan Khusus Linux:
- **Konflik Paket `brltty`:** Jika adapter USB serial (CH340 / PL2303) tidak muncul di `/dev/ttyUSB0`, hapus paket braille display bawaan:
  ```bash
  sudo apt remove --purge brltty
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```
- **Izin Grup Dialout:** Jika port serial tidak bisa diakses, pastikan user telah masuk grup dialout:
  ```bash
  sudo usermod -aG dialout $USER
  ```
  *(Perlu Log Out lalu Log In kembali).*

*Untuk panduan lengkap, lihat: [../INSTALLER_README.md](../INSTALLER_README.md)*
