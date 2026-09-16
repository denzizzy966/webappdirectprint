@echo off
title Uninstall Hardware Bridge Auto-Start Windows

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_DIR%\HardwareBridge.lnk"

if exist "%SHORTCUT%" (
    del "%SHORTCUT%"
    echo [SUKSES] Auto-Start shortcut berhasil dihapus dari folder Startup.
) else (
    echo [INFO] Shortcut tidak ditemukan di Startup.
)

pause
