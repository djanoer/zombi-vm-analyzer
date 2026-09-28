# Zombie VM Analyzer v4.0

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

- Python 3.13
- Ubuntu x86_64 (target deployment)
- Dependensi: `streamlit`, `pandas`, `openpyxl` (lihat `requirements.txt`)

> Catatan: aplikasi ini tool lokal single-user tanpa autentikasi. Jangan ekspos langsung ke jaringan publik tanpa lapisan keamanan tambahan.

## Instalasi & Menjalankan

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
app/                  Modul aplikasi (±7.300 baris, 17 modul)
  main.py             Entry point — alur utama Streamlit
  analysis.py         Business rule analisis zombie
  data_loader.py      Ingest & validasi CSV
  status_tracking.py  Persistensi status disposal (SQLite)
  trend_analysis.py   Snapshot & analisis tren (SQLite)
  results_view.py     Tampilan hasil analisis
  trend_view.py       Tampilan tren
  sidebar_controls.py Kontrol sidebar
  error_messages.py   Pesan error standar Indonesia
  manual_book.py      Manual pengguna in-app
  ...                 (constants, parsers, identity_utils, app_config, dll.)
tools/                8 skrip diagnosis & pengembangan
cleanup_trend_db.py   Utilitas pembersihan DB tren
inspect_status_db.py  Utilitas inspeksi DB status
inspect_trend_db.py   Utilitas inspeksi DB tren
UAT_RESULT.md         Hasil User Acceptance Test
start_analyzer.bat    Launcher Windows
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
| Fase 4 — Paket portable offline | ⏳ Pending |
| Fase 5 — systemd | ⏳ Pending (ditunda) |
| Fase 6 | ✅ Selesai & terverifikasi |

UAT: 9/10 lulus (lihat `UAT_RESULT.md`; UAT-10 menunggu Fase 4).

## Pengembangan

Perubahan kode dilakukan manual oleh maintainer. Setiap modul mencantumkan
PATCH NOTES di header file sebagai riwayat perubahan. Ikuti standar yang ada:
pesan error berbahasa Indonesia via `user_error()`, tanpa traceback mentah
ke user, dan satu langkah kecil per commit.
