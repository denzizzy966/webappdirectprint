@echo off
title Install Hardware Bridge Auto-Start Windows
cd /d "%~dp0"

set "TARGET_EXE=%~dp0HardwareBridge.exe"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_DIR%\HardwareBridge.lnk"

echo ===================================================
echo  Memasang Auto-Start Hardware Bridge saat Login
echo ===================================================
echo.

if not exist "%TARGET_EXE%" (
    echo [ERROR] Berkas HardwareBridge.exe tidak ditemukan di folder ini!
    pause
    exit /b 1
)

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%TARGET_EXE%'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'WebApp Hardware Bridge Tray Service'; $s.Save()"

if exist "%SHORTCUT%" (
    echo [SUKSES] Auto-Start berhasil dipasang di:
    echo "%SHORTCUT%"
    echo.
    echo Hardware Bridge akan otomatis aktif di System Tray setiap kali Windows dinyalakan/login.
    echo.
    echo Menjalankan Hardware Bridge sekarang...
    start "" "%TARGET_EXE%"
) else (
    echo [GAGAL] Gagal membuat shortcut di Startup folder.
)

echo.
pause
