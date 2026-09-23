@echo off
setlocal EnableDelayedExpansion
title Izinkan Akses Hardware Bridge dari Jaringan LAN

REM Butuh hak Administrator untuk mengubah Windows Firewall.
net session >nul 2>nul
if errorlevel 1 (
    echo ==========================================================
    echo   PERLU HAK ADMINISTRATOR
    echo ==========================================================
    echo   Meminta izin Administrator, klik "Yes" pada dialog UAC...
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b 0
)

cd /d "%~dp0"
set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
set "CFG=%BASE_DIR%\bridge_config.json"

echo ==========================================================
echo   Izinkan Akses Hardware Bridge dari Jaringan LAN
echo ==========================================================
echo.
echo   OPSIONAL. Hanya perlu dijalankan bila aplikasi web Anda
echo   dibuka dari KOMPUTER LAIN dalam satu jaringan, bukan dari
echo   PC yang sama dengan printer.
echo.
echo   Kalau kasir membuka aplikasi web di PC yang sama dengan
echo   printer ^(kasus paling umum^), Anda TIDAK perlu ini.
echo ==========================================================
echo.

set "PORT=18212"
if exist "%CFG%" (
    for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $raw = Get-Content -Raw -LiteralPath '%CFG%'; $cfg = ConvertFrom-Json $raw; $cfg.server.port } catch { 18212 }"`) do set "PORT=%%P"
)
if "!PORT!"=="" set "PORT=18212"

echo Membuka port !PORT! dan 12212 di Windows Firewall...
netsh advfirewall firewall delete rule name="WebApp Hardware Bridge" >nul 2>nul
netsh advfirewall firewall add rule name="WebApp Hardware Bridge" dir=in action=allow protocol=TCP localport=!PORT!,12212 profile=private,domain >nul 2>nul

if errorlevel 1 (
    echo   [GAGAL] Aturan firewall tidak dapat dipasang.
) else (
    echo   [OK] Aturan firewall terpasang untuk profil Private dan Domain.
    echo.
    echo   Catatan penting:
    echo     - Profil Public sengaja TIDAK dibuka demi keamanan.
    echo     - Pastikan "host" di bridge_config.json bernilai "0.0.0.0".
    echo.
    echo   Alamat IP komputer ini:
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' } | ForEach-Object { '    http://' + $_.IPAddress + ':!PORT!' }"
)

echo.
echo   Ingin menutup akses LAN lagi? Jalankan UNINSTALL.bat,
echo   atau perintah berikut sebagai Administrator:
echo     netsh advfirewall firewall delete rule name="WebApp Hardware Bridge"
echo.
pause
endlocal
