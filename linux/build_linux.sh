#!/usr/bin/env bash
# ==============================================================================
# Build Standalone Binary Executable (Linux ELF)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$BASE_DIR"

if [ -d "$BASE_DIR/venv" ]; then
    PIP_BIN="$BASE_DIR/venv/bin/pip"
    PYINSTALLER_BIN="$BASE_DIR/venv/bin/pyinstaller"
else
    PIP_BIN="pip"
    PYINSTALLER_BIN="pyinstaller"
fi

$PIP_BIN install pyinstaller --quiet

echo "Membangun binary Linux dengan PyInstaller..."
$PYINSTALLER_BIN --noconfirm --clean \
    --name "hardware-bridge" \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --add-data "bridge_config.json:." \
    --hidden-import "uvicorn" \
    --hidden-import "fastapi" \
    --hidden-import "serial" \
    --hidden-import "jinja2" \
    app.py

echo "✅ Binary berhasil dibangun di dist/hardware-bridge/hardware-bridge"
