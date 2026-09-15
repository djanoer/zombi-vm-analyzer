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

THRESHOLD_PRESETS = {
    "Konservatif (Pasti Idle)": {"cpu": 1.0, "iops": 2.0, "throughput": 5.0, "network": 10.0},
    "Agresif (Lebih Banyak Kandidat)": {"cpu": 5.0, "iops": 15.0, "throughput": 20.0, "network": 25.0},
}

DEFAULT_CUSTOM_THRESHOLD = {"cpu": 3.0, "iops": 5.0, "throughput": 10.0, "network": 10.0}

SCORE_WEIGHTS = {
    "cpu": 20,
    "iops": 25,
    "throughput": 25,
    "network": 15,
    "status_idle": 15,
}

DEFAULT_MIN_CONSISTENT_PERIODS = 3
DEFAULT_DISPOSAL_OFF_DAYS = 30
