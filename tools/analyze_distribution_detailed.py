#!/usr/bin/env python3
"""
ZOMBIE VM ANALYZER — TOOL: analyze_distribution_detailed.py

Peran:
- Menganalisis distribusi metrik VM untuk diagnosis.
- Membantu memahami mengapa kandidat zombie terlalu banyak,
  terlalu sedikit, atau nol.
- Tidak mengubah database.
- Tidak menjalankan Streamlit.
- Tidak mengubah hasil aplikasi utama.

Kontrak angka:
- Titik (.) = desimal.
- Koma (,) = pemisah ribuan jika muncul bersama titik.
- Satuan seperti %, KBps, ms, dan μs dihapus saat parsing.

Penggunaan:
    python tools/analyze_distribution_detailed.py file.csv

Dengan separator eksplisit:
    python tools/analyze_distribution_detailed.py file.csv --sep ","

Dengan output CSV diagnosis:
    python tools/analyze_distribution_detailed.py file.csv \
        --output diagnosis.csv
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd


CPU_COLUMN = "CPU Percentile 95%"
IOPS_COLUMN = "IOPS Percentile 95%"
THROUGHPUT_COLUMN = "Throughput Percentile 95%"
NETWORK_COLUMN = (
    "Network I/O | Usage Rate (KBps) - 95th Percentile"
)
STATE_COLUMN = "State"
NAME_COLUMN = "Name"

ANALYSIS_COLUMNS = {
    "cpu": CPU_COLUMN,
    "iops": IOPS_COLUMN,
    "throughput": THROUGHPUT_COLUMN,
    "network": NETWORK_COLUMN,
}

DEFAULT_TEST_CASES = [
    {
        "cpu": 0.5,
        "iops": 1.5,
        "throughput": 0.07,
        "network": 30.0,
        "name": "ULTRA KONSERVATIF",
    },
    {
        "cpu": 0.8,
        "iops": 2.0,
        "throughput": 0.10,
        "network": 50.0,
        "name": "KONSERVATIF",
    },
    {
        "cpu": 1.5,
        "iops": 3.0,
        "throughput": 0.15,
        "network": 75.0,
        "name": "MODERAT",
    },
    {
        "cpu": 2.5,
        "iops": 5.0,
        "throughput": 0.25,
        "network": 100.0,
        "name": "AGRESIF",
    },
    {
        "cpu": 5.0,
        "iops": 10.0,
        "throughput": 0.50,
        "network": 250.0,
        "name": "SANGAT AGRESIF",
    },
    {
        "cpu": 10.0,
        "iops": 20.0,
        "throughput": 1.00,
        "network": 500.0,
        "name": "EKSTREM",
    },
]


def parse_numeric(value):
    """
    Parse angka sesuai format data aplikasi.

    Contoh:
        1,428.36   -> 1428.36
        1,641      -> 1641.0
        0.0001     -> 0.0001
        904.63 μs  -> 904.63
        -          -> NaN
    """
    if value is None or pd.isna(value):
        return np.nan

    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)

    value_string = str(value).strip()

    if value_string.lower() in {
        "",
        "-",
        "nan",
        "none",
        "null",
    }:
        return np.nan

    cleaned = re.sub(
        r"[^0-9,.\-]",
        "",
        value_string,
    )

    if not cleaned or cleaned == "-":
        return np.nan

    has_comma = "," in cleaned
    has_dot = "." in cleaned

    if has_comma and has_dot:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = (
                cleaned.replace(".", "")
                .replace(",", ".")
            )
        else:
            cleaned = cleaned.replace(",", "")

    elif has_dot:
        # Format project: titik selalu desimal.
        pass

    elif has_comma:
        groups = cleaned.split(",")
        is_thousands = (
            len(groups) > 1
            and all(len(group) == 3 for group in groups[1:])
        )

        if is_thousands:
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(",", ".")

    try:
        return float(cleaned)
    except ValueError:
        return np.nan


def read_csv_robust(csv_path, separator=None):
    if separator:
        return pd.read_csv(
            csv_path,
            sep=separator,
            engine="python",
            encoding="utf-8-sig",
        )

    candidates = []

    for encoding in [
        "utf-8-sig",
        "utf-8",
        "latin1",
    ]:
        for sep in [",", ";", "\t"]:
            try:
                dataframe = pd.read_csv(
                    csv_path,
                    sep=sep,
                    engine="python",
                    encoding=encoding,
                )

                if dataframe.shape[1] > 1:
                    candidates.append(
                        (
                            dataframe.shape[1],
                            dataframe,
                            encoding,
                            sep,
                        )
                    )
            except (
                UnicodeDecodeError,
                pd.errors.EmptyDataError,
                pd.errors.ParserError,
            ):
                continue

    if not candidates:
        raise ValueError(
            "CSV tidak dapat dibaca sebagai beberapa kolom."
        )

    _, dataframe, encoding, sep = max(
        candidates,
        key=lambda item: item[0],
    )

    print(
        f"[INFO] CSV dibaca dengan encoding={encoding!r}, "
        f"separator={sep!r}, kolom={len(dataframe.columns)}"
    )

    return dataframe


def normalize_columns(dataframe):
    result = dataframe.copy()

    result.columns = [
        re.sub(
            r"\s+",
            " ",
            str(column)
            .replace("\ufeff", "")
            .replace("\xa0", " ")
            .strip(),
        )
        for column in result.columns
    ]

    return result


def validate_required_columns(dataframe):
    required_columns = list(
        ANALYSIS_COLUMNS.values()
    )

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            "Kolom metrik wajib tidak ditemukan: "
            + ", ".join(missing_columns)
        )


def prepare_metric_dataframe(dataframe):
    result = dataframe.copy()

    for metric_column in ANALYSIS_COLUMNS.values():
        result[metric_column] = result[
            metric_column
        ].apply(parse_numeric)

    return result


def print_metric_summary(dataframe, metric_name, column):
    series = dataframe[column].dropna()

    print(f"\n{metric_name}:")

    if series.empty:
        print("  Count: 0")
        print("  Tidak ada nilai numerik yang valid.")
        return

    print(f"  Count: {len(series)}")
    print(f"  Min: {series.min():.6f}")
    print(f"  Max: {series.max():.6f}")
    print(f"  Mean: {series.mean():.6f}")
    print(f"  Median: {series.median():.6f}")

    print("\n  Percentiles:")

    for percentile in [
        1,
        5,
        10,
        15,
        20,
        25,
        30,
        40,
        50,
    ]:
        value = series.quantile(
            percentile / 100
        )
        print(
            f"    P{percentile:2d}: "
            f"{value:.6f}"
        )


def get_thresholds(metric_name):
    if metric_name == "CPU P95":
        return [
            0.3,
            0.5,
            0.8,
            1.0,
            1.5,
            2.0,
            2.5,
            5.0,
            10.0,
        ]

    if metric_name == "IOPS P95":
        return [
            0.5,
            1.0,
            1.5,
            2.0,
            3.0,
            5.0,
            10.0,
            20.0,
            50.0,
        ]

    if metric_name == "Throughput P95":
        return [
            0.01,
            0.02,
            0.05,
            0.07,
            0.10,
            0.15,
            0.20,
            0.25,
            0.50,
            1.0,
        ]

    return [
        10.0,
        20.0,
        30.0,
        50.0,
        75.0,
        100.0,
        250.0,
        500.0,
    ]


def print_threshold_summary(
    dataframe,
    metric_name,
    column,
):
    series = dataframe[column].dropna()

    print("\n  VM di bawah threshold:")

    if series.empty:
        print("    Tidak ada data numerik valid.")
        return

    for threshold in get_thresholds(metric_name):
        count = int((series <= threshold).sum())
        percentage = count / len(series) * 100

        print(
            f"    ≤ {threshold:8.2f}: "
            f"{count:6d} VM "
            f"({percentage:6.1f}%)"
        )


def build_complete_metric_dataframe(dataframe):
    metric_columns = list(
        ANALYSIS_COLUMNS.values()
    )

    result = dataframe.dropna(
        subset=metric_columns
    ).copy()

    return result


def print_combination_analysis(dataframe):
    print("\n" + "=" * 80)
    print("ANALISIS KOMBINASI (AND LOGIC)")
    print("=" * 80)

    complete_dataframe = (
        build_complete_metric_dataframe(dataframe)
    )

    total = len(complete_dataframe)

    print(
        f"\nTotal VM dengan data lengkap untuk "
        f"4 metrik analisis: {total}"
    )

    if total == 0:
        print(
            "Tidak ada VM dengan data lengkap. "
            "Kombinasi threshold tidak dapat dihitung."
        )
        return pd.DataFrame()

    print(
        f"\n{'Scenario':<25} "
        f"{'CPU':>8} "
        f"{'IOPS':>8} "
        f"{'TP':>8} "
        f"{'NET':>8} "
        f"{'VM':>8} "
        f"{'%':>8}"
    )
    print("-" * 95)

    results = []

    for test_case in DEFAULT_TEST_CASES:
        mask = (
            (complete_dataframe[CPU_COLUMN]
             <= test_case["cpu"])
            & (
                complete_dataframe[IOPS_COLUMN]
                <= test_case["iops"]
            )
            & (
                complete_dataframe[THROUGHPUT_COLUMN]
                <= test_case["throughput"]
            )
            & (
                complete_dataframe[NETWORK_COLUMN]
                <= test_case["network"]
            )
        )

        count = int(mask.sum())
        percentage = count / total * 100

        print(
            f"{test_case['name']:<25} "
            f"{test_case['cpu']:>8.2f} "
            f"{test_case['iops']:>8.2f} "
            f"{test_case['throughput']:>8.2f} "
            f"{test_case['network']:>8.2f} "
            f"{count:>8d} "
            f"{percentage:>7.1f}%"
        )

        results.append(
            {
                "Scenario": test_case["name"],
                "CPU": test_case["cpu"],
                "IOPS": test_case["iops"],
                "Throughput": test_case["throughput"],
                "Network": test_case["network"],
                "VM": count,
                "Percentage": percentage,
            }
        )

    return pd.DataFrame(results)


def print_data_quality_summary(dataframe):
    print("\n" + "=" * 80)
    print("RINGKASAN KUALITAS DATA")
    print("=" * 80)

    for metric_name, column in ANALYSIS_COLUMNS.items():
        valid_count = int(
            dataframe[column].notna().sum()
        )
        missing_count = int(
            dataframe[column].isna().sum()
        )

        print(
            f"{column}: valid={valid_count}, "
            f"missing/invalid={missing_count}"
        )

    if STATE_COLUMN in dataframe.columns:
        state_counts = (
            dataframe[STATE_COLUMN]
            .astype("string")
            .fillna("Unknown")
            .value_counts(dropna=False)
        )

        print("\nDistribusi State:")
        for state, count in state_counts.items():
            print(f"  {state}: {count}")


def save_results(results, output_path):
    if results.empty:
        return

    results.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"\n[INFO] Hasil kombinasi disimpan ke: "
        f"{output_path}"
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Analisis distribusi metrik VM untuk diagnosis "
            "kandidat zombie."
        )
    )

    parser.add_argument(
        "csv_file",
        help="Path ke CSV metrik VM.",
    )

    parser.add_argument(
        "--sep",
        default=None,
        help=(
            "Separator CSV. Jika tidak diisi, script "
            "mencoba ',', ';', dan tab."
        ),
    )

    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Path output CSV untuk hasil kombinasi "
            "threshold."
        ),
    )

    return parser.parse_args()


def main():
    arguments = parse_arguments()
    csv_path = Path(arguments.csv_file)

    if not csv_path.exists():
        print(
            f"❌ File tidak ditemukan: {csv_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        dataframe = read_csv_robust(
            csv_path,
            separator=arguments.sep,
        )
        dataframe = normalize_columns(dataframe)
        validate_required_columns(dataframe)
        dataframe = prepare_metric_dataframe(dataframe)

    except (OSError, ValueError) as error:
        print(
            f"❌ Gagal memproses CSV: {error}",
            file=sys.stderr,
        )
        sys.exit(1)

    print("=" * 80)
    print("ANALISIS DISTRIBUSI DETAIL")
    print("=" * 80)
    print(f"File: {csv_path}")
    print(f"Jumlah baris: {len(dataframe)}")
    print(f"Jumlah kolom: {len(dataframe.columns)}")

    print_data_quality_summary(dataframe)

    metric_labels = {
        "CPU P95": CPU_COLUMN,
        "IOPS P95": IOPS_COLUMN,
        "Throughput P95": THROUGHPUT_COLUMN,
        "Network P95": NETWORK_COLUMN,
    }

    for metric_name, column in metric_labels.items():
        print_metric_summary(
            dataframe,
            metric_name,
            column,
        )
        print_threshold_summary(
            dataframe,
            metric_name,
            column,
        )

    results = print_combination_analysis(dataframe)

    if arguments.output:
        save_results(results, arguments.output)


if __name__ == "__main__":
    main()
