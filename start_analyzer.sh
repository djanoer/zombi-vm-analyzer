#!/usr/bin/env bash
# VM Zombie Analyzer Decision Support System - launcher Linux
# Porting dari start_analyzer.bat
set -euo pipefail

cd "$(dirname "$0")"

echo "[System] Memeriksa virtual environment..."
if [ ! -x "venv/bin/python" ]; then
    echo "[ERROR] Virtual environment tidak ditemukan."
    echo "[INFO] Pastikan folder venv tersedia di root project."
    exit 1
fi

if [ ! -f "app/main.py" ]; then
    echo "[ERROR] File app/main.py tidak ditemukan."
    exit 1
fi

if [ ! -d "data" ]; then
    echo "[System] Membuat folder data..."
    mkdir -p "data"
fi

echo "[System] Menjalankan Streamlit Server..."
exec venv/bin/python -m streamlit run app/main.py
