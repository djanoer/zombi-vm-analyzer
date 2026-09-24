# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — ENTRY POINT: main.py
# ------------------------------------------------------------------------------
# Kontrak data:
# - analysis.py menghasilkan kolom CANDIDATE_COLUMN ("Is Kandidat Zombie").
# - Label akhir ditentukan setelah merge hasil analisis, disposal, dan Status HK.
# - UUID adalah UUID murni dan tetap ditampilkan sebagai data.
# - vCenter dinormalisasi menjadi VC01/VC02.
# - Identity Key = vCenter + UUID untuk VM dengan UUID valid.
# - VM Powered Off tanpa UUID menggunakan vCenter + Name.
# - Identity Key digunakan internal untuk merge, deduplikasi, dan trend.
#
# Model data (dikonfirmasi user):
# - Master metrics berisi SELURUH VM, baik Power On maupun Power Off.
# - File Power Off adalah ENRICHMENT (subset) yang hanya menambahkan
#   kolom "Days Powered Off"; bukan pengganti master.
# - UUID kosong hanya diizinkan untuk VM Power Off (fallback vCenter+Name).
#   VM Power On tanpa UUID DITOLAK karena tidak dapat diberi identity
#   yang aman untuk analisis zombie.
#
# PATCH NOTES (25 Sep 2026):
# - Fase 2 (FEAT-05, Opsi B): hook render_vcenter_move_section() setelah
#   panel validasi -- expander konfirmasi penautan histori VM pindah
#   vCenter, hanya muncul jika ada kandidat.
#
# PATCH NOTES (24 Sep 2026, final pass):
# - BUG DIPERBAIKI: render_validation_section() sebelumnya menerima
#   `filtered_vms` (sudah lolos filter State+Uptime+Tag) sebagai
#   parameter kedua, padahal seharusnya menerima `active_vms` (baru
#   lolos filter State saja). Akibatnya statistik "Membuang X VM akibat
#   filter Uptime/Tag" SELALU menampilkan 0, dan "Membuang X VM akibat
#   filter State" menggelembung karena diam-diam menyerap kontribusi
#   filter Uptime/Tag juga. Ini murni bug pelaporan statistik pada
#   panel Validasi & Sanity Check -- TIDAK mempengaruhi hasil analisis
#   zombie/disposal itu sendiri.
# - Import "normalize_text_series" dari identity_utils DIHAPUS karena
#   tidak pernah dipakai di file ini (sisa dari versi sebelum
#   build_identity_key diimpor langsung, bukan didefinisikan lokal).
# - Blok debug Identity Key yang sebelumnya inline kini memakai
#   render_identity_debug() dari debug_view.py.
# - Seluruh fungsi normalisasi/identity diimpor dari identity_utils.py
#   (satu-satunya sumber kebenaran), tidak lagi didefinisikan ulang lokal.
# - Nama kolom hasil analisis diimpor dari constants.py (CANDIDATE_COLUMN,
#   SCORE_COLUMN, JUSTIFICATION_COLUMN).
# - "debug_mode" diinisialisasi dengan default False di baris paling atas
#   (sebelum widget apa pun), agar dijamin selalu terikat di seluruh
#   jalur eksekusi.
# - TIDAK ADA perubahan pada urutan pipeline, business rule, atau formula.
# ------------------------------------------------------------------------------


import re
import traceback


import pandas as pd
import streamlit as st


from analysis import run_zombie_analysis
from constants import (
    CANDIDATE_COLUMN,
    JUSTIFICATION_COLUMN,
    OPTIONAL_COLUMNS,
    SCORE_COLUMN,
)
from data_loader import (
    flag_data_quality,
    load_and_merge_uploads,
    load_pic_uploads,
    load_power_off_uploads,
    normalize_state_column,
    parse_numeric_columns,
    resolve_memory_column,
)
from debug_view import (
    render_identity_debug,
    render_pipeline_debug,
    render_raw_data_debug,
)
from disposal_rules import merge_disposal_and_zombie
from filter_settings import load_filter_settings
from identity_utils import (
    build_identity_key,
    invalid_identity_mask,
    is_powered_off_series,
    normalize_uuid_series,
    normalize_vcenter_series,
)
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
from status_tracking import bulk_save_pic_mapping, merge_status_into_df
from vcenter_move_view import render_vcenter_move_section
from trend_analysis import record_period_snapshot
from trend_view import render_trend_section


