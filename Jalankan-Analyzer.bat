@echo off
setlocal EnableExtensions DisableDelayedExpansion

TITLE VM Zombie Analyzer (Portable)

rem Launcher portable Windows 11 (WinPython) - klik dua kali langsung jalan.
rem Letakkan folder project ini DI SEBELAH folder WPy64-* hasil ekstrak WinPython.
rem Tidak perlu install Python di sistem, tidak butuh administrator.
rem
rem Versi hardened (usulan QA 2026-09-30): seluruh logika deteksi ditulis TANPA
rem blok multi-baris (...), sehingga aman untuk path yang mengandung kurung,
rem mis. D:\Aplikasi (Baru)\ atau WPy64-31380 (1) hasil ekstrak ganda.

cd /d "%~dp0" || goto :gagal_cd
if not exist "app\main.py" goto :no_main
if not exist "data" mkdir "data" >nul 2>&1

rem ---- cari python.exe WinPython di folder induk (sejajar dengan project) ----
set "PYEXE="
for %%I in ("%~dp0..") do set "PARENT=%%~fI"
for /d %%D in ("%PARENT%\WPy64-*") do call :cek_satu "%%~fD"
if not defined PYEXE goto :no_python
echo [System] Python: "%PYEXE%"

rem ---- cek dependensi via folder site-packages (tanpa menjalankan python) ----
for %%H in ("%PYEXE%") do set "PYHOME=%%~dpH"
if exist "%PYHOME%Lib\site-packages\streamlit" goto :deps_ok
echo [ERROR] Dependensi belum terinstall ke WinPython portable.
echo [INFO] Jalankan Setup-Windows.bat terlebih dahulu (sekali saja, butuh internet).
pause
exit /b 1
:deps_ok

echo [System] Menjalankan Streamlit Server...
echo [INFO] Browser akan terbuka otomatis di http://127.0.0.1:8501
echo [INFO] Tutup jendela ini untuk menghentikan server.
"%PYEXE%" -m streamlit run "app\main.py" --server.address 127.0.0.1
pause
endlocal
exit /b 0

:cek_satu
rem %~1 = satu folder WPy64-* (sudah path absolut, dikutip)
if defined PYEXE goto :eof
if exist "%~1\python\python.exe" set "PYEXE=%~1\python\python.exe" & goto :eof
for /d %%P in ("%~1\python-3.*") do if exist "%%~fP\python.exe" set "PYEXE=%%~fP\python.exe"
if defined PYEXE goto :eof
echo [System] Pola standar tidak cocok, mencari python.exe di dalam "%~1" ...
for /r "%~1" %%Q in (python.exe) do if not defined PYEXE set "PYEXE=%%~fQ"
goto :eof

:no_main
echo [ERROR] File app\main.py tidak ditemukan.
echo [INFO] Pastikan file ini dijalankan dari dalam folder project zombi-vm-analyzer.
pause
exit /b 1

:gagal_cd
echo [ERROR] Gagal pindah ke folder script.
pause
exit /b 1

:no_python
echo [ERROR] WinPython tidak ditemukan.
echo [INFO] Letakkan folder project ini di sebelah folder WPy64-* hasil ekstrak WinPython.
echo [INFO] Lihat INSTALL_WINDOWS_PORTABLE.md untuk langkah lengkapnya.
pause
exit /b 1
