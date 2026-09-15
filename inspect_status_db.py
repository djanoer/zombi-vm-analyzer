# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — UTILITY: inspect_status_db.py
# ------------------------------------------------------------------------------
#  Lokasi : app/inspect_status_db.py
#  Peran  : Membaca langsung isi status_tracking.db TANPA lewat UI Streamlit.
#  Cara pakai (dari folder app/, dengan venv aktif):
#      python inspect_status_db.py
#      python inspect_status_db.py "D:\path\lain\status_tracking.db"
# ------------------------------------------------------------------------------
#  UPDATE (14 Sep 2026): default path diperbarui mengikuti pemindahan database
#  ke folder data/ terpisah (lihat app_config.py). Sebelumnya utility ini
#  masih menunjuk ke app/status_tracking.db (lokasi lama) sehingga akan
#  melaporkan "file tidak ditemukan" meski database baru sudah aktif dipakai.
# ==============================================================================
import sqlite3
import sys

try:
    from app_config import STATUS_DATABASE_PATH
    DEFAULT_DB_PATH = STATUS_DATABASE_PATH
except ImportError:
    from pathlib import Path
    DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "status_tracking.db"

db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH

print(f"Mengecek database di: {db_path}\n")

import os
if not os.path.exists(db_path):
    print("❌ File database TIDAK ditemukan di lokasi tersebut.")
    print("   Pastikan Anda sudah membuka app dan minimal 1 kandidat HK tampil di tabel hasil,")
    print("   karena init_db() dipanggil otomatis saat render_results_section() jalan.")
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
    print("❌ Tabel 'vm_status' tidak ditemukan — skema belum terbuat dengan benar.")
    conn.close()
    sys.exit(1)

cur.execute(
    "SELECT vm_name, uuid, status, catatan, tanggal_update, updated_by "
    "FROM vm_status ORDER BY tanggal_update DESC"
)
rows = cur.fetchall()
cols = ["vm_name", "uuid", "status", "catatan", "tanggal_update", "updated_by"]

print(f"Jumlah baris tersimpan: {len(rows)}\n")
print(" | ".join(f"{c:<18}" for c in cols))
print("-" * 120)
for r in rows:
    print(" | ".join(f"{str(v):<18}" for v in r))

conn.close()
