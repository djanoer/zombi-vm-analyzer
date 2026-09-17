# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — MODULE: trend_analysis.py
# ------------------------------------------------------------------------------
#  Lokasi : app/trend_analysis.py
#  Peran  : Penyimpanan dan perhitungan tren idle multi-periode.
#  Database: ../data/trend_history.db
#  Dipakai: main.py, trend_view.py
# ------------------------------------------------------------------------------
#  Kompatibilitas: migrasi satu kali dari app/trend_history.db jika tersedia.
# ==============================================================================
import shutil
import sqlite3
from pathlib import Path

import pandas as pd

from app_config import TREND_DATABASE_PATH, ensure_data_directory


LEGACY_DB_PATH = Path(__file__).resolve().parent / "trend_history.db"


def migrate_legacy_database():
    ensure_data_directory()
    if TREND_DATABASE_PATH.exists() or not LEGACY_DB_PATH.exists():
        return
    shutil.copy2(LEGACY_DB_PATH, TREND_DATABASE_PATH)


def init_db(db_path=TREND_DATABASE_PATH):
    migrate_legacy_database()
    ensure_data_directory()
    conn = sqlite3.connect(db_path)

    # 1. Buat tabel dasar jika belum ada
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vm_trend_history (
            vm_name TEXT NOT NULL,
            uuid TEXT NOT NULL DEFAULT '',
            tanggal_proses TEXT NOT NULL,
            is_kandidat_disposal INTEGER NOT NULL,
            skor_idle REAL DEFAULT 0.0,
            PRIMARY KEY (vm_name, uuid, tanggal_proses)
        )
    """)

    # --------------------------------------------------------------------------
    # FIX: MIGRATION - Tambahkan kolom PIC Owner & Status HK ke tabel lama
    # Menggunakan try-except karena ALTER TABLE ADD COLUMN akan error jika kolom sudah ada
    # --------------------------------------------------------------------------
    try:
        conn.execute("ALTER TABLE vm_trend_history ADD COLUMN pic_owner TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass # Kolom sudah ada

    try:
        conn.execute("ALTER TABLE vm_trend_history ADD COLUMN status_hk TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass # Kolom sudah ada
    # --------------------------------------------------------------------------

    conn.commit()
    conn.close()


def record_period_snapshot(filtered_vms, tanggal_proses, db_path=TREND_DATABASE_PATH):
    try:
        init_db(db_path)
        dataframe = filtered_vms.copy()
        if "UUID" not in dataframe.columns:
            dataframe["UUID"] = ""
        dataframe["UUID"] = dataframe["UUID"].fillna("").astype(str)

        # Siapkan array/list penampung data untuk dieksekusi secara bulk
        records = []
        for _, row in dataframe.iterrows():
            # Evaluasi apakah VM ini adalah kandidat melalui kolom 'Label'
            label_vm = str(row.get("Label", ""))

            # Perbaikan: Kandidat Zombie / Pengecualian (Rejected) tetap direkam tren skor idle-nya
            # Tapi flag is_kandidat_disposal hanya aktif jika dia benar-benar kandidat yang belum di-reject
            is_kandidat = 1 if label_vm in ["Kandidat Zombie", "Kandidat Disposal"] else 0

            # FIX: Ambil data PIC dan Status HK dari row
            pic_owner = str(row.get("PIC Owner", "")).strip()
            status_hk = str(row.get("Status HK", "")).strip()

            records.append((
                str(row["Name"]),
                str(row["UUID"]),
                str(tanggal_proses),
                is_kandidat,
                float(row.get("Skor Idle (0-100)", 0.0)),
                pic_owner,
                status_hk
            ))

        conn = sqlite3.connect(db_path)
        # Gunakan executemany untuk mempercepat query hingga 100x lipat
        # FIX: Tambahkan parameter pic_owner dan status_hk
        conn.executemany("""
            INSERT INTO vm_trend_history
                (vm_name, uuid, tanggal_proses, is_kandidat_disposal, skor_idle, pic_owner, status_hk)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(vm_name, uuid, tanggal_proses) DO UPDATE SET
                is_kandidat_disposal = excluded.is_kandidat_disposal,
                skor_idle = excluded.skor_idle,
                pic_owner = excluded.pic_owner,
                status_hk = excluded.status_hk
        """, records)

        conn.commit()
        conn.close()
        return True, None
    except Exception as error:
        return False, str(error)


def load_trend_history(db_path=TREND_DATABASE_PATH):
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        dataframe = pd.read_sql_query("SELECT * FROM vm_trend_history", conn)
        conn.close()
        return dataframe
    except Exception:
        # FIX: Sesuaikan list kolom kosong dengan skema baru
        return pd.DataFrame(
            columns=[
                "vm_name", "uuid", "tanggal_proses",
                "is_kandidat_disposal", "skor_idle",
                "pic_owner", "status_hk"
            ]
        )


def compute_consistent_idle_vms(min_periods, db_path=TREND_DATABASE_PATH):
    history = load_trend_history(db_path)
    if history.empty:
        # FIX: Tambahkan PIC Owner dan Status HK agar tampil di tabel hasil Trend
        return pd.DataFrame(
            columns=[
                "Nama VM", "UUID", "PIC Owner", "Status HK",
                "Jumlah Periode Idle Berturut-turut",
                "Periode Terakhir",
            ]
        )

    # Konversi kolom tanggal_proses dari text menjadi objek DateTime
    history['tanggal_sortir'] = pd.to_datetime(history['tanggal_proses'], errors='coerce')

    results = []
    for (vm_name, uuid), group in history.groupby(["vm_name", "uuid"]):
        # Sortir menggunakan kolom DateTime, bukan text string (Terbaru ke Terlama)
        group = group.sort_values("tanggal_sortir", ascending=False)
        streak = 0

        for _, row in group.iterrows():
            if row["is_kandidat_disposal"] == 1:
                streak += 1
            else:
                break

        if streak >= min_periods:
            # FIX: Ambil data PIC dan Status dari catatan TERBARU (index 0 karena sudah disortir descending)
            latest_record = group.iloc[0]

            results.append({
                "Nama VM": vm_name,
                "UUID": uuid,
                "PIC Owner": latest_record.get("pic_owner", ""),
                "Status HK": latest_record.get("status_hk", ""),
                "Jumlah Periode Idle Berturut-turut": streak,
                "Periode Terakhir": latest_record["tanggal_proses"],
            })

    result = pd.DataFrame(results)
    if not result.empty:
        result = result.sort_values(
            "Jumlah Periode Idle Berturut-turut",
            ascending=False,
        ).reset_index(drop=True)
    return result


def count_recorded_periods(db_path=TREND_DATABASE_PATH):
    history = load_trend_history(db_path)
    return 0 if history.empty else history["tanggal_proses"].nunique()
