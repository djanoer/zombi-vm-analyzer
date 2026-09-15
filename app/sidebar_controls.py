# ==============================================================================
#  🧟 ZOMBIE VM ANALYZER v4.0 — MODULE: sidebar_controls.py
# ------------------------------------------------------------------------------
#  UPDATE: Aturan Bisnis Tambahan kini hanya memiliki kontrol Days Powered Off.
#  Info singkat setiap widget tersedia melalui ikon help '?'.
#  FIX #1: Cap max_data ke nilai reasonable (2000 hari) untuk slider uptime
# ==============================================================================
from datetime import date
import streamlit as st
from constants import DEFAULT_CUSTOM_THRESHOLD, DEFAULT_MIN_CONSISTENT_PERIODS, THRESHOLD_PRESETS
from filter_settings import save_filter_settings
from parsers import clean_criticality_tag



def render_debug_toggle():
    st.sidebar.header("🐞 Mode Debug")
    return st.sidebar.checkbox("Aktifkan Mode Debug", value=st.session_state.get("debug_mode", False), help="Tampilkan kolom, dtype, preview data, pipeline, dan traceback.", key="debug_mode")



def render_user_identity():
    st.sidebar.header("👤 Identitas Anda")
    return st.sidebar.text_input("Nama Anda", value=st.session_state.get("updated_by_name", ""), help="Dicatat sebagai updated_by pada Status HK.", key="updated_by_name")



def render_analysis_date_control():
    st.sidebar.header("🗓️ Periode Analisa")
    return st.sidebar.date_input("Tanggal Analisa Ini", value=date.today(), help="Tanggal snapshot tren; tanggal sama melakukan upsert.", key="tanggal_proses_input")



def render_min_consistent_periods_control(saved_settings):
    return st.sidebar.slider("📈 Min. Periode Konsisten Idle", 2, 12, int(saved_settings.get("min_consistent_periods", DEFAULT_MIN_CONSISTENT_PERIODS)), 1, help="Minimum periode idle berturut-turut tanpa gap.", key="min_consistent_periods_input")



def render_status_filter(unique_states, default_active_states, saved_settings):
    st.sidebar.header("🔌 Filter Status VM")
    saved_states = saved_settings.get("selected_states") or []
    valid_saved = [state for state in saved_states if state in unique_states]
    return st.sidebar.multiselect("Status yang dianggap Aktif", unique_states, default=valid_saved or default_active_states, help="Dipakai untuk Skor Idle/Zombie. VM OFF diproses dari file Power Off.", key="selected_states_input")



def render_uptime_filter(active_vms, saved_settings):
    st.sidebar.header("🗓️ Rentang Target Uptime (Hari)")

    # FIX #1: Cap max_data ke nilai reasonable (2000 hari = ~5.5 tahun)
    min_data = int(active_vms["Uptime / Days"].min()) if not active_vms.empty else 0
    max_data = int(active_vms["Uptime / Days"].max()) if not active_vms.empty else 0
    max_data = min(max_data, 2000)  # Cap ke 2000 hari

    saved_min, saved_max = saved_settings.get("min_uptime"), saved_settings.get("max_uptime")
    default_min = saved_min if isinstance(saved_min, int) and min_data <= saved_min <= max_data else min_data
    default_max = saved_max if isinstance(saved_max, int) and min_data <= saved_max <= max_data else max_data

    first, second = st.sidebar.columns(2)
    min_uptime = first.number_input("Minimum", 0, max_data, default_min, 1, help="Batas uptime minimum untuk analisis Zombie.", key="min_uptime_input")
    max_uptime = second.number_input("Maksimum", 0, max_data, default_max, 1, help="Batas uptime maksimum untuk analisis Zombie.", key="max_uptime_input")
    return min_uptime, max_uptime



def render_tag_filter(active_vms):
    raw_tags = active_vms["Summary|vSphere Tag"].dropna().unique().tolist()
    tag_mapping = {}
    for tag in raw_tags:
        tag_mapping.setdefault(clean_criticality_tag(tag), []).append(tag)
    return tag_mapping, st.sidebar.multiselect("🏷️ Filter Tag Kritikalitas", sorted(tag_mapping), help="Kosongkan untuk semua tag.")



def render_threshold_controls(saved_settings):
    st.sidebar.header("⚙️ Threshold Skor Idle P95")
    options = ["Custom (Atur Manual)"] + list(THRESHOLD_PRESETS)
    saved_preset = saved_settings.get("preset_mode", options[0])
    preset = st.sidebar.selectbox("🎯 Preset Agresivitas", options, index=options.index(saved_preset) if saved_preset in options else 0, help="Preset mengatur CPU/IOPS/Throughput/Network P95.", key="preset_mode_input")
    values = THRESHOLD_PRESETS[preset] if preset in THRESHOLD_PRESETS else {key: float(saved_settings.get(f"max_{key}", DEFAULT_CUSTOM_THRESHOLD[key])) for key in ["cpu", "iops", "throughput", "network"]}
    disabled = preset in THRESHOLD_PRESETS
    cpu = st.sidebar.slider("📉 Batas CPU P95 (%)", 1.0, 10.0, values["cpu"], 0.5, disabled=disabled, help="Syarat AND kandidat + bobot 20%.", key="max_cpu_input")
    iops = st.sidebar.slider("💽 Batas IOPS P95", 1.0, 50.0, values["iops"], 1.0, disabled=disabled, help="Syarat AND kandidat + bobot 25%.", key="max_iops_input")
    throughput = st.sidebar.slider("📡 Batas Throughput P95", 1.0, 200.0, values["throughput"], 1.0, disabled=disabled, help="Syarat AND kandidat + bobot 25%.", key="max_throughput_input")
    network = st.sidebar.slider("🌐 Batas Network P95 (KBps)", 0.1, 1000.0, values["network"], 0.5, disabled=disabled, help="Syarat AND kandidat + bobot 15%.", key="max_network_input")
    return preset, cpu, iops, throughput, network



def render_business_rule_controls(saved_settings):
    st.sidebar.header("🏷️ Aturan Disposal Tambahan")
    off_days = st.sidebar.number_input("⏻ Ambang Days Powered Off", 1, 365, int(saved_settings.get("min_off_days", 30)), 1, help="VM dari file Power Off menjadi Kandidat Disposal jika Days Powered Off > ambang ini.", key="min_off_days_input")
    return off_days



def render_filter_persistence_controls(current_settings, load_error):
    st.sidebar.header("💾 Simpan Pengaturan Filter")
    if load_error:
        st.sidebar.warning(f"Filter tersimpan gagal dibaca: {load_error}")
    if st.sidebar.button("💾 Simpan Filter Saat Ini", key="save_filter_button"):
        ok, error = save_filter_settings(current_settings)
        if ok:
            st.sidebar.success("✅ Filter tersimpan untuk sesi berikutnya.")
        else:
            st.sidebar.error(f"❌ Gagal menyimpan filter: {error}")
    st.sidebar.caption("Perubahan persisten setelah tombol simpan ditekan.")
