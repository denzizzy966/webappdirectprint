# ==============================================================================
# WebApp Hardware Bridge Universal — Portable Offline Edition (Windows 10 / 11)
# ==============================================================================

Paket ini adalah versi PORTABLE OFFLINE mandiri (Standalone).
- 100% OFFLINE: Tidak membutuhkan koneksi internet sama sekali.
- BEBAS DEPENDENSI: Tidak perlu menginstal Python di komputer klien.
- SILENT TRAY: Otomatis berjalan di latar belakang (System Tray pojok kanan bawah dekat jam) tanpa jendela hitam CMD.

--------------------------------------------------------------------------------
CARA PENGGUNAAN CEPAT:
--------------------------------------------------------------------------------

1. CARA MENJALANKAN LANGSUNG:
   Klik 2x pada "HardwareBridge.exe".
   Ikon Hardware Bridge akan langsung muncul di System Tray (dekat jam Windows).
   Akses dashboard di browser: http://127.0.0.1:18212

2. CARA AGAR OTOMATIS BERJALAN SAAT KOMPUTER MENYALA (AUTO-START):
   Klik 2x pada "Install_AutoStart.bat".
   Shortcut akan otomatis dipasang di folder Startup Windows.
   Setiap kali kasir menyalakan PC/login, Hardware Bridge otomatis aktif di System Tray.

3. CARA MEMATIKAN ATAU KELUAR:
   Klik kanan pada ikon Hardware Bridge di System Tray -> pilih "Exit Bridge".

4. CARA MENGHAPUS AUTO-START:
   Klik 2x pada "Uninstall_AutoStart.bat".

--------------------------------------------------------------------------------
KONFIGURASI PERANGKAT (PRINTER & TIMBANGAN):
--------------------------------------------------------------------------------
Seluruh pengaturan tersimpan di file "bridge_config.json":
- Port server default: 18212
- Opsi enable_scale_at_startup: false (Port COM tidak terkunci saat startup)
- Daftar printer (ESC/POS, ZPL, PDF, cash drawer)
- Daftar timbangan digital (Mettler, Shinko, A&D, simulator)

Panduan integrasi Laravel / ERPNext dan dual-timbangan:
Buka folder "laravel" atau lihat "DOKUMENTASI_PENGGUNAAN.md".
Demo interaktif: http://127.0.0.1:18212/static/cara-pakai.html
