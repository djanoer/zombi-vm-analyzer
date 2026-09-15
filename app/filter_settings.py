# ==============================================================================
#  🧟 ZOMBIE VM ANALYZER v4.0 — MODULE: filter_settings.py
# ------------------------------------------------------------------------------
#  UPDATE: Aturan tambahan hanya menyimpan threshold Days Powered Off.
#  Threshold Zombie CPU/Network tambahan dan Downsize dihapus.
# ==============================================================================
import json
from app_config import FILTER_SETTINGS_PATH, ensure_data_directory

DEFAULT_SETTINGS = {
    "selected_states": [], "preset_mode": "Custom (Atur Manual)",
    "max_cpu": 3.0, "max_iops": 5.0, "max_throughput": 10.0, "max_network": 10.0,
    "min_consistent_periods": 3, "min_uptime": None, "max_uptime": None,
    "min_off_days": 30,
}

def load_filter_settings():
    ensure_data_directory()
    if not FILTER_SETTINGS_PATH.exists():
        return DEFAULT_SETTINGS.copy(), None
    try:
        with FILTER_SETTINGS_PATH.open("r", encoding="utf-8") as file:
            saved = json.load(file)
        settings = DEFAULT_SETTINGS.copy()
        settings.update(saved)
        for key in ["memory_high", "memory_low", "downsize_vcpu_threshold", "downsize_cpu_util_threshold", "zombie_cpu_util_threshold", "zombie_network_threshold"]:
            settings.pop(key, None)
        return settings, None
    except (OSError, json.JSONDecodeError) as error:
        return DEFAULT_SETTINGS.copy(), str(error)

def save_filter_settings(settings):
    ensure_data_directory()
    clean_settings = dict(settings)
    for key in ["memory_high", "memory_low", "downsize_vcpu_threshold", "downsize_cpu_util_threshold", "zombie_cpu_util_threshold", "zombie_network_threshold"]:
        clean_settings.pop(key, None)
    try:
        with FILTER_SETTINGS_PATH.open("w", encoding="utf-8") as file:
            json.dump(clean_settings, file, ensure_ascii=False, indent=2)
        return True, None
    except OSError as error:
        return False, str(error)
