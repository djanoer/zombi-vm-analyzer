# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: status_tracking.py
# ============================================================================

import sqlite3
import pandas as pd
from datetime import datetime

from app_config import STATUS_DATABASE_PATH, ensure_data_directory

VALID_STATUSES = ["Pending", "Approved", "Rejected"]


def get_db_connection():
    ensure_data_directory()
    connection = sqlite3.connect(
        STATUS_DATABASE_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    connection.row_factory = sqlite3.Row
    return connection


def initialize_db():
    connection = get_db_connection()
    cursor = connection.cursor()
    # Menggunakan nama tabel asli 'vm_status'.
    # (Pastikan database lama dihapus manual agar tidak terjadi konflik kolom 'name')
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vm_status (
            uuid TEXT,
            name TEXT,
            status TEXT,
            notes TEXT,
            updated_by TEXT,
            updated_at TIMESTAMP,
            PRIMARY KEY (uuid, name)
        )
        """
    )
    connection.commit()
    connection.close()


def get_all_statuses():
    initialize_db()
    connection = get_db_connection()
    query = "SELECT uuid, name, status, notes, updated_by, updated_at FROM vm_status"
    dataframe = pd.read_sql_query(query, connection)
    connection.close()
    return dataframe


def merge_status_into_df(dataframe):
    status_df = get_all_statuses()
    if status_df.empty:
        dataframe["Status HK"] = "Pending"
        dataframe["Catatan"] = ""
        return dataframe

    status_df = status_df.rename(
        columns={
            "uuid": "UUID",
            "name": "Name",
            "status": "DB_Status",
            "notes": "DB_Notes",
        }
    )

    dataframe["Name_Clean"] = dataframe["Name"].fillna("").astype(str).str.strip()
    dataframe["UUID_Clean"] = dataframe.get("UUID", "").fillna("").astype(str).str.strip()
    status_df["Name_Clean"] = status_df["Name"].fillna("").astype(str).str.strip()
    status_df["UUID_Clean"] = status_df["UUID"].fillna("").astype(str).str.strip()

    merged = pd.merge(
        dataframe,
        status_df[["Name_Clean", "UUID_Clean", "DB_Status", "DB_Notes"]],
        on=["Name_Clean", "UUID_Clean"],
        how="left",
    )

    merged["Status HK"] = merged["DB_Status"].fillna("Pending")
    invalid_mask = ~merged["Status HK"].isin(VALID_STATUSES)
    merged.loc[invalid_mask, "Status HK"] = "Pending"

    merged["Catatan"] = merged["DB_Notes"].fillna("")

    merged = merged.drop(
        columns=["Name_Clean", "UUID_Clean", "DB_Status", "DB_Notes"]
    )
    return merged


def save_status_updates(original_df, edited_df, updated_by):
    initialize_db()
    connection = get_db_connection()
    cursor = connection.cursor()

    changed_rows = []
    for index, row in edited_df.iterrows():
        orig_row = original_df.iloc[index]
        if (
            row["Status HK"] != orig_row["Status HK"]
            or row["Catatan"] != orig_row["Catatan"]
        ):
            changed_rows.append(
                {
                    "uuid": str(row.get("UUID", "")).strip(),
                    "name": str(row["Name"]).strip(),
                    "status": row["Status HK"],
                    "notes": str(row["Catatan"]),
                }
            )

    if not changed_rows:
        connection.close()
        return 0

    current_time = datetime.now()
    updates = [
        (
            item["uuid"],
            item["name"],
            item["status"],
            item["notes"],
            updated_by,
            current_time,
        )
        for item in changed_rows
    ]

    cursor.executemany(
        """
        INSERT INTO vm_status (uuid, name, status, notes, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(uuid, name) DO UPDATE SET
            status = excluded.status,
            notes = excluded.notes,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at
        """,
        updates,
    )

    connection.commit()
    connection.close()
    return len(updates)
