@echo off
setlocal EnableDelayedExpansion
title Installer WebApp Hardware Bridge Universal (Windows 10 / 11)
cd /d "%~dp0"

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
set "EXE=%BASE_DIR%\HardwareBridge.exe"
set "CFG=%BASE_DIR%\bridge_config.json"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_DIR%\HardwareBridge.lnk"
set "DESKTOP_LNK=%USERPROFILE%\Desktop\Hardware Bridge Dashboard.url"

echo ==========================================================
echo   Pemasangan WebApp Hardware Bridge Universal
echo   Windows 10 / 11 - Portable Offline Edition
echo ==========================================================
echo   Folder   : %BASE_DIR%
echo   Pengguna : %USERNAME%
echo ==========================================================
echo.

REM ----------------------------------------------------------
REM [1/6] Memeriksa berkas aplikasi
REM ----------------------------------------------------------
echo [1/6] Memeriksa berkas aplikasi...
set "RUN_MODE=EXE"
if not exist "%EXE%" (
    where python >nul 2>nul
    if errorlevel 1 (
        echo.
        echo   [ERROR] HardwareBridge.exe TIDAK DITEMUKAN di folder ini!
        echo.
        echo   Penyebab paling umum:
        echo     Anda menjalankan INSTALL.bat langsung dari DALAM berkas ZIP.
        echo     Windows hanya mengintip isi ZIP, berkas lain belum benar-benar ada.
        echo.
        echo   Solusi:
        echo     1. Klik kanan HardwareBridge_Windows_x64_Portable.zip
        echo     2. Pilih "Extract All..." / "Ekstrak Semua"
        echo     3. Buka folder hasil ekstrak, lalu klik 2x INSTALL.bat lagi
        echo.
        pause
        exit /b 1
    )
    set "RUN_MODE=PYTHON"
    echo   [i] Mode sumber kode ^(Python^) terdeteksi.
) else (
    echo   [OK] HardwareBridge.exe ditemukan.
)

REM ----------------------------------------------------------
REM [2/6] Menyiapkan konfigurasi dan folder log
REM ----------------------------------------------------------
echo [2/6] Menyiapkan konfigurasi dan folder log...
if not exist "%BASE_DIR%\logs" mkdir "%BASE_DIR%\logs" >nul 2>nul

if not exist "%CFG%" (
    echo   [i] bridge_config.json belum ada, membuat setelan bawaan Windows...
    call :BuatConfigBawaan
    echo   [OK] bridge_config.json dibuat.
) else (
    echo   [OK] bridge_config.json sudah ada, setelan lama dipertahankan.
)

REM Membaca nomor port dari bridge_config.json
set "PORT=18212"
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $raw = Get-Content -Raw -LiteralPath '%CFG%'; $cfg = ConvertFrom-Json $raw; $cfg.server.port } catch { 18212 }"`) do set "PORT=%%P"
if "%PORT%"=="" set "PORT=18212"
echo   [OK] Port dashboard: %PORT%

REM ----------------------------------------------------------
REM [3/6] Menghentikan instance lama
REM ----------------------------------------------------------
echo [3/6] Menghentikan Hardware Bridge lama jika sedang berjalan...
taskkill /IM HardwareBridge.exe /F >nul 2>nul
if errorlevel 1 (
    echo   [OK] Tidak ada instance lama yang berjalan.
) else (
    echo   [OK] Instance lama dihentikan.
)

