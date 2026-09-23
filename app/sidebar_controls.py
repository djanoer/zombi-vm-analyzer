# ==============================================================================
#  🧟 ZOMBIE VM ANALYZER v4.0 — MODULE: sidebar_controls.py
# ------------------------------------------------------------------------------
#  UPDATE: Aturan Bisnis Tambahan kini hanya memiliki kontrol Days Powered Off.
#  Info singkat setiap widget tersedia melalui ikon help '?'.
#  FIX #1: Cap max_data ke nilai reasonable untuk slider uptime.
#  FIX (17 Sep 2026): render_tag_filter() menerima saved_settings untuk
#  persist Filter Tag Kritikalitas antar sesi.
#
#  PATCH NOTES (24 Sep 2026):
#  - BUG KRITIS DIPERBAIKI: render_threshold_controls() sebelumnya
#    mengeset st.session_state[key] SEKALIGUS memberikan parameter
#    value= pada widget dengan key yang sama -- kombinasi ini
#    menyebabkan StreamlitAPIException setiap kali preset non-Custom
#    dipilih. Diperbaiki dengan HANYA mengandalkan st.session_state
#    (tanpa parameter value=) untuk widget-widget threshold.
#  - Cap uptime slider (sebelumnya diam-diam 2000 hari) kini disertai
#    peringatan eksplisit jika data asli melebihi batas tersebut, agar
#    VM dengan uptime sangat panjang (target utama tool ini) tidak
#    tersaring tanpa disadari.
#  - `import time` dipindah ke bagian atas file (sebelumnya di tengah
#    fungsi) untuk kerapian, tanpa mengubah perilaku.
# ==============================================================================
import time
from datetime import date

import streamlit as st

from constants import (
    DEFAULT_CUSTOM_THRESHOLD,
    DEFAULT_MIN_CONSISTENT_PERIODS,
    THRESHOLD_PRESETS,
)
from filter_settings import save_filter_settings, reset_filter_settings
from parsers import clean_criticality_tag


# Batas atas slider uptime. Ini HANYA membatasi rentang widget (untuk
# menghindari widget dengan rentang absurd akibat data korup), BUKAN
# membatasi hasil filter secara diam-diam -- lihat peringatan eksplisit
# di render_uptime_filter() jika data asli melebihi batas ini.
UPTIME_SLIDER_HARD_CAP = 3650  # ~10 tahun


def render_debug_toggle():
    st.sidebar.header("🐞 Mode Debug")
    return st.sidebar.checkbox(
        "Aktifkan Mode Debug",
        value=st.session_state.get("debug_mode", False),
        help="Tampilkan kolom, dtype, preview data, pipeline, dan traceback.",
        key="debug_mode"
    )


def render_user_identity():
    st.sidebar.header("👤 Identitas Anda")
    return st.sidebar.text_input(
        "Nama Anda",
        value=st.session_state.get("updated_by_name", ""),
        help="Dicatat sebagai updated_by pada Status HK.",
        key="updated_by_name"
    )


def render_analysis_date_control():
    st.sidebar.header("🗓️ Periode Analisa")
    return st.sidebar.date_input(
        "Tanggal Analisa Ini",
        value=date.today(),
        help="Tanggal snapshot tren; tanggal sama melakukan upsert.",
        key="tanggal_proses_input"
    )


def render_min_consistent_periods_control(saved_settings):
    return st.sidebar.slider(
        "📈 Min. Observasi Kandidat Berturut-turut", 2, 12,
        int(saved_settings.get("min_consistent_periods", DEFAULT_MIN_CONSISTENT_PERIODS)), 1,
        help=(
            "Jumlah minimum observasi aktual terbaru "
            "di mana VM tetap menjadi kandidat."
        ),
        key="min_consistent_periods_input"
    )


def render_status_filter(unique_states, default_active_states, saved_settings):
    st.sidebar.header("🔌 Filter Status VM")
    saved_states = saved_settings.get("selected_states") or []
    valid_saved = [state for state in saved_states if state in unique_states]
    return st.sidebar.multiselect(
        "Status yang dianggap Aktif", unique_states,
        default=valid_saved or default_active_states,
        help="Dipakai untuk Skor Idle/Zombie. VM OFF diproses dari file Power Off.",
        key="selected_states_input"
    )


