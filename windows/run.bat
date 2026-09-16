@echo off
title WebApp Hardware Bridge Universal
cd /d "%~dp0\.."

echo ===================================================
echo  WebApp Hardware Bridge Universal v2.1.0
echo  Direct Print & Scale Serial Connector
echo ===================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python tidak ditemukan di sistem PATH!
    echo Silakan install Python 3.10+ dari https://www.python.org/
    pause
    exit /b 1
)

echo Memeriksa dependensi...
if exist "requirements.txt" (
    pip install -r requirements.txt --quiet
) else if exist "requirement.txt" (
    pip install -r requirement.txt --quiet
) else if exist "windows\requirements.txt" (
    pip install -r windows\requirements.txt --quiet
) else (
    pip install fastapi uvicorn websockets pyserial Pillow pywin32 pystray PyMuPDF jinja2 python-multipart requests --quiet
)

echo Menjalankan Hardware Bridge...
echo Akses Web UI di: http://127.0.0.1:18212 (atau 12212)
python app.py

pause
