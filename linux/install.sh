#!/usr/bin/env bash
# ==============================================================================
# Installer WebApp Hardware Bridge untuk Linux Mint 22 & Ubuntu 22
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="${SUDO_USER:-$USER}"

# ────────────────────────────────────────────────────────────
# Deteksi Otomatis Direktori Utama Proyek (app.py)
# ────────────────────────────────────────────────────────────
PROJECT_DIR=""
for cand in \
    "$SCRIPT_DIR" \
    "$SCRIPT_DIR/.." \
    "$PWD" \
    "$PWD/webapp" \
    "$PWD/webappdirectprint" \
    "$SCRIPT_DIR/../webapp" \
    "$SCRIPT_DIR/../webappdirectprint" \
    "/home/$CURRENT_USER/Downloads/webapp" \
    "/home/$CURRENT_USER/Downloads/webappdirectprint" \
    "/home/$CURRENT_USER/webapp" \
    "/home/$CURRENT_USER/webappdirectprint"; do
    if [ -f "$cand/app.py" ]; then
        PROJECT_DIR="$(cd "$cand" && pwd)"
        break
    fi
done

# Jika belum ketemu, cari file app.py di sekitar folder
if [ -z "$PROJECT_DIR" ]; then
    FOUND=$(find "$SCRIPT_DIR" "$PWD" -maxdepth 3 -name "app.py" 2>/dev/null | head -n 1)
    if [ -n "$FOUND" ] && [ -f "$FOUND" ]; then
        PROJECT_DIR="$(cd "$(dirname "$FOUND")" && pwd)"
    fi
fi

if [ -z "$PROJECT_DIR" ] || [ ! -f "$PROJECT_DIR/app.py" ]; then
    echo "=========================================================="
    echo "  ❌ ERROR: File utama 'app.py' TIDAK DITEMUKAN!"
    echo "=========================================================="
    echo "  Lokasi script saat ini: $SCRIPT_DIR"
    echo ""
    echo "  Penyebab:"
    echo "  Tampaknya Anda hanya meng-copy folder 'linux/' saja ke komputer ini."
    echo "  Hardware Bridge membutuhkan SELURUH berkas proyek agar dapat berjalan."
    echo ""
    echo "  Solusi:"
    echo "  1. Salin seluruh isi folder proyek 'webappdirectprint' ke Linux ini:"
    echo "     - app.py                <-- berkas server utama"
    echo "     - bridge_config.json    <-- setelan port & timbangan"
    echo "     - requirements.txt      <-- daftar pustaka"
    echo "     - app/                  <-- modul logika printer & timbangan"
    echo "     - templates/            <-- tampilan web dashboard"
    echo "     - static/               <-- javascript & styling"
    echo "     - linux/                <-- script installer ini"
    echo ""
    echo "  2. Setelah diekstrak ke (misal: ~/webappdirectprint), jalankan:"
    echo "     cd ~/webappdirectprint"
    echo "     sudo bash linux/install.sh"
    echo "=========================================================="
    exit 1
fi

BASE_DIR="$PROJECT_DIR"

echo "=========================================================="
echo "  Pemasangan WebApp Hardware Bridge (Linux Mint / Ubuntu)"
echo "  User target:      $CURRENT_USER"
echo "  Direktori Proyek: $BASE_DIR"
echo "=========================================================="
echo ""

# 1. Cek dependensi sistem dasar (Python3, Venv, CUPS)
echo "[1/6] Memeriksa paket sistem dasar (Python, CUPS, Udev)..."
NEED_APT=0
if ! command -v python3 >/dev/null 2>&1; then NEED_APT=1; fi
if ! python3 -m venv --help >/dev/null 2>&1; then NEED_APT=1; fi
if ! command -v lpstat >/dev/null 2>&1; then NEED_APT=1; fi

if [ "$NEED_APT" -eq 1 ]; then
    echo "  Paket sistem dasar belum lengkap. Menyiapkan instalasi via APT..."
    # Tunggu sebentar jika apt sedang dikunci oleh mint-refresh-ca atau background updates
    for i in 1 2 3 4 5; do
        if fuser /var/lib/dpkg/lock >/dev/null 2>&1 || fuser /var/lib/apt/lists/lock >/dev/null 2>&1; then
            echo "  ⏳ APT sedang digunakan sistem (mint-refresh-ca). Menunggu 3 detik ($i/5)..."
            sleep 3
        else
            break
        fi
    done
    sudo apt-get update -qq || true
    sudo apt-get install -y python3 python3-pip python3-venv cups cups-client libcups2-dev build-essential || true
else
    echo "  ✅ Paket dasar (Python 3, Venv, CUPS) sudah terpasang lengkap."
fi

# 2. Pastikan service CUPS aktif
echo "[2/6] Memastikan CUPS printing service aktif..."
sudo systemctl enable --now cups || true

# 3. Buat Virtual Environment Python & Pasang Dependensi
echo "[3/6] Menyiapkan Virtual Environment Python..."
VENV_DIR="$BASE_DIR/venv"
if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/python3" ]; then
    python3 -m venv "$VENV_DIR"
fi

# 1. Pasang dari paket offline lokal (wheels) terlebih dahulu (cepat & 100% tanpa internet)
WHEELS_DIR=""
for w in \
    "$SCRIPT_DIR/wheels" \
    "$SCRIPT_DIR/linux/wheels" \
    "$BASE_DIR/linux/wheels" \
    "$BASE_DIR/wheels"; do
    if [ -d "$w" ] && [ -n "$(ls -A "$w" 2>/dev/null)" ]; then
        WHEELS_DIR="$w"
        break
    fi
done