def render_uptime_filter(active_vms, saved_settings):
    st.sidebar.header("🗓️ Rentang Target Uptime (Hari)")

    real_max_data = (
        int(active_vms["Uptime / Days"].max()) if not active_vms.empty else 0
    )
    max_data = min(real_max_data, UPTIME_SLIDER_HARD_CAP)

    # PATCH: peringatan eksplisit -- sebelumnya cap ini SENYAP, berisiko
    # menyaring VM dengan uptime sangat panjang (target utama tool ini)
    # tanpa disadari pengguna.
    if real_max_data > UPTIME_SLIDER_HARD_CAP:
        st.sidebar.warning(
            f"⚠️ Ditemukan VM dengan Uptime hingga **{real_max_data} hari**, "
            f"melebihi batas slider ({UPTIME_SLIDER_HARD_CAP} hari). "
            "VM dengan uptime di atas batas ini TIDAK akan ikut terfilter "
            "kecuali Anda menaikkan batas maksimum secara manual di bawah."
        )

    saved_min, saved_max = saved_settings.get("min_uptime"), saved_settings.get("max_uptime")

    default_min = saved_min if isinstance(saved_min, int) and 0 <= saved_min <= max_data else 0
    default_max = saved_max if isinstance(saved_max, int) and 0 <= saved_max <= max_data else max_data

    first, second = st.sidebar.columns(2)
    min_uptime = first.number_input(
        "Minimum", 0, max_data, default_min, 1,
        help="Batas uptime minimum untuk analisis Zombie.",
        key="min_uptime_input"
    )
    max_uptime = second.number_input(
        "Maksimum", 0, max_data, default_max, 1,
        help="Batas uptime maksimum untuk analisis Zombie.",
        key="max_uptime_input"
    )
    return min_uptime, max_uptime


def render_tag_filter(active_vms, saved_settings):
    """
    Render filter Tag Kritikalitas.

    FIX (17 Sep 2026): Menerima saved_settings untuk load default dari
    filter yang sudah disimpan sebelumnya, bukan hardcode default=[].
    """
    raw_tags = active_vms["Summary|vSphere Tag"].dropna().unique().tolist()
    tag_mapping = {}
    for tag in raw_tags:
        tag_mapping.setdefault(clean_criticality_tag(tag), []).append(tag)

    saved_tags = saved_settings.get("tag_filter_input", [])
    valid_saved_tags = [tag for tag in saved_tags if tag in tag_mapping]

    return tag_mapping, st.sidebar.multiselect(
        "🏷️ Filter Tag Kritikalitas",
        sorted(tag_mapping),
        default=valid_saved_tags,
        help="Kosongkan untuk semua tag.",
        key="tag_filter_input"
    )


def _seed_threshold_session_state(key, value):
    """Set session_state TANPA memberi parameter value= pada widget terkait
    -- menghindari konflik "Session State API vs value parameter" yang
    menyebabkan StreamlitAPIException."""
    st.session_state[key] = float(value)


