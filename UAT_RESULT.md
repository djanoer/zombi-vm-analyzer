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
| UAT-10 | Instal offline | PENDING | Menunggu Fase 4 (paket portable offline) |

**Hasil: 9/10 lulus, 1 pending (UAT-10).**

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
- [ ] UAT-10 menunggu Fase 4
- [ ] Sign-off Nucifera (di bawah)

## Sign-off

Dengan ini saya menyatakan hasil UAT di atas dapat diterima.

Nama: ______________________

Tanggal: ______________________

Tanda tangan: ______________________
