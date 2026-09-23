@echo off
setlocal EnableDelayedExpansion
title Status WebApp Hardware Bridge Universal
cd /d "%~dp0"

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
set "CFG=%BASE_DIR%\bridge_config.json"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_DIR%\HardwareBridge.lnk"

echo ==========================================================
echo   Status WebApp Hardware Bridge Universal
echo ==========================================================
echo.

set "PORT=18212"
if exist "%CFG%" (
    for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $raw = Get-Content -Raw -LiteralPath '%CFG%'; $cfg = ConvertFrom-Json $raw; $cfg.server.port } catch { 18212 }"`) do set "PORT=%%P"
)
if "!PORT!"=="" set "PORT=18212"

echo   Folder      : %BASE_DIR%
echo   Port setelan: !PORT!
echo.

echo   Proses HardwareBridge.exe:
call :CekProses
if "!PROSES_ADA!"=="1" (
    echo     BERJALAN
) else (
    echo     TIDAK BERJALAN
)

echo.
echo   Auto-start saat login Windows:
if exist "%SHORTCUT%" (
    echo     AKTIF - %SHORTCUT%
) else (
    echo     TIDAK AKTIF - jalankan INSTALL.bat untuk mengaktifkan
)

echo.
echo   Uji koneksi dashboard:
set "ALIVE=0"
set "LIVE_PORT="
call :CekPort !PORT!
if "!ALIVE!"=="0" call :CekPort 12212

if "!ALIVE!"=="1" (
    echo     ONLINE - http://127.0.0.1:!LIVE_PORT!
    echo.
    echo   Ringkasan dari /api/status:
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:!LIVE_PORT!/api/status' -TimeoutSec 4 -UseBasicParsing; $j = ConvertFrom-Json $r.Content; ConvertTo-Json -InputObject $j -Depth 4 } catch { 'Tidak dapat membaca status.' }"
) else (
    echo     TIDAK MENJAWAB di port !PORT! maupun 12212
    echo.
    echo   Yang bisa dicoba:
    echo     1. Jalankan INSTALL.bat atau Jalankan.bat
    echo     2. Lihat 20 baris log terakhir di bawah ini
    echo     3. Jalankan Jalankan_Konsol.bat untuk melihat galat langsung
)

echo.
echo ----------------------------------------------------------
echo   20 baris terakhir logs\hardware_bridge.log
echo ----------------------------------------------------------
if exist "%BASE_DIR%\logs\hardware_bridge.log" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -LiteralPath '%BASE_DIR%\logs\hardware_bridge.log' -Tail 20"
) else (
    echo   ^(berkas log belum terbentuk^)
)

echo.
pause
endlocal
exit /b 0

:CekProses
REM Memakai PowerShell, bukan "tasklist | find", karena perintah find bisa
REM tertukar dengan find versi Unix bila Git Bash / GnuWin ada di PATH.
set "PROSES_ADA=0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-Process -Name HardwareBridge -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>nul
if not errorlevel 1 set "PROSES_ADA=1"
exit /b 0

:CekPort
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:%~1/api/status' -TimeoutSec 3 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 (
    set "ALIVE=1"
    set "LIVE_PORT=%~1"
)
exit /b 0
