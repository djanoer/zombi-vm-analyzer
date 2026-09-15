# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — ENTRY POINT: main.py
# ============================================================================


import re
import traceback


import pandas as pd
import streamlit as st


from analysis import run_zombie_analysis
from constants import OPTIONAL_COLUMNS
from data_loader import (
    flag_data_quality,
    load_and_merge_uploads,
    load_power_off_uploads,
    normalize_state_column,
    parse_numeric_columns,
    resolve_memory_column,
)
from debug_view import render_pipeline_debug, render_raw_data_debug
from disposal_rules import merge_disposal_and_zombie
from filter_settings import load_filter_settings
from manual_book import render_manual_book
from parsers import clean_criticality_tag
from results_view import render_results_section, render_validation_section
from sidebar_controls import (
    render_analysis_date_control,
    render_business_rule_controls,
    render_debug_toggle,
    render_filter_persistence_controls,
    render_min_consistent_periods_control,
    render_status_filter,
    render_tag_filter,
    render_threshold_controls,
    render_uptime_filter,
    render_user_identity,
)
from trend_analysis import record_period_snapshot
from trend_view import render_trend_section


st.set_page_config(
    page_title="Zombie VM Analyzer",
    layout="wide",
    page_icon="🧟",
)
st.title("🧟 Zombie VM Analyzer v4.0")
st.markdown(
    "Decision-Support System: Tabel utama **hanya menampilkan VM yang sesuai dengan filter** "
    "(Status, Uptime, Tag). Label Disposal dan Zombie menjadi enrichment analisis."
)


metric_files = st.file_uploader(
    "📂 Upload CSV Metrik VM",
    type=["csv"],
    accept_multiple_files=True,
    help="File master seluruh VM dan metrik utama.",
)
poweroff_files = st.file_uploader(
    "⏻ Upload CSV Power Off (Opsional)",
    type=["csv"],
    accept_multiple_files=True,
    help="File tambahan Days Powered Off untuk enrichment VM master.",
)


render_manual_book()
saved_settings, filter_load_error = load_filter_settings()
debug_mode = render_debug_toggle()
updated_by = render_user_identity()
tanggal_proses = render_analysis_date_control()


if not metric_files:
    st.info("⬆️ Upload CSV Metrik untuk memulai analisis.")
    st.stop()


