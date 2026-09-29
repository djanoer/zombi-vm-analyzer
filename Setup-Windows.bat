@echo off
setlocal

TITLE Setup Zombie Analyzer (Windows Portable)

rem Dijalankan SEKALI dengan internet: menginstall dependensi ke WinPython portable.
rem Setelah ini, folder bundle bisa dicopy ke PC Windows 11 lain tanpa setup ulang.

cd /d "%~dp0"

if not exist "requirements.txt" (
    echo [ERROR] File requirements.txt tidak ditemukan.
    pause
    exit /b 1
)

rem Cari python.exe WinPython portable di sebelah folder project.
rem Folder project harus bersebelahan dengan folder WPy64-* dalam satu folder induk.
set "PYEXE="
for %%I in ("%~dp0..") do set "PARENT=%%~fI"
for /d %%D in ("%PARENT%\WPy64-*") do (
    for /d %%P in ("%%D\python-3.*.amd64") do (
        if exist "%%P\python.exe" set "PYEXE=%%P\python.exe"
    )
    rem Fallback: cari python.exe secara rekursif bila pola nama folder tidak cocok
    if not defined PYEXE (
        for /f "delims=" %%P in ('dir /b /s "%%D\python.exe" 2^>nul') do (
            if not defined PYEXE set "PYEXE=%%P"
        )
    )
)

if not defined PYEXE (
    echo [ERROR] WinPython tidak ditemukan.
    echo [INFO] Letakkan folder project ini di sebelah folder WPy64-* hasil ekstrak WinPython.
    pause
    exit /b 1
)

echo [System] Menginstall dependensi ke WinPython portable...
echo [INFO] Butuh koneksi internet (hanya sekali ini).
"%PYEXE%" -m pip install -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Instalasi gagal. Periksa koneksi internet lalu coba lagi.
    pause
    exit /b 1
)

echo.
echo [OK] Setup selesai. Klik dua kali Jalankan-Analyzer.bat untuk memakai aplikasi.
pause
endlocal
