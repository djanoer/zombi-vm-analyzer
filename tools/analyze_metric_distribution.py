#!/usr/bin/env python3
"""
Script untuk analisis distribusi metrik VM dari CSV vROps.

Tujuan:
- Memahami distribusi metrik (CPU, IOPS, Throughput, Network)
- Menentukan threshold optimal berdasarkan distribusi aktual
- Mengidentifikasi outlier dan pattern

Cara penggunaan:
    python analyze_metric_distribution.py vm_metrics.csv

Output:
    - Statistik deskriptif
    - Histogram distribusi
    - Rekomendasi threshold
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

def parse_numeric(value):
    """
    Parse nilai numerik dari CSV yang mungkin mengandung koma, persen, atau satuan.

    Contoh:
    - "0.05" → 0.05
    - "1,632" → 1632
    - "0 KBps" → 0
    - "1.03 ms" → 1.03
    """
    if pd.isna(value):
        return np.nan

    # Convert ke string
    value = str(value).strip()

    # Hapus satuan
    for unit in [' KBps', ' MBps', ' GBps', ' GB', ' TB', ' ms', ' μs', '%']:
        value = value.replace(unit, '')

    # Hapus koma (untuk format angka ribuan)
    value = value.replace(',', '')

    # Hapus spasi
    value = value.strip()

    # Coba convert ke float
    try:
        return float(value)
    except ValueError:
        return np.nan

def analyze_distribution(df, column_name, metric_label):
    """
    Analisis distribusi untuk satu kolom metrik.
    """
    # Parse nilai
    values = df[column_name].apply(parse_numeric)

    # Hapus NaN
    values = values.dropna()

    if len(values) == 0:
        print(f"\n⚠️  {metric_label}: Tidak ada data valid")
        return None

    # Statistik deskriptif
    stats = {
        'count': len(values),
        'min': values.min(),
        'max': values.max(),
        'mean': values.mean(),
        'median': values.median(),
        'std': values.std(),
        'p10': values.quantile(0.10),
        'p25': values.quantile(0.25),
        'p50': values.quantile(0.50),
        'p75': values.quantile(0.75),
        'p90': values.quantile(0.90),
        'p95': values.quantile(0.95),
        'p99': values.quantile(0.99),
    }

    # Tampilkan statistik
    print(f"\n{'=' * 80}")
    print(f"DISTRIBUSI: {metric_label}")
    print(f"{'=' * 80}")
    print(f"Count: {stats['count']}")
    print(f"Min: {stats['min']:.2f}")
    print(f"Max: {stats['max']:.2f}")
    print(f"Mean: {stats['mean']:.2f}")
    print(f"Median (P50): {stats['median']:.2f}")
    print(f"Std Dev: {stats['std']:.2f}")
    print(f"\nPercentiles:")
    print(f"  P10: {stats['p10']:.2f}")
    print(f"  P25: {stats['p25']:.2f}")
    print(f"  P50: {stats['p50']:.2f}")
    print(f"  P75: {stats['p75']:.2f}")
    print(f"  P90: {stats['p90']:.2f}")
    print(f"  P95: {stats['p95']:.2f}")
    print(f"  P99: {stats['p99']:.2f}")

    # Rekomendasi threshold
    print(f"\n📊 REKOMENDASI THRESHOLD:")

    # Threshold konservatif (P10 atau lebih rendah)
    threshold_conservative = min(stats['p10'], stats['p25'] * 0.5)
    print(f"  Conservative: ≤ {threshold_conservative:.2f} (P10={stats['p10']:.2f})")

    # Threshold balanced (di antara P10 dan P25)
    threshold_balanced = (stats['p10'] + stats['p25']) / 2
    print(f"  Balanced: ≤ {threshold_balanced:.2f} (P10={stats['p10']:.2f}, P25={stats['p25']:.2f})")

    # Threshold aggressive (P25 atau lebih tinggi)
    threshold_aggressive = max(stats['p25'], stats['p10'] * 2)
    print(f"  Aggressive: ≤ {threshold_aggressive:.2f} (P25={stats['p25']:.2f})")

    # Estimasi VM yang akan terdeteksi
    total_vm = len(values)
    vm_conservative = (values <= threshold_conservative).sum()
    vm_balanced = (values <= threshold_balanced).sum()
    vm_aggressive = (values <= threshold_aggressive).sum()

    print(f"\n📈 ESTIMASI VM TERDETEKSI (jika hanya metrik ini):")
    print(f"  Conservative: {vm_conservative} VM ({vm_conservative/total_vm*100:.1f}%)")
    print(f"  Balanced: {vm_balanced} VM ({vm_balanced/total_vm*100:.1f}%)")
    print(f"  Aggressive: {vm_aggressive} VM ({vm_aggressive/total_vm*100:.1f}%)")

    return stats

def main():
    # Cek argument
    if len(sys.argv) < 2:
        print("Usage: python analyze_metric_distribution.py <csv_file>")
        print("Example: python analyze_metric_distribution.py vm_metrics.csv")
        sys.exit(1)

    csv_file = sys.argv[1]

    # Cek file exists
    if not Path(csv_file).exists():
        print(f"❌ File tidak ditemukan: {csv_file}")
        sys.exit(1)

    # Load CSV
    print(f"📂 Loading CSV: {csv_file}")
    df = pd.read_csv(csv_file)
    print(f"✅ Loaded {len(df)} VM")

    # Mapping kolom (sesuaikan dengan struktur CSV Anda)
    column_mapping = {
        'CPU Percentile 95%': 'CPU P95 (%)',
        'IOPS Percentile 95%': 'IOPS P95',
        'Throughput Percentile 95%': 'Throughput P95 (KBps)',
        'Network I/O | Usage Rate (KBps) - 95th Percentile': 'Network P95 (KBps)',
        'Uptime / Days': 'Uptime (Days)',
        'Status Idle': 'Status Idle',
    }

    # Analisis setiap metrik
    all_stats = {}

    for col, label in column_mapping.items():
        if col in df.columns:
            stats = analyze_distribution(df, col, label)
            all_stats[col] = stats
        else:
            print(f"\n⚠️  Kolom tidak ditemukan: {col}")

    # Rekomendasi threshold final
    print(f"\n{'=' * 80}")
    print("REKOMENDASI THRESHOLD FINAL (BERDASARKAN DISTRIBUSI AKTUAL)")
    print(f"{'=' * 80}")

    if 'CPU Percentile 95%' in all_stats and all_stats['CPU Percentile 95%']:
        cpu_p25 = all_stats['CPU Percentile 95%']['p25']
        cpu_p10 = all_stats['CPU Percentile 95%']['p10']
        cpu_threshold = min(cpu_p10, cpu_p25 * 0.5)
        print(f"CPU P95: ≤ {cpu_threshold:.2f}%")

    if 'IOPS Percentile 95%' in all_stats and all_stats['IOPS Percentile 95%']:
        iops_p25 = all_stats['IOPS Percentile 95%']['p25']
        iops_p10 = all_stats['IOPS Percentile 95%']['p10']
        iops_threshold = min(iops_p10, iops_p25 * 0.5)
        print(f"IOPS P95: ≤ {iops_threshold:.0f}")

    if 'Throughput Percentile 95%' in all_stats and all_stats['Throughput Percentile 95%']:
        tp_p25 = all_stats['Throughput Percentile 95%']['p25']
        tp_p10 = all_stats['Throughput Percentile 95%']['p10']
        tp_threshold = min(tp_p10, tp_p25 * 0.5)
        print(f"Throughput P95: ≤ {tp_threshold:.0f} KBps")

    if 'Network I/O | Usage Rate (KBps) - 95th Percentile' in all_stats and all_stats['Network I/O | Usage Rate (KBps) - 95th Percentile']:
        net_p25 = all_stats['Network I/O | Usage Rate (KBps) - 95th Percentile']['p25']
        net_p10 = all_stats['Network I/O | Usage Rate (KBps) - 95th Percentile']['p10']
        net_threshold = min(net_p10, net_p25 * 0.5)
        print(f"Network P95: ≤ {net_threshold:.0f} KBps")

    print(f"\n💡 CATATAN:")
    print(f"  - Threshold ini adalah rekomendasi berdasarkan distribusi data Anda")
    print(f"  - Sesuaikan berdasarkan toleransi false positive")
    print(f"  - Test dengan subset data sebelum apply ke semua VM")

    # Simpan ringkasan ke file
    output_file = Path('output/metric_distribution_summary.txt')
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        f.write("METRIC DISTRIBUTION SUMMARY\n")
        f.write("=" * 80 + "\n\n")

        for col, stats in all_stats.items():
            if stats:
                f.write(f"{col}:\n")
                f.write(f"  Min: {stats['min']:.2f}\n")
                f.write(f"  Max: {stats['max']:.2f}\n")
                f.write(f"  Mean: {stats['mean']:.2f}\n")
                f.write(f"  Median: {stats['median']:.2f}\n")
                f.write(f"  P10: {stats['p10']:.2f}\n")
                f.write(f"  P25: {stats['p25']:.2f}\n")
                f.write(f"  P75: {stats['p75']:.2f}\n")
                f.write(f"  P90: {stats['p90']:.2f}\n")
                f.write(f"  P95: {stats['p95']:.2f}\n")
                f.write("\n")

    print(f"\n📄 Ringkasan disimpan ke: {output_file}")

if __name__ == '__main__':
    main()
