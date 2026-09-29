@echo off
setlocal EnableExtensions DisableDelayedExpansion

TITLE Setup Zombie Analyzer (Windows Portable)

rem Dijalankan SEKALI dengan internet: menginstall dependensi ke WinPython portable.
rem Setelah ini, folder bundle bisa dicopy ke PC Windows 11 lain tanpa setup ulang.
rem
rem Versi hardened (usulan QA 2026-09-30): seluruh logika deteksi ditulis TANPA
rem blok multi-baris (...), sehingga aman untuk path yang mengandung kurung,
rem mis. D:\Aplikasi (Baru)\ atau WPy64-31380 (1) hasil ekstrak ganda.

cd /d "%~dp0" || goto :gagal_cd
if not exist "requirements.txt" goto :no_req

rem ---- cari python.exe WinPython di folder induk (sejajar dengan project) ----
set "PYEXE="
for %%I in ("%~dp0..") do set "PARENT=%%~fI"
for /d %%D in ("%PARENT%\WPy64-*") do call :cek_satu "%%~fD"
if not defined PYEXE goto :no_python
echo [System] Python: "%PYEXE%"

echo [System] Menginstall dependensi ke WinPython portable...
echo [INFO] Butuh koneksi internet (hanya sekali ini).
"%PYEXE%" -m pip install -r requirements.txt || goto :pip_gagal

echo.
echo [OK] Setup selesai. Klik dua kali Jalankan-Analyzer.bat untuk memakai aplikasi.
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

:no_req
echo [ERROR] File requirements.txt tidak ditemukan.
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

:pip_gagal
echo [ERROR] Instalasi gagal. Periksa koneksi internet lalu coba lagi.
pause
exit /b 1
