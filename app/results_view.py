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
from openpyxl.styles import Font

from error_messages import user_error
from identity_utils import (
    invalid_identity_mask,
    is_powered_off_series,
)
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

    # Kolom Justifikasi gabungan: satu kolom untuk kedua Label yang
    # disjoint (Kandidat Zombie vs Kandidat Disposal).
    if "Justifikasi" not in result.columns:
        base = (
            result["Status Justifikasi"]
            if "Status Justifikasi" in result.columns
            else ""
        )
        result["Justifikasi"] = base
        if "Justifikasi Disposal" in result.columns and "Label" in result.columns:
            disposal_rows = result["Label"] == "Kandidat Disposal"
            result.loc[disposal_rows, "Justifikasi"] = result.loc[
                disposal_rows, "Justifikasi Disposal"
            ]

    result = result.drop(
        columns=["Catatan HK"],
        errors="ignore",
    )

    # Terapkan urutan kolom user-facing (hanya memengaruhi urutan
    # tampil/export; seluruh akses kolom di aplikasi by name).
    ordered = [c for c in USER_FACING_COLUMN_ORDER if c in result.columns]
    ordered += [c for c in result.columns if c not in ordered]
    return result[ordered]



# Urutan kolom user-facing untuk export Excel (disepakati David
# 2026-10-01; revisi v4c: Kritikalitas tepat setelah State).
# Kolom "No." disisipkan terpisah di posisi 0.
# Kolom yang tidak ada (mis. tanpa file Power Off) dilewati;
# kolom tak dikenal diletakkan di belakang agar tidak hilang.
USER_FACING_COLUMN_ORDER = [
    "Name",
    "State",
    "Kritikalitas",
    "vCPU",
    "Utilization CPU (%)",
    "CPU Percentile 95%",
    "CPU|Contention (%)",
    "Memory (GB)",
    "Utilization Memory (%)",
    "Memory Percentile 95%",
    "Provisioned Space (GB)",
    "Provisioned Space (TB)",
    "Used Space (GB)",
    "Used Space (TB)",
    "Utilization Disk (%)",
    "Virtual Disk Total Latency",
    "Storage Read Latency",
    "Storage Write Latency",
    "Avg Read IOPS",
    "Avg Write IOPS",
    "IOPS Percentile 95%",
    "Avg Read Throughput",
    "Avg Write Throughput",
    "Throughput Percentile 95%",
    "IP",
    "Guest OS",
    "vCenter",
    "Cluster",
    "Host",
    "Datastore",
    "UUID",
    "Identity Key",
    "Summary|vSphere Tag",
    "Summary|Guest Operating System|Tools Running Status",
    "Summary|Guest Operating System|Tools Version",
    "Summary|Guest Operating System|Tools Version Status",
    "Network I/O | Usage Rate (KBps) - 95th Percentile",
    "Status Idle",
    "Kualitas Data",
    "Uptime / Days",
    "Days Powered Off",
    "Skor Idle (0-100)",
    "Label",
    "Justifikasi",
    "Status HK",
    "PIC Owner",
    "Catatan",
]

# Nama bulan Indonesia untuk format tanggal evidence
# (tanpa dependensi locale OS): "1 Oktober 2026".
_BULAN_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def format_tanggal_id(tanggal):
    """Format tanggal ala Indonesia: "1 Oktober 2026"."""
    if tanggal is None:
        return ""
    if hasattr(tanggal, "strftime"):
        try:
            return (
                f"{tanggal.day} {_BULAN_ID[tanggal.month]} {tanggal.year}"
            )
        except (KeyError, AttributeError, TypeError):
            pass
    return str(tanggal)


# Kolom yang dibuang dari file export (bukan dari data internal).
# - "Power State": duplikat "State" (identik utk baris disposal, kosong utk zombie).
# - "Is Kandidat Zombie": redundan dgn "Label" di dalam scope file export.
# - "Status Justifikasi" & "Justifikasi Disposal": digantikan satu kolom
#   "Justifikasi" (dibentuk di _prepare_user_facing_dataframe).
EXPORT_DROP_COLUMNS = [
    "Power State",
    "Is Kandidat Zombie",
    "Status Justifikasi",
    "Justifikasi Disposal",
]


