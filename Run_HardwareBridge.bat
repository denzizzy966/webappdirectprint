@echo off
title WebApp Hardware Bridge Universal
cd /d "%~dp0"

echo ==========================================================
echo   Menjalankan WebApp Hardware Bridge Universal...
echo ==========================================================
echo.

if exist "HardwareBridge.exe" (
    echo Menjalankan HardwareBridge.exe...
    start "" "HardwareBridge.exe"
) else (
    echo Menjalankan via Python...
    python app.py
)

exit /b 0
