# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — MODULE: parsers.py
# ------------------------------------------------------------------------------
#  Lokasi   : app/parsers.py
#  Peran    : Fungsi parsing MURNI (tidak bergantung Streamlit) — konversi
#             angka string/format lokal ke float, dan ekstraksi tag kritikalitas.
#  Depends  : re, pandas
#  Dipakai  : data_loader.py, sidebar_controls.py, results_view.py
# ------------------------------------------------------------------------------
#  ATURAN EDIT:
#  - Fungsi di sini WAJIB tetap pure (tanpa import streamlit) agar bisa
#    di-unit-test terpisah tanpa menjalankan app.
#  - Jangan tambahkan side-effect (print/st.warning dsb) di modul ini.
#
#  PATCH NOTES (24 Sep 2026):
#  - BUG KRITIS DIPERBAIKI: heuristik "is_thousands" SEBELUMNYA diterapkan
#    ke SEMBARANG pemisah tunggal (titik ATAU koma) yang diikuti tepat 3
#    digit. Ini membuat nilai desimal wajar seperti "0.123" (Throughput
#    0.123 KBps) salah dibaca sebagai "0123" -> 123.0 (1000x lebih
#    besar!) -- berpotensi membuat VM zombie asli GAGAL lolos threshold
#    karena nilai metriknya membengkak keliru.
#  - FIX: titik (.) SEKARANG SELALU dianggap desimal, TIDAK PERNAH
#    dianggap pemisah ribuan pada kasus separator tunggal. Ini
#    didasarkan pada bukti kuat bahwa seluruh threshold di constants.py
#    (0.8, 2.0, 0.10, dst.) memakai konvensi titik=desimal (locale
#    US/vROps standar), sehingga TIDAK ADA nilai metrik pada project ini
#    yang secara sah memakai titik sebagai pemisah ribuan.
#  - Heuristik "is_thousands" (3-digit grouping) HANYA dipertahankan
#    untuk kasus koma tunggal, karena risiko koma-sebagai-ribuan lebih
#    umum pada file numerik hasil export tool lain (mis. Excel locale
#    Indonesia yang kadang memakai koma untuk ribuan pada angka bulat).
#  - Kasus dua pemisah sekaligus (mis. "1,234.56" atau "1.234,56") TIDAK
#    berubah -- heuristik posisi (rfind) untuk kasus ini sudah benar dan
#    tidak ambigu.
# ==============================================================================
import re
import pandas as pd



def parse_numeric_verbose(val):
    """Parse 1 nilai ke float, menangani format ribuan/desimal campuran (',' vs '.').

    Return (nilai_float, berhasil_parse: bool). berhasil_parse=False dipakai
    Validasi & Sanity Check untuk melaporkan baris yang gagal dikonversi
    (bukan diam-diam jadi 0 tanpa jejak).

    CATATAN PENTING: nilai kosong/NaN/token null ('-', 'nan', 'none')
    dikembalikan sebagai (0.0, True) -- dianggap "berhasil" secara teknis
    parsing, TAPI ini menyamakan "data tidak tersedia" dengan "confirmed
    zero usage". Untuk metrik seperti CPU/IOPS/Throughput, ini BISA
    membuat VM dengan data hilang (bukan benar-benar idle) tampak sebagai
    kandidat zombie yang sangat kuat. Ini adalah keputusan desain yang
    SUDAH ADA sebelumnya (bukan diubah pada patch ini) -- lihat catatan
    review terpisah soal apakah perilaku ini perlu dikonfirmasi ulang.
    """
    if pd.isna(val):
        return 0.0, True
    if isinstance(val, (int, float)):
        return float(val), True
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ('nan', 'none') or val_str == '-':
        return 0.0, True

    cleaned = re.sub(r'[^0-9,.\-]', '', val_str)
    if not cleaned or cleaned == '-':
        return 0.0, True

    has_comma = ',' in cleaned
    has_dot = '.' in cleaned

    if has_comma and has_dot:
        # Dua pemisah sekaligus -- posisi terakhir menentukan mana yang
        # desimal. Tidak ambigu, tidak diubah dari versi sebelumnya.
        if cleaned.rfind(',') > cleaned.rfind('.'):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    elif has_dot:
        # PATCH KRITIS: titik SELALU desimal, tidak pernah dianggap
        # pemisah ribuan pada kasus separator tunggal. Lihat catatan
        # patch di atas untuk justifikasi (locale vROps = titik desimal).
        pass  # cleaned sudah memakai titik sebagai desimal, tidak diubah.
    elif has_comma:
        # Koma tunggal -- pertahankan heuristik 3-digit grouping untuk
        # membedakan pemisah ribuan ("1,234" -> 1234) dari kemungkinan
        # locale desimal-koma ("1,23" -> 1.23).
        groups = cleaned.split(',')
        is_thousands = len(groups) > 1 and all(len(g) == 3 for g in groups[1:])
        cleaned = cleaned.replace(',', '') if is_thousands else cleaned.replace(',', '.')

    try:
        return float(cleaned), True
    except ValueError:
        return 0.0, False



def parse_numeric(val):
    """Wrapper ringkas dari parse_numeric_verbose — hanya mengambil nilainya."""
    value, _ = parse_numeric_verbose(val)
    return value



def clean_criticality_tag(tag_str):
    """Ekstrak nama kritikalitas bersih dari tag mentah, mis. 'Criticality-C_1_Low' -> 'Low'."""
    if pd.isna(tag_str):
        return "Normal"
    tag_str = str(tag_str)
    match = re.search(r'Criticality-([^\>\]\,]+)', tag_str)
    if match:
        raw_tag = match.group(1)
        cleaned = re.sub(r'^C_\d+_', '', raw_tag)
        return cleaned.replace('_', ' ').title()
    return "Normal"
