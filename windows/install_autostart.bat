@echo off
title Install Hardware Bridge Auto-Start Windows
cd /d "%~dp0\.."

set "TARGET_VBS=%~dp0run_background.vbs"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_DIR%\HardwareBridge.lnk"

echo ===================================================
echo  Memasang Auto-Start Hardware Bridge saat Login
echo ===================================================
echo.

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%TARGET_VBS%\"'; $s.WorkingDirectory = '%~dp0..'; $s.Save()"

if exist "%SHORTCUT%" (
    echo [SUKSES] Auto-Start berhasil dipasang di:
    echo "%SHORTCUT%"
    echo Hardware Bridge akan otomatis aktif setiap kali Anda menyalakan komputer.
) else (
    echo [GAGAL] Gagal membuat shortcut di Startup folder.
)

echo.
pause