if [ -n "$WHEELS_DIR" ]; then
    echo "  📦 Menemukan paket offline lokal di: $WHEELS_DIR"
    echo "  Menginstal dependensi secara offline (instan & tanpa internet)..."
    "$VENV_DIR/bin/pip" install --no-index --find-links="$WHEELS_DIR" fastapi uvicorn websockets pyserial Pillow PyMuPDF jinja2 python-multipart requests pystray python-xlib six || {
        "$VENV_DIR/bin/pip" install --no-index --find-links="$WHEELS_DIR" fastapi uvicorn websockets pyserial Pillow PyMuPDF jinja2 python-multipart requests
    }
fi

# 2. Cari berkas requirements.txt jika ada paket tambahan
REQ_FILE=""
for candidate in \
    "$BASE_DIR/requirements.txt" \
    "$BASE_DIR/requirement.txt" \
    "$SCRIPT_DIR/requirements.txt" \
    "$SCRIPT_DIR/requirement.txt" \
    "$SCRIPT_DIR/../requirements.txt" \
    "requirements.txt" \
    "requirement.txt"; do
    if [ -f "$candidate" ]; then
        REQ_FILE="$candidate"
        break
    fi
done

if [ -n "$REQ_FILE" ] && [ -z "$WHEELS_DIR" ]; then
    echo "  Memeriksa dependensi online dari: $REQ_FILE..."
    "$VENV_DIR/bin/pip" install -r "$REQ_FILE" || true
fi

# 4. Pasang Aturan Udev untuk Serial & USB Printer
echo "[4/6] Memasang aturan udev untuk port serial & printer..."
sudo cp "$SCRIPT_DIR/99-hardware-bridge.rules" /etc/udev/rules.d/99-hardware-bridge.rules 2>/dev/null || true
sudo udevadm control --reload-rules 2>/dev/null || true
sudo udevadm trigger 2>/dev/null || true

# 5. Tambahkan user ke grup dialout & lp
echo "[5/6] Menambahkan user '$CURRENT_USER' ke grup dialout dan lp..."
sudo usermod -aG dialout "$CURRENT_USER" || true
sudo usermod -aG lp "$CURRENT_USER" || true

# Pastikan folder logs dan seluruh berkas dimiliki oleh user target
mkdir -p "$BASE_DIR/logs"
sudo chown -R "$CURRENT_USER:$CURRENT_USER" "$BASE_DIR"

# 6. Pasang Service Systemd & Desktop System Tray
echo "[6/6] Memasang Systemd service & Desktop Tray Indicator..."
SERVICE_FILE="/etc/systemd/system/hardware-bridge.service"

sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=WebApp Hardware Bridge Universal Service
After=network.target cups.service

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$BASE_DIR
ExecStart=$VENV_DIR/bin/python3 $BASE_DIR/app.py --no-tray
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable hardware-bridge.service
sudo systemctl restart hardware-bridge.service

# Pasang Desktop System Tray Autostart untuk sesi grafis (Linux Mint Cinnamon / Ubuntu)
USER_HOME=$(getent passwd "$CURRENT_USER" | cut -d: -f6)
if [ -z "$USER_HOME" ]; then
    USER_HOME="/home/$CURRENT_USER"
fi

AUTOSTART_DIR="$USER_HOME/.config/autostart"
if [ -d "$USER_HOME" ]; then
    mkdir -p "$AUTOSTART_DIR"
    cat <<EOF > "$AUTOSTART_DIR/hardware-bridge-tray.desktop"
[Desktop Entry]
Type=Application
Name=Hardware Bridge Tray
Comment=WebApp Hardware Bridge System Tray Indicator
Exec=$VENV_DIR/bin/python3 $BASE_DIR/tray_indicator.py
Icon=printer
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
EOF
    chown -R "$CURRENT_USER:$CURRENT_USER" "$USER_HOME/.config" 2>/dev/null || true

    # Jalankan tray indicator sekarang untuk sesi desktop aktif jika tersedia
    if [ -f "$BASE_DIR/tray_indicator.py" ]; then
        pkill -f "$BASE_DIR/tray_indicator.py" 2>/dev/null || true
        sudo -u "$CURRENT_USER" DISPLAY="${DISPLAY:-:0}" nohup "$VENV_DIR/bin/python3" "$BASE_DIR/tray_indicator.py" >/dev/null 2>&1 &
    fi
fi

# Tunggu 2 detik untuk verifikasi kesehatan service
sleep 2

echo ""
if systemctl is-active --quiet hardware-bridge.service; then
    echo "=========================================================="
    echo "  ✅ PEMASANGAN SELESAI & SERVICE BERJALAN DI BACKGROUND!"
    echo "=========================================================="
    echo "  Status Service:  Active (running) 🟢"
    echo "  System Tray:     Ikon hijau aktif di pojok taskbar desktop"
    echo "  Dashboard Web:   http://127.0.0.1:18212 (atau 12212)"
    echo "  WebSocket:       ws://127.0.0.1:18212/ws (atau 12212)"
    echo ""
    echo "  Perintah pengelolaan:"
    echo "    - Cek status:  sudo systemctl status hardware-bridge"
    echo "    - Restart:     sudo systemctl restart hardware-bridge"
    echo "    - Lihat log:   journalctl -u hardware-bridge -f"
    echo "=========================================================="
else
    echo "=========================================================="
    echo "  ⚠️ SERVICE BELUM BERHASIL BERJALAN SEMPURNA"
    echo "=========================================================="
    echo "  Log error terakhir:"
    journalctl -u hardware-bridge.service -n 12 --no-pager || true
    echo ""
    echo "  Coba uji jalankan manual:"
    echo "    $VENV_DIR/bin/python3 $BASE_DIR/app.py"
    echo "=========================================================="
fi
