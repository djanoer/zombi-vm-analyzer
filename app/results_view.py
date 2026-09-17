# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: results_view.py
# ============================================================================


import io


import pandas as pd
import streamlit as st


from status_tracking import (
    merge_status_into_df,
    save_status_updates,
)



def _ensure_columns(dataframe):
    result = dataframe.copy()
    if "Status HK" not in result.columns:
        result["Status HK"] = "Pending"
    if "Catatan" not in result.columns:
        result["Catatan"] = ""
    return result



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
    total_with_score=None
):
    with st.expander("🔎 Validasi & Sanity Check Analisa", expanded=True):
        st.markdown("### 📊 Ringkasan Pemrosesan Data (Relevan dengan Tabel)")


        # FIX #2: Gunakan statistik yang di-pass jika tersedia, else hitung sendiri
        if total_in_table is not None:
            total_di_tabel = total_in_table
            total_zombie_count = total_zombie
            total_disposal_count = total_disposal
        else:
            total_di_tabel = len(combined_candidates)
            total_zombie_count = len(combined_candidates[combined_candidates["Label"] == "Kandidat Zombie"])
            total_disposal_count = len(combined_candidates[combined_candidates["Label"] == "Kandidat Disposal"])


        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total VM Master (CSV Asli)", len(raw_dataframe))
        col2.metric("VM Lolos Filter (Di Tabel)", total_di_tabel)
        col3.metric("🎯 Total Kandidat Zombie", total_zombie_count)
        col4.metric("🗑️ Total Kandidat Disposal", total_disposal_count)


        st.markdown("---")


        col_detail1, col_detail2, col_detail3 = st.columns(3)


        with col_detail1:
            st.markdown("**⚙️ Ambang Batas (Threshold)**")
            st.write(f"- **Uptime Target:** {min_uptime} sd {max_uptime} hari")
            st.write(f"- **Disposal:** > {min_off_days} hari Power Off")
            st.write(f"- **Zombie CPU:** <= {max_cpu}%")
            st.write(f"- **Zombie IOPS:** <= {max_iops}")
            st.write(f"- **Zombie Throughput:** <= {max_throughput}")
            st.write(f"- **Zombie Network:** <= {max_network} KBps")


        with col_detail2:
            st.markdown("**ℹ️ Filter & Penyusutan Data**")
            st.write(f"- Membuang **{len(raw_dataframe) - len(active_vms)} VM** yang di luar status (State) sidebar.")
            st.write(f"- Membuang **{len(active_vms) - total_di_tabel} VM** akibat filter target Uptime / Tag.")


        with col_detail3:
            st.markdown("**⚠️ Catatan Parsing Numerik**")
            st.write(f"Kolom Memory Utama: `{memory_column}`")
            if parse_fail_counts:
                st.write("Sistem mendeteksi nilai tidak terbaca (dianggap 0):")
                st.json(parse_fail_counts)
            else:
                st.success("✅ Seluruh angka berhasil dikonversi.")



def render_results_section(combined_candidates, memory_column, updated_by, tanggal_proses=None):
    st.markdown("### 📋 Hasil Keputusan & Analisis Master VM")


    if combined_candidates.empty:
        st.info("Tidak ada VM yang memenuhi kriteria filter saat ini.")
        return


    display_dataframe = _ensure_columns(combined_candidates)
    display_dataframe = merge_status_into_df(display_dataframe)


    preview_columns = [
        "Name", "Kritikalitas", "State", "Uptime / Days", "Days Powered Off", "Label", # <-- TAMBAH Kritikalitas di sini
        "Skor Idle (0-100)", "CPU Percentile 95%", "IOPS Percentile 95%",
        "Throughput Percentile 95%", memory_column,
        "Network I/O | Usage Rate (KBps) - 95th Percentile",
        "Status Justifikasi", "Status HK", "Catatan"
    ]
    preview_columns = [
        column for column in preview_columns if column in display_dataframe.columns
    ]


    st.markdown(
        "Gunakan tabel di bawah ini untuk meninjau justifikasi setiap VM. "
        "Anda dapat mengubah status `Status HK` dan `Catatan` langsung pada tabel."
    )


    edited_dataframe = st.data_editor(
        display_dataframe[preview_columns],
        hide_index=True,
        column_config={
            "Status HK": st.column_config.SelectboxColumn(
                "Status HK",
                help="Status tindak lanjut housekeeping",
                width="medium",
                options=["Pending", "Approved", "Rejected"],
                required=True,
            ),
            "Catatan": st.column_config.TextColumn(
                "Catatan",
                help="Catatan/Alasan tambahan",
                width="large",
            ),
            "Skor Idle (0-100)": st.column_config.NumberColumn(
                "Skor Idle",
                format="%.2f",
            ),
        },
        use_container_width=True,
        disabled=[
            column for column in preview_columns if column not in ["Status HK", "Catatan"]
        ],
        key="master_vm_editor",
    )

    if st.button("💾 Simpan Perubahan", type="primary"):
        if not updated_by or updated_by.strip() == "":
            # FIX 1: Ubah st.error statis menjadi st.toast
            st.toast("⚠️ Masukkan nama/identitas Anda pada sidebar sebelum menyimpan perubahan.", icon="⚠️")
        else:
            changed_rows = edited_dataframe[
                (edited_dataframe["Status HK"] != display_dataframe["Status HK"])
                | (edited_dataframe["Catatan"] != display_dataframe["Catatan"])
            ]
            if changed_rows.empty:
                # FIX 2: Ubah st.info statis menjadi st.toast
                st.toast("Tidak ada perubahan status untuk disimpan.", icon="ℹ️")
            else:
                # FIX 3: Cukup panggil fungsinya. Hapus st.toast sukses di sini
                # karena fungsi save_status_updates() sudah memunculkan toast-nya sendiri.
                save_status_updates(
                    display_dataframe,
                    edited_dataframe,
                    updated_by,
                )

    buffer = io.BytesIO()
    # Tambah timestamp di filename jika tanggal_proses tersedia
    file_name = f"Master_VM_Analysis_{tanggal_proses}.xlsx" if tanggal_proses else "Master_VM_Analysis.xlsx"


    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        display_dataframe.to_excel(writer, index=False, sheet_name="Master VM Analysis")
    st.download_button(
        label="📥 Download Excel Master VM (Seluruh Kolom)",
        data=buffer.getvalue(),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Download keseluruhan data (termasuk kolom yang tidak tampil di tabel preview).",
    )
