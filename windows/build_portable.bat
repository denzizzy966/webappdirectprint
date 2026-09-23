@echo off
setlocal EnableDelayedExpansion
title Build Paket Portable Windows - WebApp Hardware Bridge
cd /d "%~dp0\.."

set "ROOT=%CD%"
set "STAGE=%ROOT%\dist\HardwareBridge_Windows_x64_Portable"
set "ZIPFILE=%ROOT%\HardwareBridge_Windows_x64_Portable.zip"

echo ==========================================================
echo   Build Paket Portable Windows x64
echo   WebApp Hardware Bridge Universal
echo ==========================================================
echo   Root proyek : %ROOT%
echo ==========================================================
echo.

REM ----------------------------------------------------------
REM [1/4] Kompilasi HardwareBridge.exe dengan PyInstaller
REM ----------------------------------------------------------
echo [1/4] Mengompilasi HardwareBridge.exe...

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo   PyInstaller belum terpasang, menginstal sekarang...
    pip install pyinstaller
)

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

if not exist "%ROOT%\dist\HardwareBridge\HardwareBridge.exe" (
    echo.
    echo   [ERROR] Kompilasi gagal, HardwareBridge.exe tidak terbentuk.
    echo           Periksa pesan galat PyInstaller di atas.
    pause
    exit /b 1
)
echo   [OK] HardwareBridge.exe berhasil dibangun.

REM ----------------------------------------------------------
REM [2/4] Menyusun isi paket portable
REM ----------------------------------------------------------
echo [2/4] Menyusun isi paket portable...

if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%" >nul 2>nul

REM Binary hasil PyInstaller (HardwareBridge.exe + _internal\)
xcopy "%ROOT%\dist\HardwareBridge\*" "%STAGE%\" /E /I /Y /Q >nul

REM Skrip installer, runner, dan BACA_SAYA
xcopy "%ROOT%\windows\portable\*" "%STAGE%\" /E /I /Y /Q >nul

REM Dokumentasi ikut dibundel supaya paket tetap berguna saat offline
mkdir "%STAGE%\docs" >nul 2>nul
xcopy "%ROOT%\docs\*" "%STAGE%\docs\" /E /I /Y /Q >nul

REM Contoh SDK dan skrip integrasi siap pakai
mkdir "%STAGE%\sdk" >nul 2>nul
copy /y "%ROOT%\static\js\hardware-bridge.js" "%STAGE%\sdk\" >nul 2>nul
copy /y "%ROOT%\static\cara-pakai.html" "%STAGE%\sdk\" >nul 2>nul
xcopy "%ROOT%\erpnext\*" "%STAGE%\sdk\erpnext\" /E /I /Y /Q >nul 2>nul

REM Folder log kosong supaya izin tulis langsung terbentuk
mkdir "%STAGE%\logs" >nul 2>nul

echo   [OK] Isi paket tersusun di:
echo        %STAGE%

REM ----------------------------------------------------------
REM [3/4] Memampatkan menjadi berkas ZIP
REM ----------------------------------------------------------
echo [3/4] Memampatkan menjadi ZIP...
if exist "%ZIPFILE%" del /f /q "%ZIPFILE%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%STAGE%\*' -DestinationPath '%ZIPFILE%' -CompressionLevel Optimal -Force"

if not exist "%ZIPFILE%" (
    echo   [ERROR] Gagal membuat berkas ZIP.
    pause
    exit /b 1
)

REM ----------------------------------------------------------
REM [4/4] Ringkasan
REM ----------------------------------------------------------
echo [4/4] Selesai.
echo.
echo ==========================================================
echo   PAKET PORTABLE WINDOWS SIAP DIBAGIKAN
echo ==========================================================
for %%F in ("%ZIPFILE%") do echo   Berkas : %%~nxF  ^(%%~zF bytes^)
echo   Lokasi : %ZIPFILE%
echo.
echo   Isi paket:
echo     HardwareBridge.exe + _internal\
echo     INSTALL.bat, UNINSTALL.bat, Jalankan.bat
echo     Cek_Status.bat, Jalankan_Konsol.bat, Izinkan_Akses_LAN.bat
echo     bridge_config.json, BACA_SAYA.txt
echo     docs\ dan sdk\
echo.
echo   Cara pakai di PC tujuan: ekstrak ZIP, klik 2x INSTALL.bat.
echo ==========================================================
echo.
pause
endlocal
