# ==============================================================================
# ZOMBIE VM ANALYZER — MODULE: analysis.py
# ============================================================================

import pandas as pd

from constants import SCORE_WEIGHTS, MEMORY_COL_CANDIDATES

CPU_COLUMN = "CPU Percentile 95%"
IOPS_COLUMN = "IOPS Percentile 95%"
THROUGHPUT_COLUMN = "Throughput Percentile 95%"
NETWORK_COLUMN = "Network I/O | Usage Rate (KBps) - 95th Percentile"
STATUS_IDLE_COLUMN = "Status Idle"
UPTIME_COLUMN = "Uptime / Days"
SCORE_COLUMN = "Skor Idle (0-100)"

# FIX (Hierarki Label): Ubah nama agar tidak menimpa hasil Disposal
CANDIDATE_COLUMN = "Is Kandidat Zombie"
JUSTIFICATION_COLUMN = "Status Justifikasi"


def _number(value, default=0.0):
    parsed = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(parsed) else float(parsed)


def _format_number(value, decimals=2):
    number = _number(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.{decimals}f}".rstrip("0").rstrip(".")


def _format_uptime(row):
    # FIX BUG #3: Gunakan flag 'Kualitas Data' yang belum terhapus parser numerik
    if row.get("Kualitas Data") == "Tidak Diketahui":
        return "Uptime tidak diketahui"
    uptime = row.get(UPTIME_COLUMN)
    return f"Uptime {_format_number(uptime, 0)} hari"


def is_zombie_candidate(row, max_cpu, max_iops, max_throughput, max_network):
    return (
        _number(row.get(CPU_COLUMN)) <= max_cpu
        and _number(row.get(IOPS_COLUMN)) <= max_iops
        and _number(row.get(THROUGHPUT_COLUMN)) <= max_throughput
        and _number(row.get(NETWORK_COLUMN)) <= max_network
    )


def score_components(row, max_cpu, max_iops, max_throughput, max_network):
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

    # FIX: Cari kolom Memory secara dinamis mendukung toleransi typo (vROps)
    memory = None
    for col in MEMORY_COL_CANDIDATES:
        val = row.get(col)
        if val is not None and not pd.isna(val):
            memory = val
            break

    status_idle = int(_number(row.get(STATUS_IDLE_COLUMN)))
    candidate = bool(row.get(CANDIDATE_COLUMN, False))

    # FIX BUG #2: Base netral, hindari mencantumkan "sangat rendah" tanpa syarat
    base = (
        f"VM berstatus {state} dengan {uptime_text}, "
        f"beban CPU ({_format_number(cpu)}%), "
        f"IOPS ({_format_number(iops)}), dan throughput "
        f"({_format_number(throughput)})"
    )

    if candidate:
        components = score_components(row, max_cpu, max_iops, max_throughput, max_network)
        # FIX BUG #5: Kalimat menyatu secara logis
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
