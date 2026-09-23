# ==============================================================================
#  🧟 ZOMBIE VM ANALYZER v4.0 — MODULE: constants.py
# ------------------------------------------------------------------------------
#  Lokasi : app/constants.py
#  Peran  : Sumber konfigurasi kolom, threshold, bobot, dan aturan aplikasi.
# ------------------------------------------------------------------------------
#  PATCH NOTES v5 (24 Sep 2026):
#  - Ditambahkan alias eksplisit "Parent vCenter" -> "vCenter" (file
#    Power Off kedua memakai nama ini, TANPA prefix "Summary|").
#  - Alias literal di sini hanya lapis PERTAMA. data_loader.py sekarang
#    juga memiliki fallback AUTO-DETECT: jika tidak ada alias yang cocok
#    tapi ada TEPAT SATU kolom yang mengandung kata "vcenter", kolom itu
#    otomatis dipetakan ke "vCenter" (dengan info ke pengguna). Ini
#    mengantisipasi variasi nama kolom dari tool export yang berbeda-beda
#    tanpa perlu terus menambah alias literal satu per satu.
# ==============================================================================


REQUIRED_COLUMNS_BASE = [
    "Name", "vCenter", "State", "Uptime / Days", "Summary|vSphere Tag",
    "CPU Percentile 95%", "IOPS Percentile 95%",
    "Throughput Percentile 95%",
    "Network I/O | Usage Rate (KBps) - 95th Percentile", "Status Idle",
]


MEMORY_COL_CANDIDATES = [
    "Memory Percentile 95%",
    "Memort Percentile 95%",
]


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


INACTIVE_STATE_KEYWORDS = [
    "off", "disconnect", "suspend", "inactive", "invalid", "orphan",
]
UPTIME_UNKNOWN_TOKENS = ["-", "", "nan", "NaN", "None"]


THRESHOLD_PRESETS = {
    "Ultra Konservatif (False Positive < 5%)": {
        "cpu": 0.5, "iops": 1.5, "throughput": 0.07, "network": 30
    },
    "Konservatif (False Positive < 10%) — REKOMENDASI": {
        "cpu": 0.8, "iops": 2.0, "throughput": 0.10, "network": 50
    },
    "Moderat (False Positive ~15%)": {
        "cpu": 1.5, "iops": 3.0, "throughput": 0.15, "network": 75
    },
    "Agresif (False Positive ~20%)": {
        "cpu": 2.5, "iops": 5.0, "throughput": 0.25, "network": 100
    },
}


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
    "vCenter",
]

POWER_OFF_OPTIONAL_COLUMNS = [
    "UUID",
]

# PATCH v5: alias literal untuk variasi nama kolom yang SUDAH DIKETAHUI.
# Untuk variasi yang BELUM diketahui, data_loader.py memiliki fallback
# auto-detect berbasis kata kunci "vcenter" (lihat normalize_power_off_columns).
POWER_OFF_COLUMN_ALIASES = {
    "Power Off Days": "Days Powered Off",
    "Days Power Off": "Days Powered Off",
    "Days Powered Off": "Days Powered Off",
    "Summary|Parent vCenter": "vCenter",
    "Parent vCenter": "vCenter",
}


PIC_COLUMN_ALIASES = {
    "nama vm": "Name", "virtual machine": "Name", "vm name": "Name", "name": "Name",
    "uuid": "UUID", "vm uuid": "UUID", "instance uuid": "UUID",
    "vcenter": "vCenter", "virtual center": "vCenter", "vc": "vCenter",
    "pic": "PIC Owner", "owner": "PIC Owner", "pemilik": "PIC Owner",
    "pic owner": "PIC Owner", "application owner": "PIC Owner"
}


# ==============================================================================
# KONFIGURASI TREND OBSERVASI AKTUAL
# ==============================================================================


TREND_METRIC_WINDOW_DEFAULT = "Relative last month"
TREND_SNAPSHOT_SOURCE_DEFAULT = "vROps"


TREND_LEGACY_CANDIDATE_COLUMN = (
    "is_kandidat_disposal"
)


TREND_ACTIONABLE_LABELS = (
    "Kandidat Zombie",
    "Kandidat Disposal",
)


# ==============================================================================
# KONFIGURASI IDENTITY (vCenter + UUID)
# ==============================================================================

IDENTITY_KEY_SEPARATOR = "::"

IDENTITY_INVALID_TOKENS = [
    "",
    "-",
    "nan",
    "none",
    "null",
    "<na>",
]

LEGACY_IDENTITY_PREFIX = "LEGACY::NAME::"

MASTER_IDENTITY_COLUMNS = [
    "Name",
    "vCenter",
    "UUID",
    "Identity Key",
]


# ==============================================================================
# KONTRAK KOLOM HASIL ANALISIS (analysis.py)
# ==============================================================================

CANDIDATE_COLUMN = "Is Kandidat Zombie"
SCORE_COLUMN = "Skor Idle (0-100)"
JUSTIFICATION_COLUMN = "Status Justifikasi"