# PATCH: default aman -- menjamin variabel selalu terikat bahkan jika
# exception terjadi sangat awal (sebelum render_debug_toggle() dipanggil).
debug_mode = False


st.set_page_config(
    page_title="Zombie VM Analyzer",
    layout="wide",
    page_icon="🧟",
)


st.title("🧟 Zombie VM Analyzer v4.0")
st.markdown(
    "**Decision-Support System:** Menganalisis utilisasi VM secara otomatis "
    "untuk menemukan, mengklasifikasikan, dan menjustifikasi zombie VM — "
    "objektif, terukur, dan terdokumentasi sebagai dasar decommission."
)


# ==============================================================================
# HELPER: Validasi & pembentukan identity
# ------------------------------------------------------------------------------
# Fungsi normalisasi & pembentukan Identity Key TIDAK didefinisikan ulang
# di sini -- diimpor dari identity_utils.py. Bagian di bawah hanya berisi
# ATURAN VALIDASI bisnis (Name wajib, vCenter wajib, UUID wajib untuk
# Power On) yang memang spesifik untuk kontrak main.py.
# ==============================================================================


def validate_input_columns(dataframe, dataframe_name):
    """
    Validasi kolom identitas dasar.

    Kontrak:
    - Name wajib ada dan tidak boleh kosong.
    - vCenter wajib ada dan tidak boleh kosong/tidak dikenali.
    - UUID wajib ada sebagai KOLOM, tetapi nilainya boleh kosong HANYA
      untuk baris yang berstatus Powered Off (fallback vCenter+Name).
      VM Power On tanpa UUID akan ditolak.
    """
    required_columns = ["Name", "vCenter", "UUID"]
    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom input wajib hilang pada {dataframe_name}: "
            + ", ".join(missing_columns)
        )

    result = dataframe.copy()
    result["Name"] = result["Name"].fillna("").astype(str).str.strip()
    result["vCenter"] = normalize_vcenter_series(result["vCenter"])
    result["UUID"] = normalize_uuid_series(result["UUID"])

    if (result["Name"] == "").any():
        raise ValueError(
            f"Ditemukan Name kosong pada {dataframe_name}."
        )

    if result["vCenter"].isna().any():
        invalid_rows = result.loc[result["vCenter"].isna()].head(10)
        raise ValueError(
            f"Ditemukan vCenter kosong/tidak valid pada {dataframe_name}. "
            f"Contoh: {invalid_rows.to_dict('records')}"
        )

    active_without_uuid = (
        ~is_powered_off_series(result)
        & result["UUID"].isna()
    )

    if active_without_uuid.any():
        invalid_rows = result.loc[active_without_uuid].head(10)
        raise ValueError(
            f"Ditemukan VM Power On tanpa UUID pada {dataframe_name}. "
            "VM Power On wajib memiliki UUID untuk dianalisis. "
            f"Contoh: {invalid_rows.to_dict('records')}"
        )

    return result



def validate_identity_column(dataframe, dataframe_name):
    result = validate_input_columns(dataframe, dataframe_name)
    result = build_identity_key(result)

    identity_invalid_mask = invalid_identity_mask(result["Identity Key"])
    if identity_invalid_mask.any():
        invalid_rows = result.loc[identity_invalid_mask].head(10)
        raise ValueError(
            f"Ditemukan identity kosong pada {dataframe_name}. "
            f"Contoh: {invalid_rows.to_dict('records')}"
        )

    return result



