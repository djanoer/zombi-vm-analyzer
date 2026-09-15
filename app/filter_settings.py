# ==============================================================================
#  🧟 ZOMBIE VM ANALYZER v4.0 — MODULE: filter_settings.py
# ------------------------------------------------------------------------------
#  UPDATE: Aturan tambahan hanya menyimpan threshold Days Powered Off.
#  Threshold Zombie CPU/Network tambahan dan Downsize dihapus.
# ==============================================================================
import json
from app_config import FILTER_SETTINGS_PATH, ensure_data_directory

# ==============================================================================
# UPDATE (16 Sep 2026): Default threshold disesuaikan dengan distribusi data
# - Berdasarkan analisis 2929 VM dari vROps export
# - False positive rate target: < 10% untuk environment banking
# - Threshold default: CPU ≤ 0.8%, IOPS ≤ 2.0, Throughput ≤ 0.10 KBps
# ==============================================================================

DEFAULT_SETTINGS = {
    "selected_states": [],
    "preset_mode": "Konservatif (False Positive < 10%) — REKOMENDASI",

    # Threshold default — REKOMENDASI untuk banking environment
    "max_cpu": 0.8,        # CPU P95 ≤ 0.8% (P25 = 0.83 dari distribusi)
    "max_iops": 2.0,       # IOPS P95 ≤ 2.0 (P25 = 2.13 dari distribusi)
    "max_throughput": 0.10,  # Throughput P95 ≤ 0.10 KBps (P25 = 0.08 dari distribusi)
    "max_network": 50,     # Network P95 ≤ 50 KBps (conservative default)

    "min_consistent_periods": 3,
    "min_uptime": 14,      # Exclude VM baru deploy (< 14 hari)
    "max_uptime": None,
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


def reset_filter_settings():
    ensure_data_directory()
    try:
        if FILTER_SETTINGS_PATH.exists():
            FILTER_SETTINGS_PATH.unlink() # Menghapus file JSON
        return True, None
    except OSError as error:
        return False, str(error)