REM ----------------------------------------------------------
REM [4/6] Memasang auto-start saat login Windows
REM ----------------------------------------------------------
echo [4/6] Memasang auto-start saat Windows login...
if /i "%RUN_MODE%"=="EXE" (
    set "LNK_TARGET=%EXE%"
) else (
    set "LNK_TARGET=%BASE_DIR%\Jalankan_Diam.vbs"
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '!LNK_TARGET!'; $s.WorkingDirectory = '%BASE_DIR%'; $s.Description = 'WebApp Hardware Bridge Universal - Direct Print dan Timbangan'; $s.Save()" >nul 2>nul

if exist "%SHORTCUT%" (
    echo   [OK] Auto-start terpasang di folder Startup Windows.
) else (
    echo   [PERINGATAN] Gagal membuat shortcut auto-start.
    echo                Bridge tetap bisa dijalankan manual lewat Jalankan.bat
)

REM Shortcut dashboard di Desktop supaya kasir gampang membukanya
(
    echo [InternetShortcut]
    echo URL=http://127.0.0.1:%PORT%
) > "%DESKTOP_LNK%" 2>nul
if exist "%DESKTOP_LNK%" echo   [OK] Shortcut "Hardware Bridge Dashboard" dibuat di Desktop.

REM ----------------------------------------------------------
REM [5/6] Menjalankan Hardware Bridge
REM ----------------------------------------------------------
echo [5/6] Menjalankan Hardware Bridge di System Tray...
if /i "%RUN_MODE%"=="EXE" (
    start "" "%EXE%"
) else (
    if exist "%BASE_DIR%\Jalankan_Diam.vbs" (
        start "" wscript.exe "%BASE_DIR%\Jalankan_Diam.vbs"
    ) else (
        start "" /min cmd /c "python "%BASE_DIR%\app.py""
    )
)

REM ----------------------------------------------------------
REM [6/6] Memverifikasi service benar-benar hidup
REM ----------------------------------------------------------
echo [6/6] Memverifikasi service ^(menunggu maksimal 20 detik^)...
set "ALIVE=0"
set "LIVE_PORT=%PORT%"
for /l %%i in (1,1,10) do (
    if "!ALIVE!"=="0" (
        call :CekPort !PORT!
        if "!ALIVE!"=="0" call :CekPort 12212
        if "!ALIVE!"=="0" powershell -NoProfile -Command "Start-Sleep -Milliseconds 1800" >nul 2>nul
    )
)

echo.
if "!ALIVE!"=="1" (
    echo ==========================================================
    echo   PEMASANGAN SELESAI - HARDWARE BRIDGE SUDAH BERJALAN
    echo ==========================================================
    echo   Status      : Aktif / Online
    echo   System Tray : Ikon hijau di pojok kanan bawah dekat jam
    echo   Dashboard   : http://127.0.0.1:!LIVE_PORT!
    echo   WebSocket   : ws://127.0.0.1:!LIVE_PORT!/ws
    echo   Auto-start  : AKTIF, otomatis nyala tiap login Windows
    echo   Berkas log  : %BASE_DIR%\logs\hardware_bridge.log
    echo.
    echo   Langkah berikutnya:
    echo     - Atur printer dan timbangan lewat Dashboard
    echo     - Cek kondisi kapan saja lewat Cek_Status.bat
    echo     - Copot auto-start lewat UNINSTALL.bat
    echo ==========================================================
    echo.
    echo   Membuka dashboard di browser...
    start "" "http://127.0.0.1:!LIVE_PORT!"
) else (
    echo ==========================================================
    echo   SERVICE BELUM BERHASIL DIVERIFIKASI
    echo ==========================================================
    echo   Auto-start sudah terpasang, tetapi port %PORT% belum menjawab.
    echo.
    echo   Yang perlu dicek:
    echo     1. Lihat System Tray. Bila ikon sudah muncul, bridge jalan
    echo        normal dan pemeriksaan ini hanya kehabisan waktu.
    echo     2. Windows Defender / antivirus memblokir HardwareBridge.exe.
    echo        Tambahkan folder ini ke daftar pengecualian ^(Exclusions^).
    echo     3. Baca berkas log:
    echo        %BASE_DIR%\logs\hardware_bridge.log
    echo     4. Jalankan Jalankan_Konsol.bat untuk melihat pesan galat
    echo        secara langsung di layar.
    echo ==========================================================
)

echo.
pause
endlocal
exit /b 0

REM ==========================================================
REM Subrutin
REM ==========================================================
:CekPort
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:%~1/api/status' -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 (
    set "ALIVE=1"
    set "LIVE_PORT=%~1"
)
exit /b 0

:BuatConfigBawaan
>"%CFG%" echo {
>>"%CFG%" echo   "server": {
>>"%CFG%" echo     "host": "0.0.0.0",
>>"%CFG%" echo     "port": 18212,
>>"%CFG%" echo     "scale_port": null,
>>"%CFG%" echo     "cors_origins": ["*"],
>>"%CFG%" echo     "enable_tray": true,
>>"%CFG%" echo     "sharing_mode": "continuous",
>>"%CFG%" echo     "idle_release_seconds": 4.0,
>>"%CFG%" echo     "pause_auto_resume_seconds": 600,
>>"%CFG%" echo     "enable_scale_at_startup": false
>>"%CFG%" echo   },
>>"%CFG%" echo   "printers": {
>>"%CFG%" echo     "default_raw_printer": "",
>>"%CFG%" echo     "default_doc_printer": "",
>>"%CFG%" echo     "default_encoding": "cp437",
>>"%CFG%" echo     "pools": {},
>>"%CFG%" echo     "network_printers": []
>>"%CFG%" echo   },
>>"%CFG%" echo   "scales": [
>>"%CFG%" echo     {
>>"%CFG%" echo       "name": "Simulator Timbangan",
>>"%CFG%" echo       "port": "SIM",
>>"%CFG%" echo       "protocol": "auto",
>>"%CFG%" echo       "baud": 9600,
>>"%CFG%" echo       "databits": 8,
>>"%CFG%" echo       "parity": "N",
>>"%CFG%" echo       "stopbits": 1,
>>"%CFG%" echo       "poll_interval": 0.5,
>>"%CFG%" echo       "autoconnect": false
>>"%CFG%" echo     }
>>"%CFG%" echo   ]
>>"%CFG%" echo }
exit /b 0
