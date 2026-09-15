@echo off
setlocal

TITLE VM Zombie Analyzer Decision Support System

echo ===================================================
echo [System] Memeriksa direktori kerja...
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment tidak ditemukan.
    echo [INFO] Pastikan folder venv tersedia di root project.
    pause
    exit /b 1
)

if not exist "app\main.py" (
    echo [ERROR] File app\main.py tidak ditemukan.
    pause
    exit /b 1
)

if not exist "data" (
    echo [System] Membuat folder data...
    mkdir "data"
)

echo [System] Menjalankan Streamlit Server...
venv\Scripts\python.exe -m streamlit run app\main.py

pause
endlocal
