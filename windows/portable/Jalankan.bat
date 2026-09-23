@echo off
setlocal
title Menjalankan WebApp Hardware Bridge Universal
cd /d "%~dp0"

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"

echo ==========================================================
echo   Menjalankan WebApp Hardware Bridge Universal
echo   ^(sekali jalan, tanpa memasang auto-start^)
echo ==========================================================
echo.

if not exist "%BASE_DIR%\logs" mkdir "%BASE_DIR%\logs" >nul 2>nul

REM Memakai PowerShell, bukan "tasklist | find", karena perintah find bisa
REM tertukar dengan find versi Unix bila Git Bash / GnuWin ada di PATH.
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-Process -Name HardwareBridge -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>nul
if not errorlevel 1 (
    echo   [i] Hardware Bridge sudah berjalan. Tidak dijalankan dua kali.
    echo       Lihat ikon hijau di System Tray, atau jalankan Cek_Status.bat.
    echo.
    pause
    exit /b 0
)

if exist "%BASE_DIR%\HardwareBridge.exe" (
    echo   Menjalankan HardwareBridge.exe di System Tray...
    start "" "%BASE_DIR%\HardwareBridge.exe"
    echo   [OK] Ikon hijau akan muncul di pojok kanan bawah dekat jam.
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo   [ERROR] HardwareBridge.exe tidak ada dan Python juga tidak terpasang.
        echo           Pastikan ZIP sudah diekstrak lebih dulu ^(bukan dibuka langsung^).
        echo.
        pause
        exit /b 1
    )
    echo   Menjalankan lewat Python...
    start "" wscript.exe "%BASE_DIR%\Jalankan_Diam.vbs"
)

echo.
echo   Dashboard: http://127.0.0.1:18212
echo   Jendela ini boleh ditutup, bridge tetap jalan di latar belakang.
echo.
timeout /t 5 >nul
endlocal