try:
    raw_dataframe, failed_metric_files, _ = load_and_merge_uploads(metric_files)
    for filename, error in failed_metric_files:
        st.error(f"❌ Gagal memproses file metrik **{filename}**: {error}")


    if raw_dataframe is None or raw_dataframe.empty:
        st.error("Tidak ada CSV metrik yang berhasil dimuat.")
        st.stop()


    st.success(f"CSV Metrik: {len(raw_dataframe)} VM master berhasil dimuat.")


    power_off_dataframe = None
    if poweroff_files:
        power_off_dataframe, failed_poweroff_files = load_power_off_uploads(
            poweroff_files
        )
        for filename, error in failed_poweroff_files:
            st.error(f"❌ Gagal memproses file Power Off **{filename}**: {error}")
        if power_off_dataframe is not None:
            st.success(
                f"CSV Power Off: {len(power_off_dataframe)} VM enrichment berhasil dimuat."
            )


    memory_column = resolve_memory_column(raw_dataframe)
    if debug_mode:
        render_raw_data_debug(raw_dataframe, memory_column)


    raw_dataframe = flag_data_quality(raw_dataframe)
    raw_dataframe, parse_fail_counts = parse_numeric_columns(
        raw_dataframe,
        memory_column,
    )
    raw_dataframe, unique_states, default_active_states = normalize_state_column(
        raw_dataframe
    )


    selected_states = render_status_filter(
        unique_states,
        default_active_states,
        saved_settings,
    )
    if not selected_states:
        st.warning("Pilih minimal satu status VM untuk analisis.")
        st.stop()


    active_vms = raw_dataframe[
        raw_dataframe["State"].isin(selected_states)
    ].copy()


    min_uptime, max_uptime = render_uptime_filter(
        active_vms,
        saved_settings,
    )
    tag_mapping, selected_tags = render_tag_filter(active_vms)
    preset, max_cpu, max_iops, max_throughput, max_network = (
        render_threshold_controls(saved_settings)
    )
    min_periods = render_min_consistent_periods_control(saved_settings)
    min_off_days = render_business_rule_controls(saved_settings)


    current_settings = {
        "selected_states": selected_states,
        "preset_mode": preset,
        "max_cpu": max_cpu,
        "max_iops": max_iops,
        "max_throughput": max_throughput,
        "max_network": max_network,
        "min_consistent_periods": min_periods,
        "min_uptime": int(min_uptime),
        "max_uptime": int(max_uptime),
        "min_off_days": int(min_off_days),
    }
    render_filter_persistence_controls(current_settings, filter_load_error)

    # -------------------------------------------------------------
    # Logika Filter Uptime (> minimum) & Max Dinamis
    # -------------------------------------------------------------
    # 1. Deteksi VM yang statusnya mati (PoweredOff, suspended, dsb)
    is_powered_off = active_vms["State"].str.lower().str.contains("off|suspend|inactive", na=False)

    # 2. Ambil nilai maksimum aktual dari data Uptime
    data_max_uptime = active_vms["Uptime / Days"].max()
    # Jika max_uptime dari UI kosong/0, gunakan nilai maksimum dari data
    actual_max_uptime = max_uptime if max_uptime else data_max_uptime

    # 3. Aturan Uptime: Lebih besar (>) dari minimum DAN Lebih kecil sama dengan (<=) maksimum
    valid_uptime = (
        (active_vms["Uptime / Days"] > min_uptime) &
        (active_vms["Uptime / Days"] <= actual_max_uptime)
    )

    # 4. Kualitas data tidak diketahui (bypass)
    unknown_uptime = active_vms["Kualitas Data"].eq("Tidak Diketahui")

    # 5. Gabungkan kondisi
    uptime_mask = is_powered_off | valid_uptime | unknown_uptime

    filtered_vms = active_vms.loc[uptime_mask].copy()
    # -------------------------------------------------------------

    if selected_tags:
        allowed_tags = [
            tag
            for display in selected_tags
            for tag in tag_mapping[display]
        ]
        tag_mask = pd.Series(False, index=filtered_vms.index)
        for tag in allowed_tags:
            tag_mask |= filtered_vms[
                "Summary|vSphere Tag"
            ].str.contains(re.escape(tag), na=False)
        filtered_vms = filtered_vms.loc[tag_mask].copy()


    # Jangan lupa import clean_criticality_tag dari parsers di bagian atas
    for column in OPTIONAL_COLUMNS:
        if column not in filtered_vms.columns:
            filtered_vms[column] = 0

    # Membuat kolom baru 'Kritikalitas' dari kolom Tag
    if "Summary|vSphere Tag" in filtered_vms.columns:
        filtered_vms["Kritikalitas"] = filtered_vms["Summary|vSphere Tag"].fillna("").apply(clean_criticality_tag)
    else:
        filtered_vms["Kritikalitas"] = "Unknown"

    analyzed_vms, zombie_candidates = run_zombie_analysis(
        filtered_vms,
        max_cpu,
        max_iops,
        max_throughput,
        max_network,
    )

    master_dataframe = filtered_vms.copy()


    if power_off_dataframe is not None:
        combined_candidates = merge_disposal_and_zombie(
            master_dataframe,
            power_off_dataframe,
            min_off_days,
        )
    else:
        combined_candidates = master_dataframe.copy()
        combined_candidates["Label"] = "Tidak Ditandai"


    # ==========================================================================
    # MERGE HASIL ANALISIS ZOMBIE KE COMBINED_CANDIDATES
    # ==========================================================================
    analysis_columns = [
        "Name",
        "UUID",
        "Is Kandidat Zombie",
        "Skor Idle (0-100)",
        "Status Justifikasi",
    ]
    analysis_result = analyzed_vms[
        [column for column in analysis_columns if column in analyzed_vms.columns]
    ].copy()

    for dataframe in [combined_candidates, analysis_result]:
        if "UUID" not in dataframe.columns:
            dataframe["UUID"] = ""
        dataframe["Name"] = dataframe["Name"].fillna("").astype(str).str.strip()
        dataframe["UUID"] = dataframe["UUID"].fillna("").astype(str).str.strip()

    analysis_result = analysis_result.drop_duplicates(
        ["Name", "UUID"],
        keep="first",
    )

    combined_candidates = combined_candidates.merge(
        analysis_result,
        on=["Name", "UUID"],
        how="left",
        suffixes=("", " Analysis"),
    )

    combined_candidates["Skor Idle (0-100)"] = combined_candidates[
        "Skor Idle (0-100)"
    ].fillna(0.0)

    combined_candidates["Status Justifikasi"] = combined_candidates[
        "Status Justifikasi"
    ].fillna("VM tidak terdeteksi oleh analisis.")

    combined_candidates["Label"] = combined_candidates["Label"].fillna("Tidak Ditandai")
    is_zombie_mask = combined_candidates["Is Kandidat Zombie"] == True
    is_not_disposal_mask = combined_candidates["Label"] == "Tidak Ditandai"
    combined_candidates.loc[
        is_zombie_mask & is_not_disposal_mask, "Label"
    ] = "Kandidat Zombie"
    # ==========================================================================


    # Hitung statistik untuk validasi (FIX #2: match dengan tabel)
    total_in_table = len(combined_candidates)
    total_zombie = len(combined_candidates[combined_candidates["Label"] == "Kandidat Zombie"])
    total_disposal = len(combined_candidates[combined_candidates["Label"] == "Kandidat Disposal"])
    total_with_score = len(combined_candidates[combined_candidates["Skor Idle (0-100)"] > 0])


    if debug_mode:
        render_pipeline_debug(
            active_vms,
            filtered_vms,
            zombie_candidates,
            parse_fail_counts,
        )


    # PEMBARUAN: Parameter disesuaikan agar panel Validasi persis mencerminkan Tabel
    render_validation_section(
        raw_dataframe,
        filtered_vms,
        combined_candidates,
        memory_column,
        parse_fail_counts,
        max_cpu,
        max_iops,
        max_throughput,
        max_network,
        min_off_days,
        total_in_table,
        total_zombie,
        total_disposal,
        total_with_score
    )


    # Hanya ambil VM yang labelnya BUKAN "Tidak Ditandai"
    kandidat_only = combined_candidates[combined_candidates["Label"] != "Tidak Ditandai"].copy()

    # Masukkan variabel kandidat_only, BUKAN combined_candidates
    render_results_section(kandidat_only, memory_column, updated_by, tanggal_proses)
    # -------------------------------------------------------------


    record_success, record_error = record_period_snapshot(
        combined_candidates,
        tanggal_proses,
    )
    render_trend_section(
        min_periods,
        tanggal_proses,
        record_success,
        record_error,
    )


except Exception as error:
    st.error(f"❌ Terjadi kesalahan teknis: {error}")
    with st.expander("🔧 Detail Teknis", expanded=debug_mode):
        st.code(traceback.format_exc())
