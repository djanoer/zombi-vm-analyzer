#!/usr/bin/env bash
# Setup sekali-jalan: instalasi Zombie VM Analyzer di mesin Linux TANPA internet.
#
# Cara pakai:
#   1. Letakkan file wheelhouse-*.zip (dari halaman Releases repo) di folder ini.
#   2. Jalankan: ./setup_offline.sh
#
# Syarat di mesin offline: python3.13 dan unzip terinstall.
set -euo pipefail

cd "$(dirname "$0")"

echo "[System] Setup offline Zombie VM Analyzer..."

# 1. Wheelhouse: ekstrak bila belum ada
if [ ! -d "wheelhouse" ]; then
    ZIP="$(ls wheelhouse-*.zip 2>/dev/null | head -n 1 || true)"
    if [ -z "${ZIP}" ]; then
        echo "[ERROR] wheelhouse-*.zip tidak ditemukan di folder ini."
        echo "[INFO] Download dari halaman Releases repo, lalu letakkan di sini."
        exit 1
    fi
    echo "[System] Mengekstrak ${ZIP} ..."
    unzip -q "${ZIP}"
fi

if [ ! -d "wheelhouse" ]; then
    echo "[ERROR] Folder wheelhouse/ tidak ditemukan setelah ekstrak."
    exit 1
fi

# 2. Python 3.13
if ! command -v python3.13 >/dev/null 2>&1; then
    echo "[ERROR] python3.13 tidak ditemukan di PATH."
    echo "[INFO] Install dulu, mis. Ubuntu: sudo apt install python3.13 python3.13-venv unzip"
    exit 1
fi

# 3. Virtual environment
if [ ! -x "venv/bin/python" ]; then
    echo "[System] Membuat virtual environment..."
    python3.13 -m venv venv
else
    echo "[System] Virtual environment sudah ada, dipakai ulang."
fi

# 4. Install dependensi TANPA internet
echo "[System] Menginstall dependensi (tanpa internet)..."
venv/bin/pip install --no-index --find-links=wheelhouse -r requirements.txt

# 5. Verifikasi
venv/bin/python -c "import streamlit, pandas, openpyxl; print('[OK] Dependensi terinstall.')"

echo ""
echo "[OK] Setup selesai."
echo "[INFO] Jalankan aplikasi : ./start_analyzer.sh"
echo "[INFO] Cronjob autostart : ./install_cron.sh (lihat INSTALL_OFFLINE.md)"
