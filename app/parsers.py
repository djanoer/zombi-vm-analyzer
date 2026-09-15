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
# ==============================================================================
import re
import pandas as pd


def parse_numeric_verbose(val):
    """Parse 1 nilai ke float, menangani format ribuan/desimal campuran (',' vs '.').

    Return (nilai_float, berhasil_parse: bool). berhasil_parse=False dipakai
    Validasi & Sanity Check untuk melaporkan baris yang gagal dikonversi
    (bukan diam-diam jadi 0 tanpa jejak).
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
        if cleaned.rfind(',') > cleaned.rfind('.'):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    elif has_comma or has_dot:
        sep = ',' if has_comma else '.'
        groups = cleaned.split(sep)
        is_thousands = len(groups) > 1 and all(len(g) == 3 for g in groups[1:])
        cleaned = cleaned.replace(sep, '') if is_thousands else cleaned.replace(sep, '.')

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
