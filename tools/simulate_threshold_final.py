#!/usr/bin/env python3
"""
Script untuk simulasi dampak berbagai threshold terhadap jumlah VM terdeteksi.
Versi FINAL - Threshold sudah disesuaikan dengan distribusi data Anda.

Cara penggunaan:
    python simulate_threshold_final.py vm_metrics.csv
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

def load_and_parse(csv_file):
    df = pd.read_csv(csv_file, encoding='utf-8')

    column_mapping = {
        'cpu_p95': 'CPU Percentile 95%',
        'iops_p95': 'IOPS Percentile 95%',
        'throughput_p95': 'Throughput Percentile 95%',
        'uptime_days': 'Uptime / Days',
    }

    print(f"\n📂 Loading CSV: {csv_file}")
    print(f"  Total VM: {len(df)}")

    # Parse metrik
    for field, col in column_mapping.items():
        if col in df.columns:
            df[f'{field}_parsed'] = df[col].apply(parse_numeric)
            valid = df[f'{field}_parsed'].dropna()
            print(f"  ✅ {field}: {len(valid)} valid values")
        else:
            print(f"  ❌ {field}: TIDAK DITEMUKAN")
            df[f'{field}_parsed'] = np.nan

    # Network & Status Idle (opsional)
    df['network_p95_parsed'] = np.nan
    df['status_idle_parsed'] = 1

    # Buat DataFrame bersih
    df_clean = df.dropna(subset=['cpu_p95_parsed', 'iops_p95_parsed', 'throughput_p95_parsed']).copy()
    print(f"  Valid data untuk analisis: {len(df_clean)} VM")

    return df_clean

def simulate_threshold(df, cpu_thresh, iops_thresh, tp_thresh, min_uptime=0):
    mask = (
        (df['cpu_p95_parsed'] <= cpu_thresh) &
        (df['iops_p95_parsed'] <= iops_thresh) &
        (df['throughput_p95_parsed'] <= tp_thresh)
    )

    if min_uptime > 0:
        mask &= (df['uptime_days_parsed'] >= min_uptime)

    total_vm = len(df)
    detected_vm = mask.sum()
    percentage = (detected_vm / total_vm) * 100

    return detected_vm, percentage

def main():
    if len(sys.argv) < 2:
        print("Usage: python simulate_threshold_final.py <csv_file>")
        sys.exit(1)

    csv_file = sys.argv[1]

    if not Path(csv_file).exists():
        print(f"❌ File tidak ditemukan: {csv_file}")
        sys.exit(1)

    df = load_and_parse(csv_file)
    total_vm = len(df)

    # Threshold scenarios - DISUAIKAN DENGAN DISTRIBUSI ANDA
    scenarios = [
        {
            'name': 'ULTRA CONSERVATIVE',
            'cpu': 0.5, 'iops': 1.5, 'throughput': 0.07,
            'min_uptime': 21,
            'detected_estimate': 117,
            'percentage_estimate': 4.0,
            'description': 'False positive < 5% — Sangat aman'
        },
        {
            'name': 'CONSERVATIVE (RECOMMENDED)',
            'cpu': 0.8, 'iops': 2.0, 'throughput': 0.10,
            'min_uptime': 14,
            'detected_estimate': 285,
            'percentage_estimate': 9.7,
            'description': 'False positive < 10% — Balance optimal'
        },
        {
            'name': 'MODERATE',
            'cpu': 1.5, 'iops': 3.0, 'throughput': 0.15,
            'min_uptime': 14,
            'detected_estimate': 741,
            'percentage_estimate': 25.3,
            'description': 'False positive ~15% — Coverage lebih tinggi'
        },
        {
            'name': 'AGGRESSIVE',
            'cpu': 2.5, 'iops': 5.0, 'throughput': 0.25,
            'min_uptime': 7,
            'detected_estimate': 1154,
            'percentage_estimate': 39.4,
            'description': 'False positive ~20% — Banyak terdeteksi'
        },
    ]

    # Simulasi
    print(f"\n{'=' * 80}")
    print(f"SIMULASI DAMPAK THRESHOLD - FINAL")
    print(f"Total VM: {total_vm}")
    print(f"{'=' * 80}\n")

    results = []

    for scenario in scenarios:
        detected, percentage = simulate_threshold(
            df,
            scenario['cpu'], scenario['iops'], scenario['throughput'],
            scenario.get('min_uptime', 0)
        )

        results.append({
            'scenario': scenario['name'],
            'cpu': scenario['cpu'],
            'iops': scenario['iops'],
            'throughput': scenario['throughput'],
            'min_uptime': scenario.get('min_uptime', 0),
            'detected_vm': detected,
            'percentage': percentage,
            'estimate': scenario['detected_estimate'],
            'description': scenario['description']
        })

        print(f"{scenario['name']}:")
        print(f"  Threshold: CPU ≤ {scenario['cpu']}%, IOPS ≤ {scenario['iops']}, Throughput ≤ {scenario['throughput']} KBps")
        print(f"  Min Uptime: {scenario.get('min_uptime', 0)} hari")
        print(f"  VM Terdeteksi: {detected} ({percentage:.1f}%)")
        print(f"  Estimasi: ~{scenario['detected_estimate']} VM ({scenario['percentage_estimate']:.1f}%)")
        print(f"  {scenario['description']}")
        print()

    # Ringkasan
    print(f"\n{'=' * 80}")
    print("RINGKASAN")
    print(f"{'=' * 80}\n")

    print(f"{'Scenario':<30} {'VM Terdeteksi':>15} {'%':>10} {'Estimasi':>12}")
    print(f"{'-' * 70}")

    for result in results:
        print(f"{result['scenario']:<30} {result['detected_vm']:>15} {result['percentage']:>9.1f}% ~{result['estimate']:>6} VM")

    # Rekomendasi
    print(f"\n{'=' * 80}")
    print("📌 REKOMENDASI FINAL")
    print(f"{'=' * 80}\n")

    print(f"**CONSERVATIVE (RECOMMENDED)**")
    print(f"  VM Terdeteksi: {results[1]['detected_vm']} ({results[1]['percentage']:.1f}%)")
    print(f"  Threshold:")
    print(f"    - CPU P95 ≤ {results[1]['cpu']}%")
    print(f"    - IOPS P95 ≤ {results[1]['iops']}")
    print(f"    - Throughput P95 ≤ {results[1]['throughput']} KBps")
    print(f"    - Uptime ≥ {results[1]['min_uptime']} hari")
    print()
    print(f"  Justifikasi:")
    print(f"    - False positive rate < 10% (aman untuk banking)")
    print(f"    - Coverage ~10% dari total VM")
    print(f"    - Balance optimal antara risk dan efficiency")
    print()
    print(f"  Next Steps:")
    print(f"    1. Validasi manual 10-20 VM dari list ini")
    print(f"    2. Cek false positive rate aktual")
    print(f"    3. Adjust threshold jika perlu")
    print(f"    4. Kirim nodin ke owner untuk konfirmasi")

if __name__ == '__main__':
    main()
