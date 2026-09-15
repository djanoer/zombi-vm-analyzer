# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — MODULE: debug_view.py
# ------------------------------------------------------------------------------
#  Lokasi   : app/debug_view.py
#  Peran    : Rendering info teknis tambahan saat "🐞 Mode Debug" aktif di
#             sidebar — daftar kolom terdeteksi, dtype, jumlah baris, dan
#             preview data mentah. Tujuan: begitu ada CSV yang gagal ter-parse
#             benar (mis. kasus delimiter salah, 13 Sep 2026), masalahnya
#             langsung kelihatan di sini TANPA harus menebak-nebak dari pesan
#             error yang lebih generik di step berikutnya.
#  Depends  : streamlit, pandas
#  Dipakai  : main.py
# ------------------------------------------------------------------------------
#  ATURAN EDIT:
#  - Modul ini HANYA untuk observability/debugging — tidak ada logika
#    keputusan zombie atau transformasi data permanen di sini.
# ==============================================================================
import streamlit as st


def render_raw_data_debug(raw_df, mem_col):
    """Tampilkan info mentah SEBELUM filter/analisa — dipanggil tepat setelah
    load_and_merge_uploads() berhasil, jadi kelihatan persis apa yang terbaca
    dari CSV sebelum diproses lebih lanjut."""
    with st.expander("🐞 Debug: Info Kolom & Data Mentah (Sebelum Filter)", expanded=True):
        st.write(f"**Jumlah baris:** {len(raw_df)} | **Jumlah kolom terdeteksi:** {len(raw_df.columns)}")
        st.write(f"**Kolom Memory P95 yang dipakai:** `{mem_col}`")

        st.markdown("**Daftar kolom terdeteksi:**")
        st.code(", ".join(raw_df.columns.tolist()))

        st.markdown("**Dtype per kolom:**")
        st.dataframe(raw_df.dtypes.astype(str).rename("dtype"), use_container_width=True)

        st.markdown("**Preview 3 baris pertama (data mentah, sebelum parsing numerik):**")
        st.dataframe(raw_df.head(3), use_container_width=True)


def render_pipeline_debug(active_vms, filtered_vms, hk_target_df, parse_fail_counts):
    """Tampilkan info tambahan SETELAH pipeline filter/analisa jalan — untuk
    melihat cepat di tahap mana data mengecil drastis, tanpa perlu expand
    section Validasi & Sanity Check secara manual."""
    with st.expander("🐞 Debug: Info Pipeline (Setelah Filter & Analisa)", expanded=True):
        st.write(f"**Aktif:** {len(active_vms)} | **Sesuai filter konteks:** {len(filtered_vms)} | **Kandidat HK:** {len(hk_target_df)}")
        if parse_fail_counts:
            st.warning(f"Kolom dengan kegagalan parse numerik: {parse_fail_counts}")
        else:
            st.write("Tidak ada kegagalan parse numerik pada kolom wajib.")