def validate_existing_identity_key(dataframe, dataframe_name):
    required_columns = ["Identity Key", "UUID", "vCenter"]
    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom identity hilang pada {dataframe_name}: "
            + ", ".join(missing_columns)
        )

    result = dataframe.copy()
    result["Identity Key"] = (
        result["Identity Key"].astype("string").str.strip()
    )

    invalid_mask = invalid_identity_mask(result["Identity Key"])
    if invalid_mask.any():
        invalid_rows = result.loc[invalid_mask].head(10)
        raise ValueError(
            f"Ditemukan Identity Key kosong pada {dataframe_name}. "
            f"Contoh: {invalid_rows.to_dict('records')}"
        )

    duplicate_mask = result["Identity Key"].duplicated(keep=False)
    if duplicate_mask.any():
        duplicate_values = (
            result.loc[duplicate_mask, "Identity Key"]
            .drop_duplicates()
            .tolist()
        )
        raise ValueError(
            f"Ditemukan Identity Key duplikat pada {dataframe_name}: "
            + ", ".join(duplicate_values)
        )

    return result



def validate_unique_identity_dataframe(dataframe, dataframe_name):
    result = validate_identity_column(dataframe, dataframe_name)
    duplicate_mask = result["Identity Key"].duplicated(keep=False)

    if duplicate_mask.any():
        duplicate_values = (
            result.loc[duplicate_mask, "Identity Key"]
            .drop_duplicates()
            .tolist()
        )
        raise ValueError(
            f"Ditemukan Identity Key duplikat pada {dataframe_name}: "
            + ", ".join(duplicate_values)
        )

    return result



def deduplicate_raw_dataframe(dataframe):
    """
    Deduplikasi berdasarkan Identity Key.

    Dipanggil SETELAH normalisasi State & parsing numerik, agar
    perbandingan metrik antarbaris duplikat lebih akurat dan fallback
    Powered Off terbentuk dari State final.
    """
    result = validate_identity_column(dataframe, "raw_dataframe")
    duplicate_mask = result["Identity Key"].duplicated(keep=False)

    if not duplicate_mask.any():
        return result.reset_index(drop=True)

    duplicate_rows = result.loc[duplicate_mask].copy()
    duplicate_keys = duplicate_rows["Identity Key"].drop_duplicates().tolist()
    compare_columns = [
        column
        for column in [
            "Name",
            "State",
            "vCenter",
            "Host",
            "Cluster",
            "Datastore",
            "CPU Percentile 95%",
            "IOPS Percentile 95%",
            "Throughput Percentile 95%",
            "Network I/O | Usage Rate (KBps) - 95th Percentile",
            "Uptime / Days",
            "Status Idle",
        ]
        if column in result.columns
    ]

    conflicting_keys = []
    for identity_key in duplicate_keys:
        identity_rows = duplicate_rows[
            duplicate_rows["Identity Key"] == identity_key
        ]
        if compare_columns and len(
            identity_rows[compare_columns].drop_duplicates()
        ) > 1:
            conflicting_keys.append(identity_key)

    if conflicting_keys:
        conflict_preview = (
            duplicate_rows[
                duplicate_rows["Identity Key"].isin(conflicting_keys)
            ]
            .sort_values("Identity Key")
            .head(50)
        )
        raise ValueError(
            "Identity vCenter+UUID memiliki isi metrik berbeda sehingga "
            "tidak dapat dideduplikasi secara aman. "
            f"Identity konflik: {conflicting_keys}. "
            f"Detail: {conflict_preview.to_dict('records')}"
        )

    st.warning(
        f"Ditemukan {len(duplicate_rows)} baris duplikat identik berdasarkan "
        "Identity Key. Baris direduksi menjadi satu."
    )

    return (
        result.drop_duplicates(subset=["Identity Key"], keep="last")
        .reset_index(drop=True)
    )


# ==============================================================================
# UPLOAD: Master metrics (berisi Power On + Power Off)
# ==============================================================================

metric_files = st.file_uploader(
    "📂 Upload CSV Metrik VM",
    type=["csv"],
    accept_multiple_files=True,
    help=(
        "File master seluruh VM dan metrik utama. "
        "Berisi VM Power On dan Power Off sekaligus."
    ),
)