def render_threshold_controls(saved_settings):
    """
    PATCH KRITIS: widget number_input di bawah TIDAK LAGI diberi parameter
    value= sama sekali. Nilai widget SEPENUHNYA dikendalikan lewat
    st.session_state, yang diisi secara eksplisit:
    - Jika preset dipilih -> paksa isi session_state dengan nilai preset
      (agar widget disabled langsung menampilkan nilai preset terbaru).
    - Jika Custom DAN belum pernah ada session_state (render pertama) ->
      isi dari saved_settings/default.
    - Jika Custom DAN sudah ada session_state (user sedang mengedit) ->
      JANGAN disentuh, biarkan nilai terakhir user tetap dipakai.
    """
    st.sidebar.header("⚙️ Threshold Zombie VM (Aktif)")
    options = ["Custom (Atur Manual)"] + list(THRESHOLD_PRESETS)
    saved_preset = saved_settings.get("preset_mode", options[0])
    preset = st.sidebar.selectbox(
        "🎯 Preset Agresivitas",
        options,
        index=options.index(saved_preset) if saved_preset in options else 0,
        help="Preset mengatur CPU/IOPS/Throughput/Network P95 untuk VM Aktif. Pilih 'Custom' untuk set manual.",
        key="preset_mode_input"
    )

    is_preset_mode = preset in THRESHOLD_PRESETS

    if is_preset_mode:
        preset_values = THRESHOLD_PRESETS[preset]
        _seed_threshold_session_state("max_cpu_input", preset_values["cpu"])
        _seed_threshold_session_state("max_iops_input", preset_values["iops"])
        _seed_threshold_session_state("max_throughput_input", preset_values["throughput"])
        _seed_threshold_session_state("max_network_input", preset_values["network"])
        display_values = preset_values
    else:
        fallback_values = {
            key: float(saved_settings.get(f"max_{key}", DEFAULT_CUSTOM_THRESHOLD[key]))
            for key in ["cpu", "iops", "throughput", "network"]
        }
        # Hanya seed jika BENAR-BENAR render pertama (belum ada state user).
        if "max_cpu_input" not in st.session_state:
            _seed_threshold_session_state("max_cpu_input", fallback_values["cpu"])
        if "max_iops_input" not in st.session_state:
            _seed_threshold_session_state("max_iops_input", fallback_values["iops"])
        if "max_throughput_input" not in st.session_state:
            _seed_threshold_session_state("max_throughput_input", fallback_values["throughput"])
        if "max_network_input" not in st.session_state:
            _seed_threshold_session_state("max_network_input", fallback_values["network"])
        display_values = fallback_values

    if is_preset_mode:
        st.sidebar.info(
            f"**{preset}**\n\n"
            f"CPU ≤ {display_values['cpu']}% | "
            f"IOPS ≤ {display_values['iops']} | "
            f"Throughput ≤ {display_values['throughput']} KBps | "
            f"Network ≤ {display_values['network']} KBps"
        )

    st.sidebar.markdown("**Custom Threshold (opsional):**")

    cpu = st.sidebar.number_input(
        "📉 Batas CPU P95 (%)", min_value=0.0, max_value=100.0,
        step=0.1, format="%.1f",
        disabled=is_preset_mode,
        help="VM dengan CPU P95 ≤ threshold ini akan dianggap kandidat zombie. Rekomendasi: 0.8%",
        key="max_cpu_input"
    )

    iops = st.sidebar.number_input(
        "💽 Batas IOPS P95", min_value=0.0, max_value=1000.0,
        step=0.5, format="%.1f",
        disabled=is_preset_mode,
        help="VM dengan IOPS P95 ≤ threshold ini akan dianggap kandidat zombie. Rekomendasi: 2.0",
        key="max_iops_input"
    )

    throughput = st.sidebar.number_input(
        "📡 Batas Throughput P95 (KBps)", min_value=0.0, max_value=1000.0,
        step=0.01, format="%.2f",
        disabled=is_preset_mode,
        help="VM dengan Throughput P95 ≤ threshold ini akan dianggap kandidat zombie. Rekomendasi: 0.10 KBps",
        key="max_throughput_input"
    )

    network = st.sidebar.number_input(
        "🌐 Batas Network P95 (KBps)", min_value=0.0, max_value=10000.0,
        step=1.0, format="%.0f",
        disabled=is_preset_mode,
        help="VM dengan Network P95 ≤ threshold ini akan dianggap kandidat zombie. Rekomendasi: 50 KBps",
        key="max_network_input"
    )

    if is_preset_mode:
        cpu, iops, throughput, network = (
            display_values["cpu"],
            display_values["iops"],
            display_values["throughput"],
            display_values["network"],
        )

    return preset, cpu, iops, throughput, network


def render_business_rule_controls(saved_settings):
    st.sidebar.header("🏷️ Aturan Disposal Tambahan")
    off_days = st.sidebar.number_input(
        "⏻ Ambang Days Powered Off",
        min_value=1, max_value=365,
        value=int(saved_settings.get("min_off_days", 30)), step=1,
        help="VM dari file Power Off menjadi Kandidat Disposal jika Days Powered Off > ambang ini. "
             "Threshold ini independen dari threshold Zombie VM Aktif.",
        key="min_off_days_input"
    )
    return off_days


def render_filter_persistence_controls(current_settings, load_error):
    st.sidebar.header("💾 Simpan Pengaturan Filter")

    if load_error:
        st.sidebar.warning(f"Filter tersimpan gagal dibaca: {load_error}")

    col1, col2 = st.sidebar.columns(2)

    if col1.button("💾 Simpan Filter", key="save_filter_button"):
        ok, error = save_filter_settings(current_settings)
        if ok:
            st.toast("Filter berhasil disimpan.", icon="💾")
        else:
            st.toast(f"Gagal menyimpan filter: {error}", icon="❌")

    if col2.button("🗑️ Reset Default", type="primary", key="reset_filter_button"):
        ok, error = reset_filter_settings()
        if ok:
            keys_to_clear = [
                "min_consistent_periods_input",
                "selected_states_input",
                "min_uptime_input",
                "max_uptime_input",
                "tag_filter_input",
                "preset_mode_input",
                "max_cpu_input",
                "max_iops_input",
                "max_throughput_input",
                "max_network_input",
                "min_off_days_input",
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]

            st.toast("Filter dikembalikan ke pengaturan default.", icon="🔄")
            time.sleep(1)
            st.rerun()
        else:
            st.toast(f"Gagal me-reset filter: {error}", icon="❌")

    st.sidebar.caption("Perubahan persisten setelah tombol ditekan.")
