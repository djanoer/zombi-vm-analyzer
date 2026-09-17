# ==============================================================================
#  🧟 ZOMBIE VM ANALYZER v4.0 — MODULE: constants.py
# ------------------------------------------------------------------------------
#  Lokasi : app/constants.py
#  Peran  : Sumber konfigurasi kolom, threshold, bobot, dan aturan aplikasi.
# ------------------------------------------------------------------------------
#  UPDATE (15 Sep 2026):
#  - Aturan tambahan hanya memakai Days Powered Off.
#  - Threshold CPU/Network tambahan Zombie dihapus karena metrik utama P95
#    sudah digunakan untuk kandidat dan Skor Idle.
#  - Downsize sudah dihapus.
# ==============================================================================

REQUIRED_COLUMNS_BASE = [
    "Name", "State", "Uptime / Days", "Summary|vSphere Tag",
    "CPU Percentile 95%", "IOPS Percentile 95%",
    "Throughput Percentile 95%",
    "Network I/O | Usage Rate (KBps) - 95th Percentile", "Status Idle",
]

MEMORY_COL_CANDIDATES = ["Memort Percentile 95%", "Memory Percentile 95%"]

OPTIONAL_COLUMNS = [
    "vCPU", "Memory (GB)", "Provisioned Space (GB)", "Provisioned Space (TB)",
]

NUMERIC_COLUMNS_BASE = [
    "Uptime / Days", "CPU Percentile 95%", "IOPS Percentile 95%",
    "Throughput Percentile 95%",
    "Network I/O | Usage Rate (KBps) - 95th Percentile", "Status Idle",
    "Utilization CPU (%)", "vCPU", "Memory (GB)",
    "Provisioned Space (GB)", "Provisioned Space (TB)",
]

INACTIVE_STATE_KEYWORDS = ["off", "disconnect", "suspend", "invalid", "orphan"]
UPTIME_UNKNOWN_TOKENS = ["-", "", "nan", "NaN", "None"]

# ==============================================================================
# UPDATE (16 Sep 2026): Threshold disesuaikan dengan distribusi data aktual
# - Berdasarkan analisis 2929 VM dari vROps export
# - False positive rate target: < 10% untuk environment banking
# - Referensi: analyze_distribution_detailed.py (tools folder)
# ==============================================================================

THRESHOLD_PRESETS = {
    # Ultra Conservative: False positive < 5% — Sangat aman untuk production critical
    "Ultra Konservatif (False Positive < 5%)": {
        "cpu": 0.5, "iops": 1.5, "throughput": 0.07, "network": 30
    },
    # Conservative: False positive < 10% — REKOMENDASI untuk banking
    "Konservatif (False Positive < 10%) — REKOMENDASI": {
        "cpu": 0.8, "iops": 2.0, "throughput": 0.10, "network": 50
    },
    # Moderate: False positive ~15% — Coverage lebih tinggi
    "Moderat (False Positive ~15%)": {
        "cpu": 1.5, "iops": 3.0, "throughput": 0.15, "network": 75
    },
    # Aggressive: False positive ~20% — Hanya untuk non-production
    "Agresif (False Positive ~20%)": {
        "cpu": 2.5, "iops": 5.0, "throughput": 0.25, "network": 100
    },
}

# Default custom threshold — REKOMENDASI untuk penggunaan umum
DEFAULT_CUSTOM_THRESHOLD = {"cpu": 0.8, "iops": 2.0, "throughput": 0.10, "network": 50}

SCORE_WEIGHTS = {
    "cpu": 20,
    "iops": 25,
    "throughput": 25,
    "network": 15,
    "status_idle": 15,
}

DEFAULT_MIN_CONSISTENT_PERIODS = 3
DEFAULT_DISPOSAL_OFF_DAYS = 30

# ==============================================================================
# ALIAS & MAPPING KOLOM (POWER OFF & PIC)
# ==============================================================================
POWER_OFF_REQUIRED_COLUMNS = [
    "Name",
    "Power State",
    "Days Powered Off",
    "UUID",
]

POWER_OFF_COLUMN_ALIASES = {
    "Power Off Days": "Days Powered Off",
    "Days Power Off": "Days Powered Off",
    "Days Powered Off": "Days Powered Off",
}

PIC_COLUMN_ALIASES = {
    "nama vm": "Name", "virtual machine": "Name", "vm name": "Name", "name": "Name",
    "uuid": "UUID", "vm uuid": "UUID", "instance uuid": "UUID",
    "pic": "PIC Owner", "owner": "PIC Owner", "pemilik": "PIC Owner",
    "pic owner": "PIC Owner", "application owner": "PIC Owner"
}
