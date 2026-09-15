# ==============================================================================
#  ZOMBIE VM ANALYZER — UTILITY: inspect_csv_structure.py
# ------------------------------------------------------------------------------
#  Peran  : Validasi independen struktur CSV sebelum upload ke Streamlit.
#  Jalankan: python inspect_csv_structure.py "file.csv"
# ------------------------------------------------------------------------------
#  Validasi 1 kolom diperlakukan sebagai FAIL, walaupun semua baris sama-sama
#  memiliki 1 field. Kesamaan jumlah field saja tidak berarti CSV valid.
# ==============================================================================
import csv
import sys
from collections import Counter


if len(sys.argv) < 2:
    print("Cara pakai: python inspect_csv_structure.py <file.csv>")
    sys.exit(1)

file_path = sys.argv[1]
rows = None
encoding_used = None

for encoding in ["utf-8-sig", "utf-8", "latin1"]:
    try:
        with open(file_path, "r", encoding=encoding, newline="") as file:
            rows = list(csv.reader(file))
        encoding_used = encoding
        break
    except UnicodeDecodeError:
        continue

if not rows:
    print("STATUS: FAIL — file kosong atau tidak dapat dibaca.")
    sys.exit(1)

header = rows[0]
expected_fields = len(header)
field_counts = Counter(len(row) for row in rows[1:])

print(f"Encoding       : {encoding_used}")
print(f"Total baris    : {len(rows)}")
print(f"Kolom header   : {expected_fields}")
print(f"Header pertama : {header[0]!r}")
print(f"Header terakhir: {header[-1]!r}")

if expected_fields <= 1:
    print("STATUS: FAIL — CSV hanya terbaca sebagai 1 kolom.")
    print("Periksa delimiter atau simpan ulang sebagai CSV UTF-8.")
    sys.exit(2)

print("\nPosisi kolom penting:")
for column in ["Name", "State", "UUID", "Uptime / Days"]:
    if column in header:
        print(f"  {column:<18}: {header.index(column)}")
    else:
        print(f"  {column:<18}: TIDAK DITEMUKAN")

print("\nDistribusi jumlah field pada baris data:")
for field_count, number_of_rows in sorted(field_counts.items()):
    print(f"  {field_count} field: {number_of_rows} baris")

invalid_rows = [
    (line_number, len(row))
    for line_number, row in enumerate(rows[1:], start=2)
    if len(row) != expected_fields
]

print(f"\nBaris dengan jumlah field tidak sesuai header: {len(invalid_rows)}")
for line_number, field_count in invalid_rows[:20]:
    print(f"  Baris {line_number}: {field_count} field, seharusnya {expected_fields}")

if invalid_rows:
    print("\nSTATUS: FAIL — jumlah field tidak konsisten.")
    sys.exit(2)

print("\nSTATUS: PASS — struktur CSV konsisten.")
