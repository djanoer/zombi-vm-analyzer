# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: results_view.py
# ------------------------------------------------------------------------------
# PATCH NOTES (24 Sep 2026):
# - UUID hanya disembunyikan dari tampilan tabel UI; tetap dipertahankan
#   untuk validasi identity, status/PIC, dan export audit.
# - vCenter tetap tampil pada tabel UI.
# - Catatan HK dihapus dari dataframe user-facing dan export Excel.
#   Catatan menjadi satu-satunya kolom catatan yang dipakai user.
# - Dukungan legacy tetap dipertahankan: jika Catatan tidak tersedia
#   tetapi Catatan HK ada, Catatan diisi dari Catatan HK sebelum kolom
#   legacy tersebut dihapus dari UI/export.
# - Export tetap hanya menerima kandidat aktif dari main.py:
#   Kandidat Zombie dan Kandidat Disposal.
# ==============================================================================


import io

import pandas as pd
import streamlit as st

from identity_utils import invalid_identity_mask
from status_tracking import (
    VALID_STATUSES,
    save_status_updates,
)



def _ensure_columns(dataframe):
    result = dataframe.copy()

    if "Status HK" not in result.columns:
        result["Status HK"] = "Need Confirm"

    if "Catatan" not in result.columns:
        result["Catatan"] = ""

    if "PIC Owner" not in result.columns:
        result["PIC Owner"] = ""

    return result



def _prepare_user_facing_dataframe(dataframe):
    """
    Bentuk dataframe yang dipakai UI dan export.

    Catatan HK adalah nama legacy/internal. Catatan adalah nama final
    user-facing. Jika hanya Catatan HK tersedia, nilainya dipindahkan
    ke Catatan terlebih dahulu. Setelah itu Catatan HK selalu dibuang
    dari dataframe user-facing dan export.
    """
    result = dataframe.copy()

    if "Catatan" not in result.columns:
        if "Catatan HK" in result.columns:
            result["Catatan"] = result["Catatan HK"]
        else:
            result["Catatan"] = ""

    return result.drop(
        columns=["Catatan HK"],
        errors="ignore",
    )



def render_validation_section(
    raw_dataframe,
    active_vms,
    combined_candidates,
    memory_column,
    parse_fail_counts,
    max_cpu,
    max_iops,
    max_throughput,
    max_network,
    min_off_days,
    min_uptime=0,
    max_uptime=0,
    total_in_table=None,
    total_zombie=None,
    total_disposal=None,
    est_vcpu=0,
    est_mem_gb=0,
    est_storage_gb=0,
    est_storage_tb=0,
):
    with st.expander(
        "🔎 Validasi & Sanity Check Analisa",
        expanded=True,
    ):
        st.markdown(
            "### 📊 Ringkasan Pemrosesan Data "
            "(Relevan dengan Tabel)"
        )

        if total_in_table is not None:
            total_di_tabel = total_in_table
            total_zombie_count = total_zombie
            total_disposal_count = total_disposal
        else:
            total_di_tabel = len(combined_candidates)
            total_zombie_count = len(
                combined_candidates[
                    combined_candidates["Label"] == "Kandidat Zombie"
                ]
            )
            total_disposal_count = len(
                combined_candidates[
                    combined_candidates["Label"] == "Kandidat Disposal"
                ]
            )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total VM Master", len(raw_dataframe))
        col2.metric("VM Lolos Filter", total_di_tabel)
        col3.metric("🎯 Total Kandidat Zombie", total_zombie_count)
        col4.metric("🗑️ Total Kandidat Disposal", total_disposal_count)

        st.markdown("---")
        st.markdown(
            "### 💎 Potensi Penghematan Resource (Reclaimable)"
        )

        r_col1, r_col2, r_col3 = st.columns(3)

        r_col1.metric("Total vCPU", f"{int(est_vcpu):,} Core")
        r_col2.metric("Total Memory", f"{int(est_mem_gb):,} GB")

        if est_storage_tb > 0:
            r_col3.metric("Total Storage", f"{est_storage_tb:,.2f} TB")
        else:
            r_col3.metric("Total Storage", f"{int(est_storage_gb):,} GB")

        st.markdown("---")

        col_detail1, col_detail2, col_detail3 = st.columns(3)

        with col_detail1:
            st.markdown("**⚙️ Ambang Batas (Threshold)**")
            st.write(
                f"- **Uptime Target:** {min_uptime} sd {max_uptime} hari"
            )
            st.write(
                f"- **Disposal:** > {min_off_days} hari Power Off"
            )
            st.write(f"- **Zombie CPU:** <= {max_cpu}%")
            st.write(f"- **Zombie IOPS:** <= {max_iops}")
            st.write(
                f"- **Zombie Throughput:** <= {max_throughput}"
            )
            st.write(
                f"- **Zombie Network:** <= {max_network} KBps"
            )

        with col_detail2:
            st.markdown("**ℹ️ Filter & Penyusutan Data**")
            st.write(
                f"- Membuang **{len(raw_dataframe) - len(active_vms)} VM** "
                "yang di luar status (State) sidebar."
            )
            st.write(
                f"- Membuang **{len(active_vms) - total_di_tabel} VM** "
                "akibat filter target Uptime / Tag."
            )

        with col_detail3:
            st.markdown("**⚠️ Catatan Parsing Numerik**")
            st.write(
                f"Kolom Memory Utama: `{memory_column}`"
            )

            if parse_fail_counts:
                st.write(
                    "Sistem mendeteksi nilai tidak terbaca "
                    "(dianggap 0):"
                )
                st.json(parse_fail_counts)
            else:
                st.success(
                    "✅ Seluruh angka berhasil dikonversi."
                )