def _contextual_preview_columns(display_dataframe, memory_column,
                                selected_states=None):
    """Daftar kolom preview UI mengikuti PILIHAN FILTER State.

    Kolom khusus-zombie disembunyikan bila tidak ada state Powered On
    yang dipilih; kolom khusus-disposal disembunyikan bila tidak ada
    state Powered Off yang dipilih. Ditentukan dari FILTER (bukan data)
    supaya kolom tidak hilang secara mengejutkan ketika barisnya habis
    tersaring filter lain (uptime/tag/search). Kolom manual
    (PIC Owner, Status HK, Catatan) selalu tampil.
    """
    zombie_only_columns = {
        "Uptime / Days",
        "Skor Idle (0-100)",
        "CPU Percentile 95%",
        "IOPS Percentile 95%",
        "Throughput Percentile 95%",
        "Network I/O | Usage Rate (KBps) - 95th Percentile",
    }
    # "Justifikasi" adalah kolom universal (isinya mengikuti Label),
    # jadi tampil di kedua konteks filter.
    if memory_column:
        zombie_only_columns.add(memory_column)
    disposal_only_columns = {"Days Powered Off"}

    # selected_states tidak pernah kosong di titik ini (main.py st.stop
    # bila kosong); default aman = tampilkan semua kolom.
    if not selected_states:
        has_powered_on, has_powered_off = True, True
    else:
        state_frame = pd.DataFrame({"State": list(selected_states)})
        off_mask = is_powered_off_series(state_frame)
        has_powered_off = bool(off_mask.any())
        has_powered_on = bool((~off_mask).any())

    ordered_columns = [
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
        "Justifikasi",
        "PIC Owner",
        "Status HK",
        "Catatan",
    ]
    return [
        column
        for column in ordered_columns
        if column in display_dataframe.columns
        and (column not in zombie_only_columns or has_powered_on)
        and (column not in disposal_only_columns or has_powered_off)
    ]



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
    selected_states=None,
):
    st.markdown(
        "### 📋 Hasil Keputusan & Analisis Master VM"
    )

    # Cap waktu evidence: kapan data ini dianalisis.
    tanggal_str = format_tanggal_id(tanggal_proses)
    if tanggal_str:
        st.caption(f"🗓️ Dianalisis pada: {tanggal_str}")

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
    # Kolom preview mengikuti pilihan filter State: kolom yang tidak
    # relevan dengan state terpilih disembunyikan (mis. Days Powered Off
    # saat filter hanya Powered On).
    preview_columns = _contextual_preview_columns(
        display_dataframe,
        memory_column,
        selected_states,
    )

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
                        f"{int(changed_rows.sum())} baris berhasil disimpan.",
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
    file_name = (
        f"Master_VM_Analysis_{tanggal_proses}.xlsx"
        if tanggal_proses
        else "Master_VM_Analysis.xlsx"
    )
    # Power State & Is Kandidat Zombie dibuang dari SALINAN export saja
    # (duplikat/redundan); dataframe editor tidak berubah.
    export_dataframe = display_dataframe.drop(
        columns=EXPORT_DROP_COLUMNS,
        errors="ignore",
    )
    render_export_button(
        export_dataframe,
        file_name,
        title="Hasil Keputusan & Analisis Master VM",
        tanggal_str=tanggal_str,
    )


def build_excel_bytes(display_dataframe, title=None, tanggal_str=None):
    """Bangun bytes file Excel dari dataframe.

    Melempar Exception saat gagal (mis. openpyxl bermasalah) — penangkap
    ada di render_export_button() agar aplikasi tidak crash (HARD-06).

    Judul + tanggal analisis ditulis di atas tabel sebagai cap waktu
    evidence (dua baris pertama, lalu satu baris kosong).
    """
    buffer = io.BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl",
    ) as writer:
        sheet_name = "Master VM Analysis"
        startrow = 3 if title else 0
        display_dataframe.to_excel(
            writer,
            index=False,
            sheet_name=sheet_name,
            startrow=startrow,
        )
        if title:
            worksheet = writer.sheets[sheet_name]
            worksheet["A1"] = title
            worksheet["A1"].font = Font(bold=True, size=14)
            if tanggal_str:
                worksheet["A2"] = f"Dianalisis pada: {tanggal_str}"
                worksheet["A2"].font = Font(bold=True)

    return buffer.getvalue()


def render_export_button(
    display_dataframe, file_name, title=None, tanggal_str=None
):
    """Tampilkan tombol download Excel.

    HARD-06: kegagalan export menampilkan st.error berbahasa Indonesia
    (bukan crash); user diberi tahu apa yang bisa dilakukan.
    """
    try:
        excel_bytes = build_excel_bytes(
            display_dataframe, title=title, tanggal_str=tanggal_str
        )
    except Exception as error:
        st.error(
            user_error(
                "Gagal menyiapkan file Excel untuk diunduh",
                f"kesalahan teknis ({error})",
                "tutup file Excel hasil unduhan sebelumnya yang masih "
                "terbuka, lalu coba lagi",
            )
        )
        return

    st.download_button(
        label="📥 Download Excel Master VM",
        data=excel_bytes,
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
