# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: filter_settings.py
# ==============================================================================
"""
Module untuk save/load filter settings.

FIX (17 Sep 2026):
- Tambah tag_filter_input ke save/load settings
- Auto-load filter saat aplikasi start

PATCH NOTES (24 Sep 2026):
- FILTER_SETTINGS_PATH tidak lagi didefinisikan ulang secara lokal --
  diimpor dari app_config.py (satu-satunya sumber kebenaran untuk path
  file data, konsisten dengan STATUS_DATABASE_PATH/TREND_DATABASE_PATH).
- DATA_DIRECTORY.mkdir(...) yang diulang 3x diganti memanggil
  ensure_data_directory() dari app_config.py.
- Daftar deprecated_keys yang diduplikasi di load & save digabung
  menjadi satu konstanta modul DEPRECATED_SETTING_KEYS.
- TIDAK ADA perubahan pada perilaku/kontrak DEFAULT_SETTINGS -- seluruh
  kunci tetap identik dan sudah diverifikasi cocok dengan
  sidebar_controls.py dan main.py.
"""


import json

from app_config import FILTER_SETTINGS_PATH, ensure_data_directory


DEFAULT_SETTINGS = {
    "selected_states": [],
    "preset_mode": "Konservatif (False Positive < 10%) — REKOMENDASI",
    "max_cpu": 0.8,
    "max_iops": 2.0,
    "max_throughput": 0.10,
    "max_network": 50,
    "min_consistent_periods": 3,
    "min_uptime": 14,
    "max_uptime": None,
    "min_off_days": 30,
    "tag_filter_input": [],
}


DEPRECATED_SETTING_KEYS = [
    "memory_high",
    "memory_low",
    "downsize_vcpu_threshold",
    "downsize_cpu_util_threshold",
    "zombie_cpu_util_threshold",
    "zombie_network_threshold",
]


def load_filter_settings():
    """Load filter settings dari JSON."""
    ensure_data_directory()

    if not FILTER_SETTINGS_PATH.exists():
        return DEFAULT_SETTINGS.copy(), None

    try:
        with FILTER_SETTINGS_PATH.open("r", encoding="utf-8") as file:
            saved = json.load(file)

        settings = DEFAULT_SETTINGS.copy()
        settings.update(saved)

        for key in DEPRECATED_SETTING_KEYS:
            settings.pop(key, None)

        return settings, None

    except (OSError, json.JSONDecodeError) as error:
        return DEFAULT_SETTINGS.copy(), str(error)


def save_filter_settings(settings):
    """Save filter settings ke JSON."""
    ensure_data_directory()

    clean_settings = dict(settings)
    for key in DEPRECATED_SETTING_KEYS:
        clean_settings.pop(key, None)

    try:
        with FILTER_SETTINGS_PATH.open("w", encoding="utf-8") as file:
            json.dump(clean_settings, file, ensure_ascii=False, indent=2)
        return True, None

    except OSError as error:
        return False, str(error)


def reset_filter_settings():
    """Reset filter settings ke default."""
    ensure_data_directory()

    try:
        if FILTER_SETTINGS_PATH.exists():
            FILTER_SETTINGS_PATH.unlink()
        return True, None

    except OSError as error:
        return False, str(error)