raw_dataframe = None
failed_metric_files = []
if metric_files:
    raw_dataframe, failed_metric_files, _ = load_and_merge_uploads(metric_files)
    for filename, error in failed_metric_files:
        st.error(f"❌ Gagal memproses file metrik **{filename}**: {error}")
    if raw_dataframe is not None and not raw_dataframe.empty:
        st.success(f"CSV Metrik: {len(raw_dataframe)} VM master berhasil dimuat.")


poweroff_files = st.file_uploader(
    "⏻ Upload CSV Power Off (Opsional)",
    type=["csv"],
    accept_multiple_files=True,
    help=(
        "File tambahan (subset VM Power Off) untuk enrichment "
        "Days Powered Off pada VM master. Bukan pengganti master metrics."
    ),
)


power_off_dataframe = None
if poweroff_files:
    power_off_dataframe, failed_poweroff_files = load_power_off_uploads(poweroff_files)
    for filename, error in failed_poweroff_files:
        st.error(f"❌ Gagal memproses file Power Off **{filename}**: {error}")
    if power_off_dataframe is not None:
        st.success(
            f"CSV Power Off: {len(power_off_dataframe)} VM enrichment berhasil dimuat."
        )


pic_files = st.file_uploader(
    "👤 Upload Data PIC / Owner (Opsional)",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True,
    help=(
        "File inventory (Excel/CSV) berisi pemetaan Nama VM ke PIC. "
        "Cukup upload sesekali untuk update database."
    ),
)


if pic_files:
    pic_dataframe, failed_pic_files = load_pic_uploads(pic_files)
    for filename, error in failed_pic_files:
        st.error(f"❌ Gagal memproses file PIC **{filename}**: {error}")
    if pic_dataframe is not None and not pic_dataframe.empty:
        st.success(f"Data PIC: Ditemukan {len(pic_dataframe)} pemetaan VM valid.")
        if st.button("💾 Ekstrak & Simpan PIC ke Database", type="primary"):
            current_user = st.session_state.get(
                "updated_by_name",
                "System Bulk Upload",
            )
            saved_count = bulk_save_pic_mapping(pic_dataframe, current_user)
            if saved_count > 0:
                st.toast(
                    f"Berhasil memperbarui {saved_count} kepemilikan VM ke database!",
                    icon="✅",
                )


render_manual_book()
saved_settings, filter_load_error = load_filter_settings()
debug_mode = render_debug_toggle()
updated_by = render_user_identity()
tanggal_proses = render_analysis_date_control()


if not metric_files or raw_dataframe is None or raw_dataframe.empty:
    st.info("⬆️ Upload CSV Metrik untuk memulai analisis.")
    st.stop()


