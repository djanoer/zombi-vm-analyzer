@echo off
setlocal

TITLE VM Zombie Analyzer (Portable)

rem Launcher portable Windows 11 (WinPython).
rem Letakkan folder project ini DI SEBELAH folder WPy64-* hasil ekstrak WinPython,
rem lalu klik dua kali file ini. Tidak perlu install Python di sistem.

cd /d "%~dp0"

if not exist "app\main.py" (
    echo [ERROR] File app\main.py tidak ditemukan.
    pause
    exit /b 1
)

if not exist "data" (
    echo [System] Membuat folder data...
    mkdir "data"
)

rem Cari python.exe WinPython portable (nama folder mengikuti versi, jadi dideteksi otomatis)
set "PYEXE="
for /d %%D in ("%~dp0..\WPy64-*") do (
    for /d %%P in ("%%D\python-3.*.amd64") do (
        if exist "%%P\python.exe" set "PYEXE=%%P\python.exe"
    )
)

if not defined PYEXE (
    echo [ERROR] WinPython tidak ditemukan.
    echo [INFO] Letakkan folder project ini di sebelah folder WPy64-* hasil ekstrak WinPython.
    echo [INFO] Lihat INSTALL_WINDOWS_PORTABLE.md untuk langkah lengkapnya.
    pause
    exit /b 1
)

echo [System] Menjalankan Streamlit Server...
"%PYEXE%" -m streamlit run app\main.py

pause
endlocal
