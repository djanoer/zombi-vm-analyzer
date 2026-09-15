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
    conn.commit()
    conn.close()


def record_period_snapshot(filtered_vms, tanggal_proses, db_path=TREND_DATABASE_PATH):
    try:
        init_db(db_path)
        dataframe = filtered_vms.copy()
        if "UUID" not in dataframe.columns:
            dataframe["UUID"] = ""
        dataframe["UUID"] = dataframe["UUID"].fillna("").astype(str)

        conn = sqlite3.connect(db_path)
        for _, row in dataframe.iterrows():
            conn.execute("""
                INSERT INTO vm_trend_history
                    (vm_name, uuid, tanggal_proses, is_kandidat_disposal, skor_idle)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(vm_name, uuid, tanggal_proses) DO UPDATE SET
                    is_kandidat_disposal = excluded.is_kandidat_disposal,
                    skor_idle = excluded.skor_idle
            """, (
                str(row["Name"]),
                str(row["UUID"]),
                str(tanggal_proses),
                int(bool(row.get("Is Kandidat Disposal", False))),
                float(row.get("Skor Idle (0-100)", 0.0)),
            ))
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
        return pd.DataFrame(
            columns=[
                "vm_name", "uuid", "tanggal_proses",
                "is_kandidat_disposal", "skor_idle",
            ]
        )


def compute_consistent_idle_vms(min_periods, db_path=TREND_DATABASE_PATH):
    history = load_trend_history(db_path)
    if history.empty:
        return pd.DataFrame(
            columns=[
                "Nama VM", "UUID",
                "Jumlah Periode Idle Berturut-turut",
                "Periode Terakhir",
            ]
        )

    results = []
    for (vm_name, uuid), group in history.groupby(["vm_name", "uuid"]):
        group = group.sort_values("tanggal_proses", ascending=False)
        streak = 0
        for _, row in group.iterrows():
            if row["is_kandidat_disposal"] == 1:
                streak += 1
            else:
                break

        if streak >= min_periods:
            results.append({
                "Nama VM": vm_name,
                "UUID": uuid,
                "Jumlah Periode Idle Berturut-turut": streak,
                "Periode Terakhir": group.iloc[0]["tanggal_proses"],
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
