# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — MODULE: trend_view.py
# ------------------------------------------------------------------------------
#  Lokasi   : app/trend_view.py
#  Peran    : Rendering section "📈 Analisis Tren Multi-Periode" — menampilkan
#             VM yang konsisten idle >= N periode berturut-turut tanpa gap,
#             dan status rekaman periode saat ini.
#  Depends  : streamlit, trend_analysis.py
#  Dipakai  : main.py
# ------------------------------------------------------------------------------
#  ATURAN EDIT:
#  - Modul ini HANYA menampilkan hasil dari trend_analysis.py — jangan taruh
#    logika penghitungan streak/gap di sini.
#  - UPDATE (13 Sep 2026): label "(Fase 4)" dihapus dari judul section —
#    istilah fase adalah jargon internal development, tidak relevan untuk
#    tampilan yang dipakai sehari-hari.
# ==============================================================================
import streamlit as st

from trend_analysis import compute_consistent_idle_vms, count_recorded_periods


def render_trend_section(min_periods, tanggal_proses, record_success, record_error):
    st.write("---")
    st.write("### 📈 Analisis Tren Multi-Periode")

    if record_success:
        st.success(f"✅ Snapshot periode **{tanggal_proses}** berhasil direkam ke riwayat tren.")
    else:
        st.error(f"❌ Gagal merekam snapshot periode ini: {record_error}. Data tren untuk periode {tanggal_proses} mungkin tidak lengkap.")

    n_periods = count_recorded_periods()
    st.caption(f"Total periode tercatat sejauh ini: **{n_periods}**. Minimum periode dibutuhkan untuk deteksi konsistensi: **{min_periods}**.")

    if n_periods < min_periods:
        st.info(f"ℹ️ Belum cukup data periode ({n_periods}/{min_periods}) untuk mendeteksi VM yang konsisten idle. Lanjutkan analisa mingguan hingga minimum periode terpenuhi.")
        return

    consistent_df = compute_consistent_idle_vms(min_periods)

    if consistent_df.empty:
        st.success(f"Tidak ada VM yang idle {min_periods}+ periode berturut-turut tanpa gap saat ini.")
        return

    st.warning(f"⚠️ Ditemukan **{len(consistent_df)} VM** yang konsisten idle {min_periods}+ periode berturut-turut TANPA GAP — kandidat prioritas tinggi untuk Housekeeping.")
    # Tambahkan visual metric di atas tabel
    st.metric(label="🚨 Total VM Kritis (Konsisten Idle)", value=f"{len(consistent_df)} VM")

    # Ambil nilai maksimal periode untuk skala progress bar (minimal skala 12 bulan)
    max_streak = max(12, int(consistent_df["Jumlah Periode Idle Berturut-turut"].max()))

    st.dataframe(
        consistent_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            # Mengubah NumberColumn menjadi ProgressColumn yang elegan
            "Jumlah Periode Idle Berturut-turut": st.column_config.ProgressColumn(
                "Periode Berturut-turut",
                help="Visualisasi durasi idle tanpa henti",
                format="%d periode",
                min_value=0,
                max_value=max_streak,
            ),
            "Periode Terakhir": st.column_config.TextColumn("Periode Terakhir", width="small"),
        },
    )
    st.caption("Definisi: idle di SEMUA periode berturut-turut sejak periode terbaru, tanpa 1 pun periode 'tidak idle' di antaranya (gap = reset hitungan ke 0).")
