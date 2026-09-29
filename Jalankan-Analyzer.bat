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

rem Cari python.exe WinPython portable (nama folder mengikuti versi, jadi dideteksi otomatis).
rem Folder project harus bersebelahan dengan folder WPy64-* dalam satu folder induk.
set "PYEXE="
for %%I in ("%~dp0..") do set "PARENT=%%~fI"
for /d %%D in ("%PARENT%\WPy64-*") do (
    if exist "%%D\python\python.exe" set "PYEXE=%%D\python\python.exe"
    for /d %%P in ("%%D\python-3.*.amd64") do (
        if exist "%%P\python.exe" set "PYEXE=%%P\python.exe"
    )
    rem Fallback terakhir: susuri folder WPy64-* bila kedua pola di atas tidak cocok
    if not defined PYEXE (
        for /r "%%D" %%P in (python.exe) do (
            if not defined PYEXE set "PYEXE=%%P"
        )
    )
)
echo [System] Python: "%PYEXE%"

if not defined PYEXE (
    echo [ERROR] WinPython tidak ditemukan.
    echo [INFO] Letakkan folder project ini di sebelah folder WPy64-* hasil ekstrak WinPython.
    echo [INFO] Lihat INSTALL_WINDOWS_PORTABLE.md untuk langkah lengkapnya.
    pause
    exit /b 1
)

rem Cek dependensi via folder site-packages (tanpa menjalankan python -c)
for %%H in ("%PYEXE%\..") do set "PYHOME=%%~fH"
if not exist "%PYHOME%\Lib\site-packages\streamlit" (
    echo [ERROR] Dependensi belum terinstall ke WinPython portable.
    echo [INFO] Jalankan Setup-Windows.bat terlebih dahulu (sekali saja, butuh internet).
    pause
    exit /b 1
)

echo [System] Menjalankan Streamlit Server...
"%PYEXE%" -m streamlit run app\main.py

pause
endlocal