try:
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

    raw_dataframe = deduplicate_raw_dataframe(raw_dataframe)

    selected_states = render_status_filter(
        unique_states,
        default_active_states,
        saved_settings,
    )
    if not selected_states:
        st.warning("Pilih minimal satu status VM untuk analisis.")
        st.stop()

    # active_vms = VM setelah filter State SAJA (belum Uptime/Tag).
    # Dipakai sebagai baseline "sebelum" untuk statistik penyusutan data
    # di render_validation_section() -- JANGAN diganti dengan filtered_vms
    # (lihat PATCH NOTES di atas untuk detail bug yang pernah terjadi).
    active_vms = raw_dataframe[
        raw_dataframe["State"].isin(selected_states)
    ].copy()

    min_uptime, max_uptime = render_uptime_filter(
        active_vms,
        saved_settings,
    )
    tag_mapping, selected_tags = render_tag_filter(
        active_vms,
        saved_settings,
    )
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
        "tag_filter_input": selected_tags,
    }
    render_filter_persistence_controls(current_settings, filter_load_error)

    is_powered_off = is_powered_off_series(active_vms)
    data_max_uptime = active_vms["Uptime / Days"].max()
    actual_max_uptime = max_uptime if max_uptime else data_max_uptime

    # FIX-04: batas bawah INKLUSIF (>=) — VM tepat pada min_uptime tetap ikut.
    valid_uptime = (
        (active_vms["Uptime / Days"] >= min_uptime)
        & (active_vms["Uptime / Days"] <= actual_max_uptime)
    )
    unknown_uptime = active_vms["Kualitas Data"].eq("Tidak Diketahui")
    uptime_mask = is_powered_off | valid_uptime | unknown_uptime
    filtered_vms = active_vms.loc[uptime_mask].copy()

    if selected_tags:
        allowed_tags = [
            tag
            for display in selected_tags
            for tag in tag_mapping[display]
        ]
        tag_mask = pd.Series(False, index=filtered_vms.index)
        for tag in allowed_tags:
            tag_mask |= filtered_vms["Summary|vSphere Tag"].str.contains(
                re.escape(tag),
                na=False,
            )
        filtered_vms = filtered_vms.loc[tag_mask].copy()

    for column in OPTIONAL_COLUMNS:
        if column not in filtered_vms.columns:
            filtered_vms[column] = 0

    if "Summary|vSphere Tag" in filtered_vms.columns:
        filtered_vms["Kritikalitas"] = (
            filtered_vms["Summary|vSphere Tag"]
            .fillna("")
            .apply(clean_criticality_tag)
        )
    else:
        filtered_vms["Kritikalitas"] = "Unknown"

    filtered_vms = validate_identity_column(filtered_vms, "filtered_vms")

    filtered_active = filtered_vms[~is_powered_off_series(filtered_vms)].copy()
    filtered_active = validate_unique_identity_dataframe(
        filtered_active,
        "filtered_active",
    )

    analyzed_vms, zombie_candidates = run_zombie_analysis(
        filtered_active,
        max_cpu,
        max_iops,
        max_throughput,
        max_network,
    )
    analyzed_vms = validate_unique_identity_dataframe(
        analyzed_vms,
        "analyzed_vms",
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

    combined_candidates = validate_identity_column(
        combined_candidates,
        "combined_candidates",
    )

    duplicate_mask = combined_candidates["Identity Key"].duplicated(keep=False)
    if duplicate_mask.any():
        duplicate_values = (
            combined_candidates.loc[duplicate_mask, "Identity Key"]
            .drop_duplicates()
            .tolist()
        )
        raise ValueError(
            "Ditemukan Identity Key duplikat setelah merge disposal dan zombie: "
            + ", ".join(duplicate_values)
        )

    analysis_columns = [
        "Name",
        "UUID",
        "vCenter",
        "Identity Key",
        CANDIDATE_COLUMN,
        SCORE_COLUMN,
        JUSTIFICATION_COLUMN,
    ]
    missing_analysis_columns = [
        column
        for column in analysis_columns
        if column not in analyzed_vms.columns
    ]
    if missing_analysis_columns:
        raise ValueError(
            "Kolom hasil analisis hilang: "
            + ", ".join(missing_analysis_columns)
        )

    analysis_result = validate_existing_identity_key(
        analyzed_vms[analysis_columns].copy(),
        "analysis_result",
    )

    identity_series = combined_candidates["Identity Key"]
    valid_identity_mask = ~invalid_identity_mask(identity_series)

    combined_with_identity = combined_candidates[valid_identity_mask].copy()
    combined_without_identity = combined_candidates[~valid_identity_mask].copy()

    combined_with_identity = combined_with_identity.merge(
        analysis_result[
            [
                "Identity Key",
                CANDIDATE_COLUMN,
                SCORE_COLUMN,
                JUSTIFICATION_COLUMN,
            ]
        ],
        on="Identity Key",
        how="left",
        suffixes=("", " Analysis"),
        validate="one_to_one",
    )

    combined_without_identity[CANDIDATE_COLUMN] = False
    combined_without_identity[SCORE_COLUMN] = 0.0
    combined_without_identity[JUSTIFICATION_COLUMN] = (
        "VM tidak memiliki identity key valid; "
        "tidak diproses sebagai Kandidat Zombie."
    )

    combined_candidates = pd.concat(
        [combined_with_identity, combined_without_identity],
        ignore_index=True,
    )

    combined_candidates[CANDIDATE_COLUMN] = combined_candidates[
        CANDIDATE_COLUMN
    ].fillna(False)
    combined_candidates[SCORE_COLUMN] = pd.to_numeric(
        combined_candidates[SCORE_COLUMN],
        errors="coerce",
    ).fillna(0.0)

    powered_off_no_analysis_mask = (
        is_powered_off_series(combined_candidates)
        & combined_candidates[JUSTIFICATION_COLUMN].isna()
    )
    combined_candidates.loc[
        powered_off_no_analysis_mask,
        JUSTIFICATION_COLUMN,
    ] = "VM Powered Off; Skor Idle tidak dihitung (bukan hasil pengukuran)."

    combined_candidates[JUSTIFICATION_COLUMN] = (
        combined_candidates[JUSTIFICATION_COLUMN].fillna(
            "VM tidak terdeteksi oleh analisis."
        )
    )
    combined_candidates["Label"] = combined_candidates["Label"].fillna(
        "Tidak Ditandai"
    )

    combined_candidates = merge_status_into_df(combined_candidates)

    is_zombie_mask = combined_candidates[CANDIDATE_COLUMN].astype(bool)
    is_not_disposal_mask = combined_candidates["Label"] == "Tidak Ditandai"
    is_not_rejected = combined_candidates["Status HK"] != "Rejected"

    combined_candidates.loc[
        is_zombie_mask & is_not_disposal_mask & is_not_rejected,
        "Label",
    ] = "Kandidat Zombie"
    combined_candidates.loc[
        is_zombie_mask & is_not_disposal_mask & ~is_not_rejected,
        "Label",
    ] = "Pengecualian (Rejected)"

    total_in_table = len(combined_candidates)
    total_zombie = len(
        combined_candidates[combined_candidates["Label"] == "Kandidat Zombie"]
    )
    total_disposal = len(
        combined_candidates[combined_candidates["Label"] == "Kandidat Disposal"]
    )

    zombie_vms = combined_candidates[
        combined_candidates["Label"] == "Kandidat Zombie"
    ]
    est_vcpu = zombie_vms["vCPU"].sum() if "vCPU" in zombie_vms.columns else 0
    est_mem_gb = (
        zombie_vms["Memory (GB)"].sum()
        if "Memory (GB)" in zombie_vms.columns
        else 0
    )

    actionable_vms = combined_candidates[
        combined_candidates["Label"].isin(
            ["Kandidat Zombie", "Kandidat Disposal"]
        )
    ]
    est_storage_gb = (
        actionable_vms["Provisioned Space (GB)"].sum()
        if "Provisioned Space (GB)" in actionable_vms.columns
        else 0
    )
    est_storage_tb = (
        actionable_vms["Provisioned Space (TB)"].sum()
        if "Provisioned Space (TB)" in actionable_vms.columns
        else 0
    )

    if debug_mode:
        render_pipeline_debug(
            active_vms,
            filtered_vms,
            zombie_candidates,
            parse_fail_counts,
        )
        render_identity_debug(combined_candidates)

    # PATCH BUG: parameter kedua HARUS active_vms (setelah filter State
    # saja), BUKAN filtered_vms (yang sudah lolos filter Uptime/Tag
    # juga) -- lihat PATCH NOTES di atas untuk dampak bug sebelumnya.
    render_validation_section(
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
        min_uptime,
        max_uptime,
        total_in_table,
        total_zombie,
        total_disposal,
        est_vcpu,
        est_mem_gb,
        est_storage_gb,
        est_storage_tb,
    )

    # Fase 2 (Opsi B): tawarkan penautan histori untuk VM yang terdeteksi
    # pindah vCenter. Hanya muncul jika ada kandidat; tidak mengubah data
    # tanpa klik eksplisit dari user.
    render_vcenter_move_section(combined_candidates, updated_by)

    kandidat_only = combined_candidates[
        ~combined_candidates["Label"].isin(
            [
                "Tidak Ditandai",
                "Pengecualian (Rejected)",
            ]
        )
    ].copy()

    render_results_section(
        kandidat_only,
        memory_column,
        updated_by,
        tanggal_proses,
    )

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
    with st.expander(
        "🔧 Detail Teknis",
        expanded=debug_mode,
    ):
        st.code(traceback.format_exc())
