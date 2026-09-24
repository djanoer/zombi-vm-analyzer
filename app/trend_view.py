# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: trend_view.py
# ------------------------------------------------------------------------------
# PATCH NOTES (24 Sep 2026):
# - Kolom "UUID" DIHAPUS dari tampilan tabel (display_columns) untuk
#   konsistensi dengan results_view.py -- HANYA perubahan tampilan UI.
#   UUID tetap ikut ke file export Excel (export_columns TIDAK diubah).
# - Kolom "vCenter" TETAP tampil.
# ==============================================================================


import io


import pandas as pd
import streamlit as st


from constants import (
    TREND_METRIC_WINDOW_DEFAULT,
    TREND_SNAPSHOT_SOURCE_DEFAULT,
)
from trend_analysis import (
    compute_consistent_idle_vms,
    count_recorded_observations,
)
from error_messages import user_error



def _ensure_trend_columns(dataframe):
    result = dataframe.copy()

    defaults = {
        "Nama VM": "",
        "vCenter": "",
        "UUID": "",
        "Identity Key": "",
        "PIC Owner": "",
        "Status HK": "",
        "Jumlah Observasi Kandidat Berturut-turut": 0,
        "Total Observasi": 0,
        "Observasi Pertama": "",
        "Observasi Terakhir": "",
        "Jeda Observasi Maksimum (Hari)": None,
        "Skor Idle Terakhir": 0.0,
        "Relative Period": TREND_METRIC_WINDOW_DEFAULT,
        "Sumber Snapshot": TREND_SNAPSHOT_SOURCE_DEFAULT,
    }

    for column, default_value in defaults.items():
        if column not in result.columns:
            result[column] = default_value

    return result



