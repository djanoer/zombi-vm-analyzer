# ==============================================================================
# ZOMBIE VM ANALYZER — MODULE: analysis.py
# ------------------------------------------------------------------------------
# PATCH NOTES (21 Sep 2026):
# - CANDIDATE_COLUMN, SCORE_COLUMN, JUSTIFICATION_COLUMN kini diimpor dari
#   constants.py (satu-satunya sumber kebenaran), bukan didefinisikan
#   ulang secara lokal. Ini mencegah drift antara analysis.py dan main.py
#   yang keduanya memakai nama kolom yang sama secara hardcode terpisah.
# - Ditambahkan validasi defensif: run_zombie_analysis() menolak input
#   yang berisi baris Powered Off (mengandalkan identity_utils sebagai
#   sumber tunggal deteksi status non-aktif). Ini adalah safety-net agar
#   VM Powered Off tidak pernah diberi Skor Idle hasil pengukuran yang
#   dapat disalahartikan sebagai hasil analisis idle sungguhan.
# - TIDAK ADA perubahan pada formula scoring, bobot (SCORE_WEIGHTS), atau
#   logika threshold gating (is_zombie_candidate). Perilaku bisnis 100%
#   dipertahankan sesuai batasan project.
# ==============================================================================


import pandas as pd


from constants import (
    CANDIDATE_COLUMN,
    JUSTIFICATION_COLUMN,
    MEMORY_COL_CANDIDATES,
    SCORE_COLUMN,
    SCORE_WEIGHTS,
)
from identity_utils import is_powered_off_series


CPU_COLUMN = "CPU Percentile 95%"
IOPS_COLUMN = "IOPS Percentile 95%"
THROUGHPUT_COLUMN = "Throughput Percentile 95%"
NETWORK_COLUMN = "Network I/O | Usage Rate (KBps) - 95th Percentile"
STATUS_IDLE_COLUMN = "Status Idle"
UPTIME_COLUMN = "Uptime / Days"



def _number(value, default=0.0):
    parsed = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(parsed) else float(parsed)



def _format_number(value, decimals=2):
    number = _number(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.{decimals}f}".rstrip("0").rstrip(".")



def _format_uptime(row):
    if row.get("Kualitas Data") == "Tidak Diketahui":
        return "Uptime tidak diketahui"
    uptime = row.get(UPTIME_COLUMN)
    return f"Uptime {_format_number(uptime, 0)} hari"



def is_zombie_candidate(row, max_cpu, max_iops, max_throughput, max_network):
    """
    Aturan gating kandidat zombie. TIDAK DIUBAH dari versi sebelumnya --
    hanya membandingkan 4 metrik terhadap threshold, tanpa syarat
    tambahan (mis. Skor Idle minimum) yang tidak disepakati.
    """
    return (
        _number(row.get(CPU_COLUMN)) <= max_cpu
        and _number(row.get(IOPS_COLUMN)) <= max_iops
        and _number(row.get(THROUGHPUT_COLUMN)) <= max_throughput
        and _number(row.get(NETWORK_COLUMN)) <= max_network
    )



def score_components(row, max_cpu, max_iops, max_throughput, max_network):
    """Formula & bobot TIDAK DIUBAH dari versi sebelumnya."""
    safe_cpu = max(float(max_cpu), 0.1)
    safe_iops = max(float(max_iops), 0.1)
    safe_throughput = max(float(max_throughput), 0.1)
    safe_network = max(float(max_network), 0.1)


    cpu = _number(row.get(CPU_COLUMN))
    iops = _number(row.get(IOPS_COLUMN))
    throughput = _number(row.get(THROUGHPUT_COLUMN))
    network = _number(row.get(NETWORK_COLUMN))
    status_idle = 1 if _number(row.get(STATUS_IDLE_COLUMN)) == 1 else 0


    components = {
        "cpu": max(0.0, 1 - cpu / safe_cpu) * SCORE_WEIGHTS["cpu"],
        "iops": max(0.0, 1 - iops / safe_iops) * SCORE_WEIGHTS["iops"],
        "throughput": max(0.0, 1 - throughput / safe_throughput) * SCORE_WEIGHTS["throughput"],
        "network": max(0.0, 1 - network / safe_network) * SCORE_WEIGHTS["network"],
        "status_idle": status_idle * SCORE_WEIGHTS["status_idle"],
    }
    components["total"] = sum(components.values())
    return components



def calculate_zombie_score(row, max_cpu, max_iops, max_throughput, max_network):
    components = score_components(row, max_cpu, max_iops, max_throughput, max_network)
    return round(components["total"], 2)



