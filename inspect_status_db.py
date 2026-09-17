# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — UTILITY: inspect_status_db.py
# ------------------------------------------------------------------------------
#  Lokasi : app/inspect_status_db.py
#  Peran  : Membaca langsung isi status_tracking.db TANPA lewat UI Streamlit.
# ==============================================================================
import sqlite3
import sys
import os

try:
    # FIX PYLANCE: Beritahu Pylance untuk mengabaikan peringatan import resolusi statis
    from app_config import STATUS_DATABASE_PATH  # type: ignore
    DEFAULT_DB_PATH = STATUS_DATABASE_PATH
except ImportError:
    from pathlib import Path
    # Handle secara dinamis jika dieksekusi dari root
    DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "status_tracking.db"

db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH

print(f"Mengecek database di: {db_path}\n")

if not os.path.exists(db_path):
    print("❌ File database TIDAK ditemukan di lokasi tersebut.")
    print(f"   Lokasi default sekarang: {DEFAULT_DB_PATH}")
    sys.exit(1)

file_size_kb = os.path.getsize(db_path) / 1024
print(f"✅ File ditemukan. Ukuran: {file_size_kb:.2f} KB\n")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cur.fetchall()]
print(f"Tabel yang ada di database: {tables}\n")

if "vm_status" not in tables:
    print("❌ Tabel 'vm_status' tidak ditemukan.")
    conn.close()
    sys.exit(1)

# FIX: Gunakan nama kolom skema BARU (name, notes, updated_at)
# bukan skema lama (vm_name, catatan, tanggal_update)
cur.execute(
    "SELECT uuid, name, status, notes, updated_at, updated_by "
    "FROM vm_status ORDER BY updated_at DESC"
)
rows = cur.fetchall()
cols = ["uuid", "name", "status", "notes", "updated_at", "updated_by"]

print(f"Jumlah baris tersimpan: {len(rows)}\n")
print(" | ".join(f"{c:<18}" for c in cols))
print("-" * 120)
for r in rows:
    # Memotong string jika terlalu panjang agar rapi di terminal
    print(" | ".join(f"{str(v)[:18]:<18}" for v in r))

conn.close()
