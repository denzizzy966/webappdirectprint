@echo off
setlocal
title Mencopot WebApp Hardware Bridge Universal
cd /d "%~dp0"

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_DIR%\HardwareBridge.lnk"
set "DESKTOP_LNK=%USERPROFILE%\Desktop\Hardware Bridge Dashboard.url"

echo ==========================================================
echo   Mencopot WebApp Hardware Bridge Universal
echo ==========================================================
echo.

echo [1/4] Menghentikan service yang sedang berjalan...
taskkill /IM HardwareBridge.exe /F >nul 2>nul
if errorlevel 1 (
    echo   [OK] Tidak ada proses HardwareBridge.exe yang aktif.
) else (
    echo   [OK] HardwareBridge.exe dihentikan.
)

echo [2/4] Menghapus auto-start dari folder Startup Windows...
if exist "%SHORTCUT%" (
    del /f /q "%SHORTCUT%" >nul 2>nul
    echo   [OK] Shortcut auto-start dihapus.
) else (
    echo   [i] Shortcut auto-start tidak ditemukan.
)

echo [3/4] Menghapus shortcut dashboard di Desktop...
if exist "%DESKTOP_LNK%" (
    del /f /q "%DESKTOP_LNK%" >nul 2>nul
    echo   [OK] Shortcut Desktop dihapus.
) else (
    echo   [i] Shortcut Desktop tidak ditemukan.
)

echo [4/4] Menghapus aturan firewall akses LAN jika pernah dipasang...
netsh advfirewall firewall delete rule name="WebApp Hardware Bridge" >nul 2>nul
if errorlevel 1 (
    echo   [i] Tidak ada aturan firewall milik Hardware Bridge.
) else (
    echo   [OK] Aturan firewall dihapus.
)

echo.
echo ==========================================================
echo   HARDWARE BRIDGE BERHASIL DICOPOT
echo ==========================================================
echo   Hardware Bridge tidak akan menyala lagi saat Windows login.
echo.
echo   Yang SENGAJA tidak dihapus supaya data Anda aman:
echo     - bridge_config.json   ^(setelan printer dan timbangan^)
echo     - folder logs\         ^(riwayat aktivitas^)
echo.
echo   Ingin membuang total? Hapus saja folder ini:
echo     %BASE_DIR%
echo.
echo   Ingin memasang lagi? Jalankan INSTALL.bat.
echo ==========================================================
echo.
pause
endlocal