def render_results_section(
    combined_candidates,
    memory_column,
    updated_by,
    tanggal_proses=None,
):
    st.markdown(
        "### 📋 Hasil Keputusan & Analisis Master VM"
    )

    if combined_candidates.empty:
        st.info(
            "Tidak ada VM yang memenuhi kriteria filter saat ini."
        )
        return

    # Satu dataframe ini dipakai sebagai sumber UI, editor, dan export.
    # Karena sudah dibersihkan di sini, Catatan HK tidak mungkin masuk
    # kembali ke export melalui display_dataframe.to_excel().
    display_dataframe = _prepare_user_facing_dataframe(
        _ensure_columns(combined_candidates)
    )

    if "No." in display_dataframe.columns:
        display_dataframe = display_dataframe.drop(
            columns=["No."]
        )

    display_dataframe.insert(
        0,
        "No.",
        range(1, len(display_dataframe) + 1),
    )

    # UUID tetap wajib ada di DATA internal meskipun tidak ditampilkan.
    for required_column in [
        "UUID",
        "vCenter",
        "Identity Key",
    ]:
        if required_column not in display_dataframe.columns:
            raise ValueError(
                f"Kolom '{required_column}' wajib tersedia untuk "
                "penyimpanan status dan PIC yang aman lintas-vCenter."
            )

    identity_series = (
        display_dataframe["Identity Key"]
        .astype("string")
        .str.strip()
    )

    invalid_mask = invalid_identity_mask(identity_series)
    if invalid_mask.any():
        raise ValueError(
            f"Ditemukan {int(invalid_mask.sum())} baris dengan "
            "Identity Key kosong/tidak valid pada tabel hasil."
        )

    if identity_series.duplicated().any():
        duplicate_keys = identity_series[
            identity_series.duplicated()
        ].tolist()
        raise ValueError(
            "Ditemukan Identity Key duplikat pada tabel hasil: "
            f"{duplicate_keys}"
        )

    # UUID sengaja tidak dimasukkan ke preview UI.
    preview_columns = [
        "No.",
        "Name",
        "vCenter",
        "Kritikalitas",
        "State",
        "Uptime / Days",
        "Days Powered Off",
        "Label",
        "Skor Idle (0-100)",
        "CPU Percentile 95%",
        "IOPS Percentile 95%",
        "Throughput Percentile 95%",
        memory_column,
        "Network I/O | Usage Rate (KBps) - 95th Percentile",
        "Status Justifikasi",
        "PIC Owner",
        "Status HK",
        "Catatan",
    ]

    preview_columns = [
        column
        for column in preview_columns
        if column in display_dataframe.columns
    ]

    editor_dataframe = display_dataframe[
        preview_columns
    ].copy()

    # Identity Key adalah row-key internal editor dan tidak ditampilkan.
    editor_dataframe.index = identity_series

    st.markdown(
        "Gunakan tabel di bawah ini untuk meninjau justifikasi setiap VM. "
        "Anda dapat mengubah `PIC Owner`, `Status HK`, dan `Catatan` "
        "langsung pada tabel. Kolom `vCenter` ditampilkan sebagai "
        "referensi identitas VM; kolom `UUID` tersedia pada file export "
        "Excel untuk keperluan audit."
    )

    editable_columns = [
        "PIC Owner",
        "Status HK",
        "Catatan",
    ]

    disabled_columns = [
        column
        for column in preview_columns
        if column not in editable_columns
    ]

    edited_dataframe = st.data_editor(
        editor_dataframe,
        hide_index=True,
        column_config={
            "No.": st.column_config.NumberColumn(
                "No.",
                width="small",
            ),
            "vCenter": st.column_config.TextColumn(
                "vCenter",
                help="vCenter sumber VM (VC01/VC02/dst).",
                width="small",
            ),
            "PIC Owner": st.column_config.TextColumn(
                "PIC Owner",
                help="Nama, Tim, atau Email pemilik VM",
                width="medium",
            ),
            "Status HK": st.column_config.SelectboxColumn(
                "Status HK",
                help="Status tindak lanjut housekeeping",
                width="medium",
                options=VALID_STATUSES,
                required=True,
            ),
            "Catatan": st.column_config.TextColumn(
                "Catatan",
                help="Catatan/alasan tambahan",
                width="large",
            ),
            "Skor Idle (0-100)": st.column_config.NumberColumn(
                "Skor Idle",
                format="%.2f",
            ),
        },
        use_container_width=True,
        disabled=disabled_columns,
        key="master_vm_editor",
    )

    if st.button(
        "💾 Simpan Perubahan",
        type="primary",
    ):
        if not updated_by or updated_by.strip() == "":
            st.toast(
                "⚠️ Masukkan nama/identitas Anda pada sidebar "
                "sebelum menyimpan perubahan.",
                icon="⚠️",
            )
        else:
            comparison_columns = [
                "Status HK",
                "Catatan",
                "PIC Owner",
            ]

            original_values = (
                display_dataframe[
                    ["Identity Key"] + comparison_columns
                ]
                .copy()
            )

            original_values["Identity Key"] = (
                original_values["Identity Key"]
                .astype("string")
                .str.strip()
            )

            original_values = (
                original_values
                .set_index("Identity Key")
                [comparison_columns]
                .fillna("")
                .astype(str)
            )

            edited_values = (
                edited_dataframe[comparison_columns]
                .fillna("")
                .astype(str)
            )

            original_values = original_values.reindex(
                edited_values.index
            )

            changed_rows = edited_values.ne(
                original_values
            ).any(axis=1)

            if not changed_rows.any():
                st.toast(
                    "Tidak ada perubahan untuk disimpan.",
                    icon="ℹ️",
                )
            else:
                original_for_save = display_dataframe.copy()

                edited_for_save = edited_dataframe.copy()
                edited_for_save.insert(
                    0,
                    "Identity Key",
                    edited_for_save.index.astype(str),
                )
                edited_for_save = edited_for_save.reset_index(
                    drop=True
                )

                saved_count = save_status_updates(
                    original_for_save,
                    edited_for_save,
                    updated_by,
                )

                if saved_count > 0:
                    st.toast(
                        f"{saved_count} perubahan berhasil disimpan.",
                        icon="✅",
                    )
                    st.rerun()
                else:
                    st.toast(
                        "Tidak ada perubahan yang berhasil disimpan.",
                        icon="⚠️",
                    )

    # Export memakai display_dataframe yang sudah dibersihkan.
    # Karena Catatan HK sudah dibuang oleh _prepare_user_facing_dataframe(),
    # kolom legacy tersebut tidak akan muncul di Excel.
    buffer = io.BytesIO()

    file_name = (
        f"Master_VM_Analysis_{tanggal_proses}.xlsx"
        if tanggal_proses
        else "Master_VM_Analysis.xlsx"
    )

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl",
    ) as writer:
        display_dataframe.to_excel(
            writer,
            index=False,
            sheet_name="Master VM Analysis",
        )

    st.download_button(
        label="📥 Download Excel Master VM",
        data=buffer.getvalue(),
        file_name=file_name,
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        help=(
            "Download keseluruhan data kandidat aktif, termasuk UUID, "
            "Identity Key, dan kolom yang tidak tampil di preview. "
            "Kolom Catatan HK legacy tidak disertakan."
        ),
    )
