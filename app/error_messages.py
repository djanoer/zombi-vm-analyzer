# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: error_messages.py
# ------------------------------------------------------------------------------
# PATCH NOTES (25 Sep 2026):
# - Modul baru untuk Fase 3 (HARD-06): format pesan error standar berbahasa
#   Indonesia. Setiap pesan menyebut tiga hal: APA yang gagal, PENYEBAB
#   yang mungkin, dan TINDAKAN yang bisa dilakukan user. Fungsi murni
#   (tanpa dependensi streamlit) agar mudah diuji.
# ==============================================================================
"""
Helper format pesan error standar (Fase 3 — Hardening).

Standar pesan error yang disepakati:
- st.error() berbahasa Indonesia.
- Menyebut: apa yang gagal, penyebab, dan tindakan user.
- Tanpa traceback mentah ke user.
"""


def user_error(apa, penyebab, tindakan):
    """
    Susun pesan error standar berbahasa Indonesia.

    Parameter:
        apa: apa yang gagal (mis. "Gagal membaca file CSV 'data.csv'").
        penyebab: kemungkinan penyebab (mis. "kolom 'UUID' tidak ditemukan").
        tindakan: apa yang harus dilakukan user
            (mis. "periksa kembali format CSV lalu upload ulang").

    Mengembalikan string siap tampil via st.error().
    """
    parts = [f"❌ {apa}."]
    if penyebab:
        parts.append(f"Kemungkinan penyebab: {penyebab}.")
    if tindakan:
        parts.append(f"Tindakan: {tindakan}.")
    return " ".join(parts)
