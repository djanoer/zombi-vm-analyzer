#!/usr/bin/env python3
"""
Analisis distribusi detail untuk memahami kenapa 0 VM terdeteksi.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

def parse_numeric(value):
    if pd.isna(value):
        return np.nan
    value = str(value).strip()
    if value in ['-', '', 'none', 'None']:
        return np.nan
    for unit in [' KBps', ' MBps', ' GBps', ' GB', ' TB', ' ms', ' μs', '%']:
        value = value.replace(unit, '')
    value = value.replace(',', '').strip()
    try:
        return float(value)
    except ValueError:
        return np.nan

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_distribution_detailed.py <csv_file>")
        sys.exit(1)

    csv_file = sys.argv[1]

    df = pd.read_csv(csv_file, encoding='utf-8')

    # Parse metrik
    cpu = df['CPU Percentile 95%'].apply(parse_numeric).dropna()
    iops = df['IOPS Percentile 95%'].apply(parse_numeric).dropna()
    tp = df['Throughput Percentile 95%'].apply(parse_numeric).dropna()

    print("=" * 80)
    print("ANALISIS DISTRIBUSI DETAIL")
    print("=" * 80)

    for name, data in [('CPU P95', cpu), ('IOPS P95', iops), ('Throughput P95', tp)]:
        print(f"\n{name}:")
        print(f"  Count: {len(data)}")
        print(f"  Min: {data.min():.4f}")
        print(f"  Max: {data.max():.4f}")
        print(f"  Mean: {data.mean():.4f}")
        print(f"  Median: {data.median():.4f}")

        # Percentiles detail
        print(f"\n  Percentiles:")
        for p in [1, 5, 10, 15, 20, 25, 30, 40, 50]:
            print(f"    P{p:2d}: {data.quantile(p/100):.4f}")

        # Hitung berapa VM di bawah berbagai threshold
        print(f"\n  VM di bawah threshold:")
        if name == 'CPU P95':
            thresholds = [0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 2.5, 5.0, 10.0]
        elif name == 'IOPS P95':
            thresholds = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0]
        else:  # Throughput
            thresholds = [0.01, 0.02, 0.05, 0.07, 0.10, 0.15, 0.20, 0.25, 0.50, 1.0]

        for thresh in thresholds:
            count = (data <= thresh).sum()
            pct = (count / len(data)) * 100
            if count > 0 or thresh <= 1.0:
                print(f"    ≤ {thresh:6.2f}: {count:4d} VM ({pct:5.1f}%)")

    # Analisis kombinasi
    print(f"\n{'=' * 80}")
    print("ANALISIS KOMBINASI (AND Logic)")
    print(f"{'=' * 80}")

    df_clean = pd.DataFrame({
        'cpu': cpu,
        'iops': iops,
        'throughput': tp
    }).dropna()

    total = len(df_clean)
    print(f"\nTotal VM dengan data lengkap: {total}")

    # Test berbagai kombinasi threshold
    test_cases = [
        {'cpu': 0.5, 'iops': 1.5, 'tp': 0.07, 'name': 'VERY CONSERVATIVE'},
        {'cpu': 0.8, 'iops': 2.0, 'tp': 0.10, 'name': 'CONSERVATIVE'},
        {'cpu': 1.5, 'iops': 3.0, 'tp': 0.15, 'name': 'MODERATE'},
        {'cpu': 2.5, 'iops': 5.0, 'tp': 0.25, 'name': 'AGGRESSIVE'},
        {'cpu': 5.0, 'iops': 10.0, 'tp': 0.50, 'name': 'VERY AGGRESSIVE'},
        {'cpu': 10.0, 'iops': 20.0, 'tp': 1.0, 'name': 'EXTREME'},
    ]

    print(f"\n{'Scenario':<25} {'CPU':>8} {'IOPS':>8} {'TP':>8} {'VM':>8} {'%':>8}")
    print(f"{'-' * 75}")

    for tc in test_cases:
        mask = (
            (df_clean['cpu'] <= tc['cpu']) &
            (df_clean['iops'] <= tc['iops']) &
            (df_clean['throughput'] <= tc['tp'])
        )
        count = mask.sum()
        pct = (count / total) * 100
        print(f"{tc['name']:<25} {tc['cpu']:>8.1f} {tc['iops']:>8.1f} {tc['tp']:>8.2f} {count:>8} {pct:>7.1f}%")

if __name__ == '__main__':
    main()
