#!/usr/bin/env bash
# ==============================================================================
# Console Runner WebApp Hardware Bridge (Linux)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prioritaskan direktori script itu sendiri, lalu direktori induk (jika script berada di folder linux/)
BASE_DIR=""
for cand in "$SCRIPT_DIR" "$SCRIPT_DIR/.." "$PWD"; do
    if [ -f "$cand/app.py" ]; then
        BASE_DIR="$(cd "$cand" && pwd)"
        break
    fi
done

if [ -z "$BASE_DIR" ]; then
    BASE_DIR="$SCRIPT_DIR"
fi

cd "$BASE_DIR"

if [ -d "$BASE_DIR/venv" ]; then
    PYTHON_BIN="$BASE_DIR/venv/bin/python3"
else
    PYTHON_BIN="python3"
fi

echo "Menjalankan WebApp Hardware Bridge di konsol..."
echo "Akses Dashboard di: http://127.0.0.1:18212 (atau 12212)"
$PYTHON_BIN app.py "$@"
