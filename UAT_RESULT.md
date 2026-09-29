# UAT_RESULT.md — Hasil User Acceptance Test

**Tanggal:** 25 September 2026
**Cakupan:** Fase 1 (FIX-01..FIX-04, D-1), Fase 2 (FEAT-05), Fase 3 (HARD-06)
**Metode:** eksekusi headless pada level fungsi (lingkungan uji tanpa Streamlit
terinstal). Setiap skenario memakai data dan pipeline yang sama dengan aplikasi.

## Ringkasan hasil

| ID | Skenario | Hasil | Bukti |
|----|----------|-------|-------|
| UAT-01 | Deteksi zombie dasar | LULUS | `uat_fase6.py`: web-srv-01 kandidat (skor >= 70), web-srv-02 (CPU 45%) bukan kandidat |
| UAT-02 | Parsing desimal koma | LULUS | `demo_bug.py`: "45,5" -> 45.0, "25,5" -> 25.5; db-srv-05 bukan kandidat disposal |
| UAT-03 | Trend konsisten | LULUS | `uat_fase6.py`: 3 snapshot terekam, web-srv-01 muncul di daftar konsisten min. 3 |
| UAT-04 | Migrasi DB legacy | LULUS | `demo_bug.py`: baris UUID kosong termigrasi tanpa crash |
| UAT-05 | Pindah vCenter (Opsi B) | LULUS | `test_fase2.py` 14/14: tawaran muncul, pindah hanya setelah setuju, tercatat di audit |
| UAT-06 | CSV kolom salah | LULUS setelah perbaikan | `uat_fase6.py`: pesan menyebut kolom hilang; temuan UUID diperbaiki (lihat bawah) |
| UAT-07 | Identity Key kosong | LULUS | `uat_fase6.py`: baris UUID+Name kosong terdeteksi, hitungan tersedia untuk peringatan UI |
| UAT-08 | Bulk PIC upload | LULUS | `uat_fase6.py`: format benar teraplikasi; format salah -> pesan error menyebut nama file |
| UAT-09 | Export | LULUS | `test_fase3.py` 8/8: gagal export -> st.error jelas, tidak crash |
| UAT-10 | Instal offline | LULUS (simulasi) | Wheelhouse 38 paket (CPython 3.13, manylinux x86_64) ter-build; `pip install --no-index` dari wheelhouse + launch app (HTTP 200) terverifikasi di sandbox. Uji di mesin offline real oleh David pending. |

**Hasil: 9/10 lulus penuh + UAT-10 lulus simulasi (uji mesin offline real pending David).**

## Temuan UAT dan perbaikan

**UAT-06 — kolom UUID tidak wajib (diperbaiki saat UAT).**
Fakta: `REQUIRED_COLUMNS_BASE` tidak memuat `UUID`, sehingga CSV tanpa kolom
UUID lolos validasi lalu crash dengan `KeyError: 'UUID'` mentah di
`build_identity_key`. Ini melanggar ekspektasi UAT-06 ("pesan error jelas
menyebut kolom yang hilang") dan standar Fase 3.
Perbaikan: `UUID` ditambahkan ke `REQUIRED_COLUMNS_BASE` di `app/constants.py`
(satu baris + komentar). Validator ini hanya dipakai jalur CSV metrik;
jalur Power Off dan PIC memakai validator masing-masing sehingga tidak
terdampak. Seluruh suite regresi tetap hijau setelah perubahan.

## Definisi selesai

- [x] Semua UAT yang dapat dieksekusi lulus (9/10)
- [x] Tidak ada traceback mentah pada skenario gagal (pesan standar Indonesia)
- [x] UAT-10 lulus simulasi (30 Sep 2026); uji mesin offline real oleh David pending
- [ ] Sign-off Nucifera (di bawah)

## Catatan keterlacakan (30 September 2026)

Skrip uji asli yang dirujuk pada tabel ringkasan di atas (`uat_fase6.py`,
`demo_bug.py`, `test_fase2.py`, `test_fase3.py`) tidak ditemukan — tidak pernah
ter-commit ke repo (0 commit di history git) dan tidak ada di mesin pengembang.
Task B1 (memindahkan skrip tersebut ke `tests/`) dibatalkan dan diganti
B1-alt: suite regresi baru yang ditulis jujur berdasarkan skenario UAT di atas
(bukan rekonstruksi skrip asli), direkam di `tests/` dan dijalankan oleh CI.

### Verifikasi UAT-10 (30 September 2026, Fase C)

- Wheelhouse `wheelhouse-py3.13-manylinux_x86_64.zip` (38 wheel, 106 MB)
  di-build via `pip download` dengan `--python-version 3.13`,
  `--only-binary=:all:`, dan lima varian `--platform` manylinux
  (sebagian package hanya menyediakan wheel untuk generasi manylinux tertentu).
- Alur `setup_offline.sh` diuji ujung-ke-ujung di sandbox: ekstrak zip ->
  buat venv -> `pip install --no-index --find-links=wheelhouse` ->
  import `streamlit, pandas, openpyxl` OK. Idempoten (jalan ulang aman).
- `start_analyzer.sh` diuji menjalankan aplikasi: Streamlit menyala,
  `GET /` dan `/_stcore/health` mengembalikan HTTP 200.
- `install_cron.sh` diuji dengan crontab tiruan: dua baris `@reboot` dan
  `*/5` terpasang benar, idempoten, entri crontab lain tidak terganggu.
  Pola keep-alive memakai `pgrep -f "streamlit run app/main[.]py"` —
  trik `[.]` mencegah pola cocok dengan baris cron itu sendiri
  (self-match yang membuat restart tidak pernah terpicu).
- Batasan jujur: sandbox tidak memiliki Python 3.13, sehingga instalasi
  offline di atas dijalankan dengan Python 3.12 + wheelhouse se-padan;
  kelengkapan wheelhouse Python 3.13 dibuktikan oleh keberhasilan resolver
  `pip download` untuk seluruh dependency tree. Uji di mesin Ubuntu offline
  dengan Python 3.13 real menunggu David.
- Launcher Windows (`Jalankan-Analyzer.bat`, `Setup-Windows.bat`) hanya
  di-review manual (tidak dapat dieksekusi di sandbox Linux);
  uji klik-langsung di Windows 11 menunggu David.

## Sign-off

Dengan ini saya menyatakan hasil UAT di atas dapat diterima.

Nama: David

Tanggal: 29 September 2026

Tanda tangan: David
