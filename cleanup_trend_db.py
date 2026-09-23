# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — UTILITY: cleanup_trend_db.py
# ------------------------------------------------------------------------------
#  Lokasi : app/cleanup_trend_db.py
#  Peran  : Menghapus baris observasi trend LAMA (pra-refactor Identity Key)
#           yang memiliki identity_key kosong/tidak valid, TANPA menghapus
#           observasi BARU yang sudah benar. Ini mempertahankan progres
#           streak yang sudah terkumpul sejak logika Identity Key final
#           diterapkan (bukan reset total database).
#
#  Mode DEFAULT: dry-run (hanya menampilkan apa yang AKAN dihapus).
#  Untuk benar-benar menghapus, jalankan dengan flag --execute.
#
#  Contoh:
#      python cleanup_trend_db.py            # dry-run, aman
#      python cleanup_trend_db.py --execute  # benar-benar menghapus
# ==============================================================================
import sqlite3
import sys
import os
import shutil
from datetime import datetime


try:
    from app_config import TREND_DATABASE_PATH  # type: ignore
    DEFAULT_DB_PATH = TREND_DATABASE_PATH
except ImportError:
    from pathlib import Path
    DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "trend_history.db"


EXECUTE_MODE = "--execute" in sys.argv
db_path = str(DEFAULT_DB_PATH)


print(f"Mengecek database di: {db_path}\n")


if not os.path.exists(db_path):
    print("❌ File database TIDAK ditemukan di lokasi tersebut.")
    sys.exit(1)


conn = sqlite3.connect(db_path)
cur = conn.cursor()


cur.execute("PRAGMA table_info(vm_trend_history)")
available_columns = {row[1] for row in cur.fetchall()}

if "identity_key" not in available_columns:
    print("❌ Kolom 'identity_key' tidak ditemukan di tabel vm_trend_history.")
    conn.close()
    sys.exit(1)


# Baris "tidak valid" = identity_key NULL, kosong, atau token placeholder.
INVALID_TOKENS = ("", "nan", "none", "null", "-", "<na>")

cur.execute(
    """
    SELECT vm_name, uuid, vcenter, tanggal_proses, identity_key
    FROM vm_trend_history
    WHERE identity_key IS NULL
       OR TRIM(LOWER(identity_key)) IN (?, ?, ?, ?, ?, ?)
    ORDER BY vm_name, tanggal_proses
    """,
    INVALID_TOKENS,
)
invalid_rows = cur.fetchall()

cur.execute("SELECT COUNT(*) FROM vm_trend_history")
total_rows = cur.fetchone()[0]


print(f"Total baris di database saat ini : {total_rows}")
print(f"Baris dengan identity_key TIDAK VALID (akan dihapus): {len(invalid_rows)}\n")


if invalid_rows:
    print("Detail baris yang akan dihapus:")
    print(" | ".join(f"{c:<20}" for c in ["vm_name", "uuid", "vcenter", "tanggal_proses", "identity_key"]))
    print("-" * 120)
    for row in invalid_rows:
        print(" | ".join(f"{str(v)[:20]:<20}" for v in row))
    print()

    # Tampilkan juga tanggal unik yang terdampak, untuk konteks.
    affected_dates = sorted({row[3] for row in invalid_rows})
    print(f"Tanggal observasi yang seluruh barisnya tidak valid: {affected_dates}\n")
else:
    print("✅ Tidak ada baris tidak valid. Database sudah bersih.\n")
    conn.close()
    sys.exit(0)


remaining_after_cleanup = total_rows - len(invalid_rows)
print(
    f"Setelah cleanup, database akan menyisakan {remaining_after_cleanup} baris "
    "(observasi dengan identity_key valid tetap dipertahankan)."
)


if not EXECUTE_MODE:
    print(
        "\nℹ️  Ini adalah DRY-RUN. Tidak ada perubahan dilakukan pada database."
    )
    print(
        "    Jalankan ulang dengan flag --execute untuk benar-benar menghapus:"
    )
    print("    python cleanup_trend_db.py --execute")
    conn.close()
    sys.exit(0)


# ==============================================================================
# MODE EKSEKUSI: backup ringan (copy file) sebelum menghapus, lalu hapus
# baris tidak valid.
# ==============================================================================
backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copy2(db_path, backup_path)
print(f"\n📦 Backup dibuat di: {backup_path}")

cur.execute(
    """
    DELETE FROM vm_trend_history
    WHERE identity_key IS NULL
       OR TRIM(LOWER(identity_key)) IN (?, ?, ?, ?, ?, ?)
    """,
    INVALID_TOKENS,
)
deleted_count = cur.rowcount
conn.commit()

cur.execute("SELECT COUNT(*) FROM vm_trend_history")
final_count = cur.fetchone()[0]

print(f"\n✅ Berhasil menghapus {deleted_count} baris tidak valid.")
print(f"   Sisa baris di database: {final_count}")
print(
    "\nObservasi dengan identity_key valid (mis. tanggal 2026-09-21 dan "
    "2026-09-23 pada contoh Anda) TETAP TERSIMPAN. Jalankan analisis "
    "sekali lagi pada tanggal baru untuk mencapai minimum observasi "
    "konsisten yang dibutuhkan."
)

conn.close()
