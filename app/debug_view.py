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
#
#  PATCH NOTES (24 Sep 2026):
#  - Parameter "hk_target_df" -> "zombie_candidates_df" dan label
#    "Kandidat HK" -> "Kandidat Zombie (evaluasi awal)". Sebelumnya
#    label ini MENYESATKAN: nilai yang ditampilkan sebenarnya adalah
#    hasil run_zombie_analysis() SEBELUM merge dengan disposal/Status
#    HK, bukan angka yang berkaitan dengan Status HK sama sekali.
#  - Ditambahkan render_identity_debug() -- memindahkan blok debug
#    Identity Key yang sebelumnya ditulis ad-hoc langsung di main.py,
#    agar seluruh kode observability terkumpul di satu modul ini
#    (konsisten dengan peran modul yang dinyatakan di docstring atas).
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



def render_pipeline_debug(active_vms, filtered_vms, zombie_candidates_df, parse_fail_counts):
    """Tampilkan info tambahan SETELAH pipeline filter/analisa jalan — untuk
    melihat cepat di tahap mana data mengecil drastis, tanpa perlu expand
    section Validasi & Sanity Check secara manual.

    PATCH: label "Kandidat Zombie" di sini merujuk pada hasil
    run_zombie_analysis() SEBELUM merge dengan disposal/Status HK --
    BUKAN angka final "Kandidat Zombie" yang muncul di Label akhir
    (yang sudah memperhitungkan Status HK Rejected). Untuk angka final,
    lihat metric "🎯 Total Kandidat Zombie" di section Validasi &
    Sanity Check.
    """
    with st.expander("🐞 Debug: Info Pipeline (Setelah Filter & Analisa)", expanded=True):
        st.write(
            f"**Aktif:** {len(active_vms)} | "
            f"**Sesuai filter konteks:** {len(filtered_vms)} | "
            f"**Kandidat Zombie (evaluasi awal, sebelum Status HK):** "
            f"{len(zombie_candidates_df)}"
        )
        if parse_fail_counts:
            st.warning(f"Kolom dengan kegagalan parse numerik: {parse_fail_counts}")
        else:
            st.write("Tidak ada kegagalan parse numerik pada kolom wajib.")



def render_identity_debug(combined_candidates):
    """
    Tampilkan tabel Identity Key mentah (Name, vCenter, UUID, Identity
    Key, Label) untuk seluruh VM pada combined_candidates -- berguna
    untuk memverifikasi tidak ada VM yang tercampur identity-nya lintas
    vCenter, atau untuk melacak VM mana yang gagal mendapat Identity
    Key valid.

    Dipindahkan dari blok ad-hoc di main.py agar seluruh kode
    observability terkumpul di modul ini.
    """
    required_columns = ["Name", "vCenter", "UUID", "Identity Key", "Label"]
    missing_columns = [
        column for column in required_columns if column not in combined_candidates.columns
    ]

    with st.expander("🐞 Debug: Identity Key", expanded=True):
        if missing_columns:
            st.error(
                f"Tidak dapat menampilkan debug Identity Key -- kolom "
                f"hilang: {missing_columns}"
            )
            return

        st.dataframe(
            combined_candidates[required_columns],
            use_container_width=True,
        )
