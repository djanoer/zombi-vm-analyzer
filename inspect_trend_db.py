# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — UTILITY: inspect_trend_db.py
# ------------------------------------------------------------------------------
#  Lokasi : app/inspect_trend_db.py
#  Peran  : Membaca langsung isi trend_history.db TANPA lewat UI Streamlit.
#           Fokus utama: mendeteksi drift format "identity_key" antar-tanggal
#           untuk VM yang sama (mis. akibat perubahan logika identity di
#           patch-patch sebelumnya), yang menyebabkan streak observasi
#           konsisten tidak pernah terakumulasi.
# ==============================================================================
import sqlite3
import sys
import os
from collections import defaultdict


try:
    from app_config import TREND_DATABASE_PATH  # type: ignore
    DEFAULT_DB_PATH = TREND_DATABASE_PATH
except ImportError:
    from pathlib import Path
    DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "trend_history.db"


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


if "vm_trend_history" not in tables:
    print("❌ Tabel 'vm_trend_history' tidak ditemukan.")
    conn.close()
    sys.exit(1)


cur.execute("PRAGMA table_info(vm_trend_history)")
available_columns = {row[1] for row in cur.fetchall()}
print(f"Kolom yang tersedia: {sorted(available_columns)}\n")


select_columns = [
    col
    for col in [
        "vm_name",
        "uuid",
        "vcenter",
        "identity_key",
        "tanggal_proses",
        "is_actionable_candidate",
        "is_kandidat_disposal",
        "skor_idle",
    ]
    if col in available_columns
]


cur.execute(
    f"SELECT {', '.join(select_columns)} FROM vm_trend_history "
    "ORDER BY vm_name, tanggal_proses"
)
rows = cur.fetchall()


print(f"Jumlah baris tersimpan: {len(rows)}\n")
print(" | ".join(f"{c:<20}" for c in select_columns))
print("-" * 140)
for r in rows:
    print(" | ".join(f"{str(v)[:20]:<20}" for v in r))


# ==============================================================================
# ANALISIS DRIFT: Kelompokkan berdasarkan vm_name, tampilkan SEMUA
# identity_key unik yang pernah tercatat untuk nama VM yang sama.
# Jika satu vm_name punya LEBIH DARI SATU identity_key unik, itu adalah
# indikasi kuat bahwa format Identity Key berubah antar-tanggal (drift),
# menyebabkan streak observasi konsisten terputus tanpa error.
# ==============================================================================
if "vm_name" in select_columns and "identity_key" in select_columns:
    name_to_keys = defaultdict(set)
    name_to_dates = defaultdict(list)

    vm_name_idx = select_columns.index("vm_name")
    identity_idx = select_columns.index("identity_key")
    date_idx = (
        select_columns.index("tanggal_proses")
        if "tanggal_proses" in select_columns
        else None
    )

    for r in rows:
        vm_name = r[vm_name_idx]
        identity_key = r[identity_idx]
        name_to_keys[vm_name].add(identity_key)
        if date_idx is not None:
            name_to_dates[vm_name].append((r[date_idx], identity_key))

    drifted_vms = {
        name: keys for name, keys in name_to_keys.items() if len(keys) > 1
    }

    print("\n" + "=" * 70)
    print("ANALISIS DRIFT IDENTITY KEY")
    print("=" * 70)

    if not drifted_vms:
        print(
            "✅ Tidak ditemukan drift. Setiap vm_name konsisten memiliki "
            "SATU identity_key yang sama di semua tanggal observasi."
        )
    else:
        print(
            f"⚠️ Ditemukan {len(drifted_vms)} VM dengan identity_key "
            "BERBEDA-BEDA antar tanggal (kemungkinan penyebab streak "
            "observasi konsisten tidak pernah terakumulasi):\n"
        )
        for name, keys in drifted_vms.items():
            print(f"  - VM '{name}':")
            for date_value, identity_key in sorted(name_to_dates[name]):
                print(f"      {date_value}  ->  {identity_key}")
            print()

        print(
            "REKOMENDASI: Reset database trend (hapus file ini) karena "
            "masih dalam masa trial, lalu jalankan analisis ulang dengan "
            "logika identity yang sudah final agar observasi konsisten "
            "dapat terakumulasi dengan benar ke depannya."
        )


conn.close()
