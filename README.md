# Zombie VM Analyzer v4.0

[![CI](https://github.com/djanoer/zombi-vm-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/djanoer/zombi-vm-analyzer/actions/workflows/ci.yml)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)

Aplikasi Streamlit untuk menganalisis VM idle/zombie dari data vROps — membantu mengidentifikasi VM yang tidak terpakai agar bisa ditindaklanjuti (disposal/reclaim).

## Fitur Utama

- Upload & validasi file CSV vROps
- Deteksi VM idle/zombie berbasis threshold
- Identity key per VM (vCenter + UUID), termasuk penanganan VM yang pindah vCenter
- Disposal rules & status tracking (disimpan di SQLite lokal)
- Snapshot & analisis tren antar periode
- Export hasil (Excel/CSV)
- Manual pengguna lengkap di dalam aplikasi
- Seluruh pesan error berbahasa Indonesia; detail teknis hanya tampil di mode debug

## Kebutuhan

- Python 3.13 (lihat `.python-version`)
- Ubuntu x86_64 (target deployment) atau Windows 11 (paket portable)
- Dependensi: `streamlit==1.63.0`, `pandas==3.0.5`, `openpyxl==3.1.5` (lihat `requirements.txt`)

> Catatan: aplikasi ini tool lokal single-user tanpa autentikasi. Jangan ekspos langsung ke jaringan publik tanpa lapisan keamanan tambahan.

## Cara Menjalankan

### A. Ubuntu offline (server tanpa internet)

Panduan lengkap: `INSTALL_OFFLINE.md`.

1. Download `wheelhouse-py3.13-manylinux_x86_64.zip` dari halaman
   [Releases](https://github.com/djanoer/zombi-vm-analyzer/releases),
   letakkan di folder project.
2. `./setup_offline.sh` — membuat virtual environment dan menginstall
   dependensi tanpa internet.
3. `./start_analyzer.sh` — menjalankan aplikasi.
4. Opsional: `./install_cron.sh` — autostart saat mesin menyala +
   keep-alive tiap 5 menit.

### B. Windows 11 portable (WinPython, tanpa instalasi)

Panduan lengkap: `INSTALL_WINDOWS_PORTABLE.md`.

1. Ekstrak WinPython 3.13 (mis. `WPy64-31380`) di sebelah folder project.
2. Klik dua kali `Setup-Windows.bat` (sekali saja, butuh internet) —
   menginstall dependensi ke WinPython portable.
3. Klik dua kali `Jalankan-Analyzer.bat` — aplikasi terbuka di browser.

> Bila muncul kotak "Open File - Security Warning", unblock sekali saja:
> klik kanan file `.bat` → Properties → centang "Unblock" → OK
> (atau via PowerShell: `Unblock-File`). Lihat Troubleshooting di
> `INSTALL_WINDOWS_PORTABLE.md`.

### C. Mode pengembangan (mesin dengan internet)

```bash
# 1. Buat virtual environment
python3.13 -m venv venv
source venv/bin/activate

# 2. Instal dependensi
pip install -r requirements.txt

# 3. Jalankan
streamlit run app/main.py
```

Lalu buka alamat yang ditampilkan Streamlit di browser (umumnya `http://localhost:8501`).

## Struktur Proyek

```
app/                        19 modul aplikasi (±6.400 baris)
  main.py                   Entry point — alur utama Streamlit
  analysis.py               Business rule analisis zombie
  data_loader.py            Ingest & validasi CSV
  status_tracking.py        Persistensi status disposal (SQLite)
  trend_analysis.py         Snapshot & analisis tren (SQLite)
  results_view.py           Tampilan hasil analisis
  trend_view.py             Tampilan tren
  sidebar_controls.py       Kontrol sidebar
  error_messages.py         Pesan error standar Indonesia
  manual_book.py            Manual pengguna in-app
  ...                       (constants, parsers, identity_utils, app_config, dll.)
tests/
  test_regresi.py           Suite regresi 11 test (dijalankan CI)
tools/                      8 skrip diagnosis & pengembangan
setup_offline.sh            Instalasi offline Ubuntu (sekali-jalan)
install_cron.sh             Pasang cronjob autostart + keep-alive
start_analyzer.sh           Launcher Linux
Jalankan-Analyzer.bat       Launcher Windows 11 (WinPython portable)
Setup-Windows.bat           Setup dependensi Windows (sekali, butuh internet)
INSTALL_OFFLINE.md          Panduan instalasi offline Ubuntu
INSTALL_WINDOWS_PORTABLE.md Panduan portable Windows 11
UAT_RESULT.md               Hasil User Acceptance Test
cleanup_trend_db.py         Utilitas pembersihan DB tren
inspect_status_db.py        Utilitas inspeksi DB status
inspect_trend_db.py         Utilitas inspeksi DB tren
```

## Alur Kerja

```
Upload CSV → Validasi → Parsing/Normalisasi → Identity Key (vCenter+UUID)
  → Analisis Zombie → Disposal Rules → Status Tracking (SQLite)
  → Snapshot Tren → Tampilan Hasil / Export
```

Data lokal tersimpan di `data/` (`status_tracking.db`, `trend_history.db`,
`filter_settings.json`) — direktori ini diabaikan Git (lihat `.gitignore`).

## Status Pengembangan

| Fase | Status |
|------|--------|
| Fase 1 | ✅ Selesai & terverifikasi |
| Fase 2 | ✅ Selesai & terverifikasi |
| Fase 3 | ✅ Selesai & terverifikasi |
| Fase 4 — Paket portable offline (Ubuntu + Windows 11) | ✅ Selesai 30 Sep 2026 |
| Fase 5 — systemd | ⏳ Ditunda |
| Fase 6 | ✅ Selesai & terverifikasi |

UAT: 9/10 lulus penuh + UAT-10 lulus simulasi (lihat `UAT_RESULT.md`;
uji mesin offline real pending David).
CI: GitHub Actions hijau — suite regresi `tests/test_regresi.py` 11/11.

## Pengembangan

Perubahan kode dilakukan manual oleh maintainer. Setiap modul mencantumkan
PATCH NOTES di header file sebagai riwayat perubahan. Ikuti standar yang ada:
pesan error berbahasa Indonesia via `user_error()`, tanpa traceback mentah
ke user, dan satu langkah kecil per commit.

## Lisensi

Proprietary — © 2026 David. Lihat `LICENSE`.