def render_trend_section(
    min_periods,
    tanggal_proses,
    record_success,
    record_error,
):
    st.write("---")
    st.write("### 📈 Analisis Tren Observasi Aktual")

    if record_success:
        st.success(
            f"✅ Observasi **{tanggal_proses}** "
            "berhasil direkam ke riwayat trend."
        )
    else:
        st.error(
            user_error(
                f"Gagal merekam observasi {tanggal_proses} ke riwayat trend",
                record_error,
                "coba ulangi; histori trend mungkin belum lengkap "
                "untuk tanggal ini",
            )
        )

    total_observations = count_recorded_observations()

    st.caption(
        f"Total tanggal observasi yang tercatat: "
        f"**{total_observations}**. "
        f"Minimum observasi kandidat berturut-turut: "
        f"**{min_periods}**."
    )

    if total_observations < min_periods:
        st.info(
            f"ℹ️ Belum cukup observasi "
            f"({total_observations}/{min_periods}) "
            "untuk mendeteksi VM yang konsisten menjadi kandidat."
        )
        return

    consistent_dataframe = compute_consistent_idle_vms(
        min_periods
    )

    if consistent_dataframe.empty:
        st.success(
            "Tidak ada VM yang memenuhi minimum observasi "
            "kandidat berturut-turut saat ini."
        )
        return

    consistent_dataframe = _ensure_trend_columns(
        consistent_dataframe
    )

    total_consistent = len(consistent_dataframe)

    st.warning(
        f"⚠️ Ditemukan **{total_consistent} VM** "
        f"yang terdeteksi sebagai kandidat pada "
        f"{min_periods}+ observasi aktual terbaru."
    )

    st.metric(
        label="🚨 Total VM Prioritas Review",
        value=f"{total_consistent} VM",
    )

    max_streak = max(
        1,
        int(
            consistent_dataframe[
                "Jumlah Observasi Kandidat Berturut-turut"
            ].max()
        ),
    )

    # PATCH: "UUID" DIHAPUS dari display_columns (tampilan tabel saja).
    # UUID tetap ada di consistent_dataframe & tetap ikut export_columns
    # di bagian bawah fungsi ini.
    display_columns = [
        "Nama VM",
        "vCenter",
        "PIC Owner",
        "Status HK",
        "Jumlah Observasi Kandidat Berturut-turut",
        "Total Observasi",
        "Observasi Pertama",
        "Observasi Terakhir",
        "Jeda Observasi Maksimum (Hari)",
        "Skor Idle Terakhir",
        "Relative Period",
        "Sumber Snapshot",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in consistent_dataframe.columns
    ]

    st.dataframe(
        consistent_dataframe[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "vCenter": st.column_config.TextColumn(
                "vCenter",
                help="vCenter sumber VM.",
                width="small",
            ),
            "Jumlah Observasi Kandidat Berturut-turut": (
                st.column_config.ProgressColumn(
                    "Observasi Kandidat Berturut-turut",
                    help=(
                        "Jumlah observasi aktual terbaru "
                        "yang berturut-turut menjadi kandidat."
                    ),
                    format="%d observasi",
                    min_value=0,
                    max_value=max_streak,
                )
            ),
            "Total Observasi": st.column_config.NumberColumn(
                "Total Observasi",
                format="%d",
            ),
            "Jeda Observasi Maksimum (Hari)": (
                st.column_config.NumberColumn(
                    "Jeda Maksimum",
                    help=(
                        "Jeda terbesar antarobservasi "
                        "yang tercatat untuk VM."
                    ),
                    format="%d hari",
                )
            ),
            "Skor Idle Terakhir": st.column_config.NumberColumn(
                "Skor Idle Terakhir",
                format="%.2f",
            ),
            "Relative Period": st.column_config.TextColumn(
                "Relative Period",
                help=(
                    "Rentang tanggal relatif yang digunakan "
                    "pada export vROps."
                ),
                width="medium",
            ),
            "Sumber Snapshot": st.column_config.TextColumn(
                "Sumber Snapshot",
                width="small",
            ),
            "Observasi Pertama": st.column_config.TextColumn(
                "Observasi Pertama",
                width="small",
            ),
            "Observasi Terakhir": st.column_config.TextColumn(
                "Observasi Terakhir",
                width="small",
            ),
            "PIC Owner": st.column_config.TextColumn(
                "PIC Owner",
                width="medium",
            ),
            "Status HK": st.column_config.TextColumn(
                "Status HK",
                width="medium",
            ),
        },
    )

    st.caption(
        "Definisi: trend dihitung dari observasi aktual yang "
        "benar-benar tercatat. Interval antaranalisis dapat "
        "berbeda karena sistem berjalan manual. Tanggal yang "
        "tidak dianalisis tidak dibuat sebagai record dan "
        "tidak dianggap sebagai non-kandidat. Relative Period "
        f"yang digunakan: {TREND_METRIC_WINDOW_DEFAULT}. "
        "Kolom UUID tersedia pada file export Excel di bawah "
        "untuk keperluan audit."
    )

    # Export TETAP menyertakan UUID dan Identity Key -- hanya TAMPILAN
    # tabel di atas yang menyembunyikan UUID.
    export_columns = [
        "Identity Key",
        "vCenter",
        "UUID",
        "Nama VM",
        "PIC Owner",
        "Status HK",
        "Jumlah Observasi Kandidat Berturut-turut",
        "Total Observasi",
        "Observasi Pertama",
        "Observasi Terakhir",
        "Jeda Observasi Maksimum (Hari)",
        "Skor Idle Terakhir",
        "Relative Period",
        "Sumber Snapshot",
    ]

    export_columns = [
        column
        for column in export_columns
        if column in consistent_dataframe.columns
    ]

    export_dataframe = consistent_dataframe[
        export_columns
    ].copy()

    buffer = io.BytesIO()

    file_name = (
        f"Tren_VM_Observasi_Aktual_{tanggal_proses}.xlsx"
        if tanggal_proses
        else "Tren_VM_Observasi_Aktual.xlsx"
    )

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl",
    ) as writer:
        export_dataframe.to_excel(
            writer,
            index=False,
            sheet_name="Trend Observasi Aktual",
        )

    st.download_button(
        label="📥 Download Data Trend (Excel)",
        data=buffer.getvalue(),
        file_name=file_name,
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        help=(
            "Ekspor daftar VM prioritas beserta UUID, "
            "vCenter, Identity Key, dan evidence trend "
            "observasi aktual."
        ),
    )