def _failed_metrics(row, max_cpu, max_iops, max_throughput, max_network):
    failures = []
    cpu = _number(row.get(CPU_COLUMN))
    iops = _number(row.get(IOPS_COLUMN))
    throughput = _number(row.get(THROUGHPUT_COLUMN))
    network = _number(row.get(NETWORK_COLUMN))


    if cpu > max_cpu:
        failures.append(f"CPU P95 {_format_number(cpu)}% > {_format_number(max_cpu)}%")
    if iops > max_iops:
        failures.append(f"IOPS P95 {_format_number(iops)} > {_format_number(max_iops)}")
    if throughput > max_throughput:
        failures.append(f"throughput P95 {_format_number(throughput)} > {_format_number(max_throughput)}")
    if network > max_network:
        failures.append(f"network P95 {_format_number(network)} KBps > {_format_number(max_network)} KBps")
    return failures



def generate_justification(row, max_cpu, max_iops, max_throughput, max_network):
    state = str(row.get("State", "Unknown")).strip()
    uptime_text = _format_uptime(row)
    cpu = _number(row.get(CPU_COLUMN))
    iops = _number(row.get(IOPS_COLUMN))
    throughput = _number(row.get(THROUGHPUT_COLUMN))
    network = _number(row.get(NETWORK_COLUMN))


    memory = None
    for col in MEMORY_COL_CANDIDATES:
        val = row.get(col)
        if val is not None and not pd.isna(val):
            memory = val
            break


    status_idle = int(_number(row.get(STATUS_IDLE_COLUMN)))
    candidate = bool(row.get(CANDIDATE_COLUMN, False))


    base = (
        f"VM berstatus {state} dengan {uptime_text}, "
        f"beban CPU ({_format_number(cpu)}%), "
        f"IOPS ({_format_number(iops)}), dan throughput "
        f"({_format_number(throughput)})"
    )


    if candidate:
        components = score_components(row, max_cpu, max_iops, max_throughput, max_network)
        ram_text = f", dan penggunaan RAM sangat rendah ({_format_number(memory)}%)" if memory is not None else ""
        return (
            f"{base} sangat rendah{ram_text}, "
            f"serta network {_format_number(network)} KBps. "
            f"Status Idle={status_idle}; Skor Idle={components['total']:.2f}/100."
        )


    failures = _failed_metrics(row, max_cpu, max_iops, max_throughput, max_network)
    ram_text = f", RAM ({_format_number(memory)}%)" if memory is not None else ""


    if failures:
        return f"{base}{ram_text}. Namun tidak menjadi kandidat karena {'; '.join(failures)}."


    return f"{base}{ram_text}. VM tidak ditandai oleh aturan bisnis tambahan."



def run_zombie_analysis(dataframe, max_cpu, max_iops, max_throughput, max_network):
    """
    PATCH: Validasi defensif ditambahkan di awal fungsi -- menolak input
    yang mengandung baris Powered Off. Analisis zombie HANYA berlaku
    untuk VM Power On; VM Power Off dievaluasi lewat jalur disposal
    (disposal_rules.py), tidak lewat sini. Ini mencegah Skor Idle hasil
    pengukuran keliru muncul untuk VM yang seharusnya tidak dianalisis,
    seandainya suatu saat ada refactor caller yang lupa memfilter State.
    """
    if "State" in dataframe.columns:
        powered_off_mask = is_powered_off_series(dataframe)
        if powered_off_mask.any():
            offending_names = (
                dataframe.loc[powered_off_mask, "Name"].head(10).tolist()
                if "Name" in dataframe.columns
                else []
            )
            raise ValueError(
                "run_zombie_analysis() menerima baris berstatus Powered "
                "Off. Analisis zombie hanya boleh dijalankan pada VM "
                "Power On; VM Power Off harus difilter oleh caller "
                "sebelum memanggil fungsi ini. "
                f"Contoh VM bermasalah: {offending_names}"
            )


    result = dataframe.copy()
    result[CANDIDATE_COLUMN] = result.apply(
        lambda row: is_zombie_candidate(
            row, max_cpu, max_iops, max_throughput, max_network
        ),
        axis=1,
    )
    result[SCORE_COLUMN] = 0.0
    mask = result[CANDIDATE_COLUMN]
    if mask.any():
        result.loc[mask, SCORE_COLUMN] = result.loc[mask].apply(
            lambda row: calculate_zombie_score(
                row, max_cpu, max_iops, max_throughput, max_network
            ),
            axis=1,
        )
    result[JUSTIFICATION_COLUMN] = result.apply(
        lambda row: generate_justification(
            row, max_cpu, max_iops, max_throughput, max_network
        ),
        axis=1,
    )
    candidates = result.loc[mask].copy().sort_values(
        SCORE_COLUMN, ascending=False
    )
    return result, candidates
