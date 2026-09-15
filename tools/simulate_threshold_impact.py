#!/usr/bin/env python3
"""
Script untuk simulasi dampak berbagai threshold terhadap jumlah VM terdeteksi.
Versi FIXED untuk CSV dengan struktur yang benar.

Cara penggunaan:
    python simulate_threshold_impact_fixed.py vm_metrics.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

def parse_numeric(value):
    """Parse nilai numerik dari CSV."""
    if pd.isna(value):
        return np.nan

    value = str(value).strip()

    # Handle nilai '-' atau kosong
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
    """Load CSV dan parse kolom metrik - FIXED version."""
    print(f"\n📂 Loading CSV: {csv_file}")

    # Coba berbagai encoding
    encodings = ['utf-8', 'latin-1', 'cp1252']
    df = None

    for encoding in encodings:
        try:
            df = pd.read_csv(csv_file, encoding=encoding)
            print(f"✅ Encoding berhasil: {encoding}")
            break
        except UnicodeDecodeError:
            continue

    if df is None:
        print("❌ Tidak bisa membaca file")
        sys.exit(1)

    # Mapping kolom yang BENAR untuk CSV Anda
    column_mapping = {
        'cpu_p95': 'CPU Percentile 95%',  # BUKAN vCPU!
        'iops_p95': 'IOPS Percentile 95%',  # BUKAN Avg Read IOPS!
        'throughput_p95': 'Throughput Percentile 95%',  # BUKAN Avg Read Throughput!
        'network_p95': 'Network I/O | Usage Rate (KBps) - 95th Percentile',
        'uptime_days': 'Uptime / Days',
        'status_idle': 'Status Idle',
    }

    # Cek kolom yang ada
    print(f"\n📋 Memeriksa kolom...")
    found_columns = {}

    for field, expected_col in column_mapping.items():
        if expected_col in df.columns:
            found_columns[field] = expected_col
            print(f"  ✅ {field}: '{expected_col}'")
        else:
            found_columns[field] = None
            print(f"  ❌ {field}: '{expected_col}' TIDAK DITEMUKAN")

    # Parse metrik
    print(f"\n🔧 Parsing metrik...")

    # CPU P95
    if found_columns['cpu_p95']:
        df['cpu_p95_parsed'] = df[found_columns['cpu_p95']].apply(parse_numeric)
        valid = df['cpu_p95_parsed'].dropna()
        print(f"  CPU P95: {len(valid)} valid values (min={valid.min():.2f}, max={valid.max():.2f})")
    else:
        print("  ❌ CPU P95 tidak ditemukan")
        sys.exit(1)

    # IOPS P95
    if found_columns['iops_p95']:
        df['iops_p95_parsed'] = df[found_columns['iops_p95']].apply(parse_numeric)
        valid = df['iops_p95_parsed'].dropna()
        print(f"  IOPS P95: {len(valid)} valid values (min={valid.min():.2f}, max={valid.max():.2f})")
    else:
        print("  ❌ IOPS P95 tidak ditemukan")
        sys.exit(1)

    # Throughput P95
    if found_columns['throughput_p95']:
        df['throughput_p95_parsed'] = df[found_columns['throughput_p95']].apply(parse_numeric)
        valid = df['throughput_p95_parsed'].dropna()
        print(f"  Throughput P95: {len(valid)} valid values (min={valid.min():.2f}, max={valid.max():.2f})")
    else:
        print("  ❌ Throughput P95 tidak ditemukan")
        sys.exit(1)

    # Network P95 (opsional)
    if found_columns['network_p95']:
        df['network_p95_parsed'] = df[found_columns['network_p95']].apply(parse_numeric)
        valid = df['network_p95_parsed'].dropna()
        if len(valid) > 0:
            print(f"  Network P95: {len(valid)} valid values (min={valid.min():.2f}, max={valid.max():.2f})")
        else:
            print(f"  ⚠️  Network P95: 0 valid values, skip analisis network")
            df['network_p95_parsed'] = np.nan
    else:
        print(f"  ⚠️  Network P95 tidak ditemukan, skip analisis network")
        df['network_p95_parsed'] = np.nan

    # Uptime (opsional)
    if found_columns['uptime_days']:
        df['uptime_days_parsed'] = df[found_columns['uptime_days']].apply(parse_numeric)
        valid = df['uptime_days_parsed'].dropna()
        if len(valid) > 0:
            print(f"  Uptime: {len(valid)} valid values (min={valid.min():.0f}, max={valid.max():.0f})")
        else:
            print(f"  ⚠️  Uptime: 0 valid values, skip filter uptime")
            df['uptime_days_parsed'] = 0
    else:
        print(f"  ⚠️  Uptime tidak ditemukan, skip filter uptime")
        df['uptime_days_parsed'] = 0

    # Status Idle (opsional)
    if found_columns['status_idle']:
        df['status_idle_parsed'] = df[found_columns['status_idle']].apply(parse_numeric)
        valid = df['status_idle_parsed'].dropna()
        if len(valid) > 0:
            print(f"  Status Idle: {len(valid)} valid values (min={valid.min():.0f}, max={valid.max():.0f})")
        else:
            print(f"  ⚠️  Status Idle: 0 valid values, skip filter idle score")
            df['status_idle_parsed'] = 1
    else:
        print(f"  ⚠️  Status Idle tidak ditemukan, skip filter idle score")
        df['status_idle_parsed'] = 1

    # Buat DataFrame bersih
    df_clean = df.dropna(subset=['cpu_p95_parsed', 'iops_p95_parsed', 'throughput_p95_parsed']).copy()

    print(f"\n📊 Summary:")
    print(f"  Total VM: {len(df)}")
    print(f"  Valid data: {len(df_clean)}")

    return df_clean

def simulate_threshold(df, cpu_thresh, iops_thresh, tp_thresh, net_thresh=None, min_uptime=0, min_idle_score=0):
    """Simulasi threshold."""
    # Filter metrik
    mask = (
        (df['cpu_p95_parsed'] <= cpu_thresh) &
        (df['iops_p95_parsed'] <= iops_thresh) &
        (df['throughput_p95_parsed'] <= tp_thresh)
    )

    # Network (jika ada data)
    if net_thresh is not None and 'network_p95_parsed' in df.columns and not df['network_p95_parsed'].isna().all():
        mask &= (df['network_p95_parsed'] <= net_thresh)

    # Uptime (jika ada data)
    if min_uptime > 0 and 'uptime_days_parsed' in df.columns:
        mask &= (df['uptime_days_parsed'] >= min_uptime)

    # Idle score (jika ada data)
    if min_idle_score > 0 and 'status_idle_parsed' in df.columns and not df['status_idle_parsed'].isna().all():
        mask &= (df['status_idle_parsed'] >= min_idle_score)

    total_vm = len(df)
    detected_vm = mask.sum()
    percentage = (detected_vm / total_vm) * 100

    return detected_vm, percentage

def main():
    if len(sys.argv) < 2:
        print("Usage: python simulate_threshold_impact_fixed.py <csv_file>")
        sys.exit(1)

    csv_file = sys.argv[1]

    if not Path(csv_file).exists():
        print(f"❌ File tidak ditemukan: {csv_file}")
        sys.exit(1)

    # Load data
    df = load_and_parse(csv_file)
    total_vm = len(df)

    # Definisi scenarios
    scenarios = [
        {
            'name': 'ULTRA CONSERVATIVE',
            'cpu': 0.3, 'iops': 1.0, 'throughput': 0.05, 'network': 20,
            'min_uptime': 30, 'min_idle_score': 80,
            'description': 'Hanya VM yang benar-benar idle'
        },
        {
            'name': 'VERY CONSERVATIVE',
            'cpu': 0.5, 'iops': 1.5, 'throughput': 0.07, 'network': 30,
            'min_uptime': 21, 'min_idle_score': 75,
            'description': 'Sangat ketat, false positive < 5%'
        },
        {
            'name': 'CONSERVATIVE',
            'cpu': 0.8, 'iops': 2.0, 'throughput': 0.10, 'network': 50,
            'min_uptime': 14, 'min_idle_score': 70,
            'description': 'Balance antara coverage dan akurasi'
        },
        {
            'name': 'MODERATE',
            'cpu': 1.5, 'iops': 3.0, 'throughput': 0.15, 'network': 75,
            'min_uptime': 14, 'min_idle_score': 60,
            'description': 'Lebih banyak terdeteksi'
        },
        {
            'name': 'AGGRESSIVE',
            'cpu': 2.5, 'iops': 5.0, 'throughput': 0.25, 'network': 100,
            'min_uptime': 7, 'min_idle_score': 50,
            'description': 'Coverage maksimal'
        },
    ]

    # Simulasi
    print(f"\n{'=' * 80}")
    print(f"SIMULASI DAMPAK THRESHOLD")
    print(f"Total VM: {total_vm}")
    print(f"{'=' * 80}\n")

    results = []

    for scenario in scenarios:
        detected, percentage = simulate_threshold(
            df,
            scenario['cpu'], scenario['iops'], scenario['throughput'],
            scenario.get('network'),
            scenario.get('min_uptime', 0),
            scenario.get('min_idle_score', 0)
        )

        results.append({
            'scenario': scenario['name'],
            'cpu': scenario['cpu'],
            'iops': scenario['iops'],
            'throughput': scenario['throughput'],
            'detected_vm': detected,
            'percentage': percentage,
            'description': scenario['description']
        })

        print(f"{scenario['name']}:")
        print(f"  CPU ≤ {scenario['cpu']}%, IOPS ≤ {scenario['iops']}, Throughput ≤ {scenario['throughput']}")
        print(f"  VM Terdeteksi: {detected} ({percentage:.1f}%)")
        print(f"  {scenario['description']}")
        print()

    # Ringkasan
    print(f"\n{'=' * 80}")
    print("RINGKASAN")
    print(f"{'=' * 80}\n")

    print(f"{'Scenario':<25} {'VM Terdeteksi':>15} {'Persentase':>12}")
    print(f"{'-' * 55}")

    for result in results:
        print(f"{result['scenario']:<25} {result['detected_vm']:>15} {result['percentage']:>10.1f}%")

    # Cari yang 5-10%
    recommended = None
    for result in results:
        if 5 <= result['percentage'] <= 10:
            recommended = result
            break

    if recommended is None:
        recommended = min(results, key=lambda x: abs(x['percentage'] - 7.5))

    print(f"\n📌 REKOMENDASI: {recommended['scenario']}")
    print(f"   VM Terdeteksi: {recommended['detected_vm']} ({recommended['percentage']:.1f}%)")
    print(f"   Threshold: CPU ≤ {recommended['cpu']}%, IOPS ≤ {recommended['iops']}, Throughput ≤ {recommended['throughput']}")

if __name__ == '__main__':
    main()
