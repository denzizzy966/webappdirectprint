@echo off
setlocal
title WebApp Hardware Bridge - Mode Diagnosa (Log Langsung)
cd /d "%~dp0"

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
set "LOG=%BASE_DIR%\logs\hardware_bridge.log"

echo ==========================================================
echo   Hardware Bridge - MODE DIAGNOSA
echo ==========================================================
echo   Bridge dijalankan ulang, lalu log ditampilkan langsung
echo   di jendela ini secara real-time.
echo.
echo   Gunakan mode ini kalau bridge tidak mau hidup atau
echo   printer / timbangan tidak terdeteksi.
echo.
echo   Tekan Ctrl + C untuk berhenti memantau.
echo   ^(Bridge tetap berjalan di System Tray^)
echo ==========================================================
echo.

if not exist "%BASE_DIR%\logs" mkdir "%BASE_DIR%\logs" >nul 2>nul

echo Menghentikan instance lama...
taskkill /IM HardwareBridge.exe /F >nul 2>nul

if exist "%BASE_DIR%\HardwareBridge.exe" (
    echo Menjalankan HardwareBridge.exe...
    start "" "%BASE_DIR%\HardwareBridge.exe"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] HardwareBridge.exe tidak ada dan Python tidak terpasang.
        echo         Pastikan ZIP sudah diekstrak lebih dulu.
        echo.
        pause
        exit /b 1
    )
    echo Menjalankan lewat Python ^(mode konsol penuh^)...
    python "%BASE_DIR%\app.py"
    echo.
    pause
    exit /b 0
)

echo Menunggu log terbentuk...
powershell -NoProfile -Command "Start-Sleep -Seconds 3" >nul 2>nul

echo.
echo ----------------------------------------------------------
echo   LOG LANGSUNG: %LOG%
echo ----------------------------------------------------------
if not exist "%LOG%" (
    echo   [PERINGATAN] Berkas log belum terbentuk.
    echo   Kemungkinan HardwareBridge.exe diblokir antivirus
    echo   atau folder ini tidak punya izin tulis.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -LiteralPath '%LOG%' -Tail 40 -Wait"

endlocal
