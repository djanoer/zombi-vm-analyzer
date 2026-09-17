# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: filter_settings.py
# ==============================================================================
"""
Module untuk save/load filter settings.
FIX (17 Sep 2026):
- Tambah tag_filter_input ke save/load settings
- Auto-load filter saat aplikasi start
"""

import json
from pathlib import Path
from app_config import DATA_DIRECTORY


FILTER_SETTINGS_PATH = DATA_DIRECTORY / "filter_settings.json"


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


def load_filter_settings():
    """Load filter settings dari JSON."""
    # Ensure directory exists
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

    if not FILTER_SETTINGS_PATH.exists():
        return DEFAULT_SETTINGS.copy(), None

    try:
        with FILTER_SETTINGS_PATH.open("r", encoding="utf-8") as file:
            saved = json.load(file)

        settings = DEFAULT_SETTINGS.copy()
        settings.update(saved)

        # Clean deprecated keys
        deprecated_keys = [
            "memory_high", "memory_low", "downsize_vcpu_threshold",
            "downsize_cpu_util_threshold", "zombie_cpu_util_threshold",
            "zombie_network_threshold"
        ]
        for key in deprecated_keys:
            settings.pop(key, None)

        return settings, None

    except (OSError, json.JSONDecodeError) as error:
        return DEFAULT_SETTINGS.copy(), str(error)


def save_filter_settings(settings):
    """Save filter settings ke JSON."""
    # Ensure directory exists
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Clean settings (hapus deprecated keys)
    clean_settings = dict(settings)
    deprecated_keys = [
        "memory_high", "memory_low", "downsize_vcpu_threshold",
        "downsize_cpu_util_threshold", "zombie_cpu_util_threshold",
        "zombie_network_threshold"
    ]
    for key in deprecated_keys:
        clean_settings.pop(key, None)

    try:
        with FILTER_SETTINGS_PATH.open("w", encoding="utf-8") as file:
            json.dump(clean_settings, file, ensure_ascii=False, indent=2)
        return True, None

    except OSError as error:
        return False, str(error)


def reset_filter_settings():
    """Reset filter settings ke default."""
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

    try:
        if FILTER_SETTINGS_PATH.exists():
            FILTER_SETTINGS_PATH.unlink()
        return True, None

    except OSError as error:
        return False, str(error)
