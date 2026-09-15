#!/usr/bin/env python3
"""
Script debug untuk investigasi masalah parsing CSV.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_csv.py <csv_file>")
        sys.exit(1)

    csv_file = sys.argv[1]

    if not Path(csv_file).exists():
        print(f"❌ File tidak ditemukan: {csv_file}")
        sys.exit(1)

    print("=" * 80)
    print("DEBUG CSV PARSING")
    print("=" * 80)

    # Coba berbagai encoding
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    df = None

    for encoding in encodings:
        try:
            df = pd.read_csv(csv_file, encoding=encoding)
            print(f"✅ Encoding berhasil: {encoding}")
            break
        except UnicodeDecodeError as e:
            print(f"❌ Encoding {encoding} gagal: {e}")

    if df is None:
        print("❌ Tidak bisa membaca file")
        sys.exit(1)

    # Tampilkan info dasar
    print(f"\n📊 Info DataFrame:")
    print(f"  Rows: {len(df)}")
    print(f"  Columns: {len(df.columns)}")

    # Tampilkan semua kolom
    print(f"\n📋 Daftar Kolom:")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i:2d}. '{col}' (type: {df[col].dtype})")

    # Cari kolom yang mungkin adalah metrik
    print(f"\n🔍 Mencari kolom metrik...")

    keyword_mapping = {
        'CPU': 'cpu_p95',
        'IOPS': 'iops_p95',
        'Throughput': 'throughput_p95',
        'Network': 'network_p95',
        'Uptime': 'uptime_days',
        'Idle': 'status_idle',
    }

    found_mapping = {}

    for keyword, field in keyword_mapping.items():
        for col in df.columns:
            if keyword.lower() in col.lower():
                found_mapping[field] = col
                print(f"  ✅ {field}: '{col}'")
                break
        else:
            print(f"  ❌ {field}: TIDAK DITEMUKAN")

    # Tampilkan sample data untuk setiap kolom metrik
    print(f"\n📈 Sample Data (5 baris pertama):")

    for field, col in found_mapping.items():
        print(f"\n  {field} ('{col}'):")
        sample = df[col].head(5)
        for i, val in sample.items():
            print(f"    Row {i}: {repr(val)}")

    # Coba parse nilai
    print(f"\n🔧 Testing parsing...")

    def parse_numeric(value):
        if pd.isna(value):
            return np.nan
        value = str(value).strip()
        for unit in [' KBps', ' MBps', ' GBps', ' GB', ' TB', ' ms', ' μs', '%']:
            value = value.replace(unit, '')
        value = value.replace(',', '').strip()
        try:
            return float(value)
        except ValueError:
            return np.nan

    for field, col in found_mapping.items():
        sample = df[col].head(5)
        parsed = sample.apply(parse_numeric)
        print(f"\n  {field}:")
        for i, (orig, num) in enumerate(zip(sample, parsed)):
            print(f"    Row {i}: {repr(orig)} → {num}")

    # Statistik dasar
    print(f"\n📊 Statistik Deskriptif:")

    for field, col in found_mapping.items():
        parsed = df[col].apply(parse_numeric)
        valid = parsed.dropna()

        if len(valid) > 0:
            print(f"\n  {field} ('{col}'):")
            print(f"    Valid values: {len(valid)} / {len(df)}")
            print(f"    Min: {valid.min():.4f}")
            print(f"    Max: {valid.max():.4f}")
            print(f"    Mean: {valid.mean():.4f}")
            print(f"    Median: {valid.median():.4f}")
        else:
            print(f"\n  {field} ('{col}'): TIDAK ADA DATA VALID")

if __name__ == '__main__':
    main()
