@echo off
title Build Standalone Executable Hardware Bridge (Windows)
cd /d "%~dp0\.."

echo ===================================================
echo  Membangun Standalone Executable (.exe)
echo ===================================================
echo.

where pyinstaller >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Menginstal PyInstaller...
    pip install pyinstaller
)

echo Memulai kompilasi dengan PyInstaller...
pyinstaller --noconfirm --clean ^
    --name "HardwareBridge" ^
    --windowed ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "bridge_config.json;." ^
    --hidden-import "win32print" ^
    --hidden-import "win32ui" ^
    --hidden-import "win32con" ^
    --hidden-import "fitz" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL.ImageWin" ^
    --hidden-import "pystray" ^
    --hidden-import "serial" ^
    --hidden-import "uvicorn" ^
    --hidden-import "fastapi" ^
    app.py

echo.
if exist "dist\HardwareBridge\HardwareBridge.exe" (
    echo [SUKSES] Binary executable berhasil dibangun di: dist\HardwareBridge\HardwareBridge.exe
) else (
    echo [SELESAI] Silakan periksa folder dist\
)

pause
