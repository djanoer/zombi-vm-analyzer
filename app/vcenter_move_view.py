# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: vcenter_move_view.py
# ------------------------------------------------------------------------------
# PATCH NOTES (25 Sep 2026):
# - Modul baru untuk Fase 2 (FEAT-05, Opsi B): UI konfirmasi penautan
#   histori VM yang pindah vCenter. Expander hanya muncul jika
#   detect_vcenter_moves() menemukan kandidat; setiap kandidat punya
#   tombol Setuju/Abaikan sendiri. Penolakan hanya berlaku sesi ini
#   (session_state) agar tidak mengganggu permanen.
# ==============================================================================
"""
Tampilan konfirmasi untuk VM yang terdeteksi pindah vCenter (Opsi B).

Prinsip: tidak ada pemindahan histori yang terjadi tanpa klik eksplisit
dari user. Penolakan ("Abaikan") bersifat sementara per sesi.
"""

import streamlit as st

from status_tracking import apply_identity_move, detect_vcenter_moves


_DISMISSED_KEY = "dismissed_vcenter_moves"


def _dismissed_moves():
    dismissed = st.session_state.get(_DISMISSED_KEY)
    if dismissed is None:
        dismissed = set()
        st.session_state[_DISMISSED_KEY] = dismissed
    return dismissed


def render_vcenter_move_section(dataframe, updated_by):
    """
    Render expander konfirmasi untuk kandidat VM pindah vCenter.

    Dipanggil dari main.py setelah dataframe kandidat terbentuk (sudah
    memiliki kolom Identity Key). Tidak melakukan apa pun jika tidak ada
    kandidat atau semuanya sudah diabaikan pada sesi ini.
    """
    try:
        candidates = detect_vcenter_moves(dataframe)
    except Exception as error:
        st.error(
            "❌ Gagal memeriksa perpindahan vCenter. "
            f"Penyebab: {error}. "
            "Analisis tetap berjalan tanpa pemeriksaan ini."
        )
        return

    dismissed = _dismissed_moves()
    candidates = [
        candidate
        for candidate in candidates
        if (
            candidate["uuid"],
            candidate["old_vcenter"],
            candidate["new_vcenter"],
        )
        not in dismissed
    ]

    if not candidates:
        return

    with st.expander(
        f"🔀 Terdeteksi {len(candidates)} VM pindah vCenter "
        "-- perlu konfirmasi",
        expanded=True,
    ):
        st.info(
            "UUID berikut tercatat di database pada vCenter lama, tetapi "
            "pada data aktif hanya muncul di vCenter baru. Setujui untuk "
            "memindahkan histori Status HK, PIC Owner, dan trend ke "
            "identitas baru. Penolakan tidak menghapus data apa pun."
        )

        for candidate in candidates:
            uuid_short = candidate["uuid"][:8]
            accept_key = (
                f"vcm_accept_{uuid_short}_"
                f"{candidate['old_vcenter']}_{candidate['new_vcenter']}"
            )
            dismiss_key = (
                f"vcm_dismiss_{uuid_short}_"
                f"{candidate['old_vcenter']}_{candidate['new_vcenter']}"
            )

            st.markdown(
                f"**{candidate['vm_name']}** "
                f"(`{uuid_short}...`) : "
                f"`{candidate['old_vcenter']}` → `{candidate['new_vcenter']}`"
            )

            summary_parts = []
            if candidate["status_hk"]:
                summary_parts.append(
                    f"Status HK: {candidate['status_hk']}"
                )
            if candidate["pic_owner"]:
                summary_parts.append(f"PIC: {candidate['pic_owner']}")
            summary_parts.append(
                f"{candidate['trend_count']} observasi trend"
            )
            st.caption(" | ".join(summary_parts))

            if candidate["name_changed"]:
                st.warning(
                    "⚠️ Nama VM berbeda dari catatan database. "
                    "Pastikan ini memang VM yang sama sebelum menyetujui."
                )

            action_col, dismiss_col, _ = st.columns([1, 1, 3])
            with action_col:
                if st.button("✅ Setuju pindahkan", key=accept_key):
                    if apply_identity_move(candidate, updated_by):
                        st.success(
                            f"Histori {candidate['vm_name']} dipindahkan "
                            f"ke {candidate['new_vcenter']} dan tercatat "
                            "di audit."
                        )
                        st.rerun()
            with dismiss_col:
                if st.button("Abaikan", key=dismiss_key):
                    dismissed.add(
                        (
                            candidate["uuid"],
                            candidate["old_vcenter"],
                            candidate["new_vcenter"],
                        )
                    )
                    st.rerun()

            st.divider()
