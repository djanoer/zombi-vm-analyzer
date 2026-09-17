# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: status_tracking.py
# ==============================================================================
"""
Module untuk tracking status housekeeping (HK) VM dan PIC Owner.
Fitur:
- Save Status HK, Catatan, dan PIC Owner
- Merge status dan PIC dari database terpisah ke DataFrame (Vectorized Mapping)
- Auto-migrate legacy schema dan handle UUID Fallbacks
"""

import sqlite3
import pandas as pd
from datetime import datetime
import streamlit as st

from app_config import STATUS_DATABASE_PATH, ensure_data_directory

# FIX TASK 1: Update list status ke best practice (ITSM/ITIL)
VALID_STATUSES = ["Need Confirm", "Approved", "Rejected", "No Feedback"]

_EXPECTED_COLUMNS = {"uuid", "name", "status", "notes", "updated_by", "updated_at"}
_LEGACY_COLUMNS = {"vm_name", "uuid", "status", "catatan", "tanggal_update", "updated_by"}


def get_db_connection():
    ensure_data_directory()
    connection = sqlite3.connect(
        STATUS_DATABASE_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _create_new_schema(cursor):
    # Tabel Housekeeping Status
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

    # FIX TASK 1: Buat tabel baru untuk PIC Owner Mapping (Independent Lifecycle)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vm_pic_mapping (
            uuid TEXT,
            name TEXT,
            pic_owner TEXT,
            source TEXT,
            mapped_by TEXT,
            mapped_at TIMESTAMP,
            PRIMARY KEY (uuid, name)
        )
        """
    )


def _migrate_legacy_schema_if_needed(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vm_status'")
    table_exists = cursor.fetchone() is not None

    if not table_exists:
        _create_new_schema(cursor)
        return

    cursor.execute("PRAGMA table_info(vm_status)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if _EXPECTED_COLUMNS.issubset(existing_columns):
        # Tabel HK aman. Pastikan tabel PIC juga di-create jika belum ada.
        _create_new_schema(cursor)
        return

    cursor.execute("ALTER TABLE vm_status RENAME TO vm_status_legacy")
    _create_new_schema(cursor)

    cursor.execute("PRAGMA table_info(vm_status_legacy)")
    legacy_columns = {row[1] for row in cursor.fetchall()}

    if _LEGACY_COLUMNS.issubset(legacy_columns):
        cursor.execute(
            """
            INSERT INTO vm_status (uuid, name, status, notes, updated_by, updated_at)
            SELECT COALESCE(uuid, ''), vm_name, status, catatan, updated_by, tanggal_update
            FROM vm_status_legacy
            """
        )
    else:
        cursor.execute("DROP TABLE IF EXISTS vm_status")
        cursor.execute("ALTER TABLE vm_status_legacy RENAME TO vm_status")
        _create_new_schema(cursor)
        return

    cursor.execute("DROP TABLE vm_status_legacy")


def initialize_db():
    connection = get_db_connection()
    cursor = connection.cursor()
    _migrate_legacy_schema_if_needed(cursor)
    connection.commit()
    connection.close()


def get_all_statuses():
    initialize_db()
    connection = get_db_connection()
    query_hk = "SELECT uuid, name, status, notes, updated_at FROM vm_status"
    query_pic = "SELECT uuid, name, pic_owner, mapped_at FROM vm_pic_mapping"

    df_hk = pd.read_sql_query(query_hk, connection)
    df_pic = pd.read_sql_query(query_pic, connection)
    connection.close()
    return df_hk, df_pic


def _resolve_column(dataframe, candidates):
    for candidate in candidates:
        if candidate in dataframe.columns:
            return candidate
    return None


def merge_status_into_df(dataframe):
    """
    Merge status HK dan PIC Owner menggunakan Vectorized Mapping secara paralel.
    """
    df_hk, df_pic = get_all_statuses()

    # Pre-fill defaults
    dataframe["Status HK"] = "Need Confirm"
    dataframe["Catatan HK"] = ""
    dataframe["Catatan"] = ""
    dataframe["PIC Owner"] = ""

    # Standarisasi kunci master dari dataframe tabel
    dataframe["UUID_Clean"] = dataframe["UUID"].fillna("").astype(str).str.strip() if "UUID" in dataframe.columns else ""
    dataframe["Name_Clean"] = dataframe["Name"].fillna("").astype(str).str.strip().str.lower()

    # =========================================================================
    # PROCESSING 1: HOUSEKEEPING STATUS (HK)
    # =========================================================================
    if not df_hk.empty:
        if "updated_at" in df_hk.columns:
            df_hk["updated_at"] = pd.to_datetime(df_hk["updated_at"], errors="coerce")
            df_hk = df_hk.sort_values(by="updated_at", ascending=False, na_position="last")

        df_hk["UUID_Clean"] = df_hk["uuid"].fillna("").astype(str).str.strip()
        df_hk["Name_Clean"] = df_hk["name"].fillna("").astype(str).str.strip().str.lower()

        valid_uuid_hk = df_hk[df_hk["UUID_Clean"] != ""].drop_duplicates(subset=["UUID_Clean"], keep="first").set_index("UUID_Clean")
        valid_name_hk = df_hk.drop_duplicates(subset=["Name_Clean"], keep="first").set_index("Name_Clean")

        # Map HK by UUID, fallback by Name
        final_status = dataframe["UUID_Clean"].map(valid_uuid_hk["status"]).combine_first(
                       dataframe["Name_Clean"].map(valid_name_hk["status"])
        ).fillna("Need Confirm")

        final_notes = dataframe["UUID_Clean"].map(valid_uuid_hk["notes"]).combine_first(
                      dataframe["Name_Clean"].map(valid_name_hk["notes"])
        ).fillna("")

        # Validasi
        invalid_mask = ~final_status.isin(VALID_STATUSES)
        final_status.loc[invalid_mask] = "Need Confirm"

        dataframe["Status HK"] = final_status
        dataframe["Catatan HK"] = final_notes
        dataframe["Catatan"] = final_notes

    # =========================================================================
    # PROCESSING 2: PIC OWNER MAPPING
    # =========================================================================
    if not df_pic.empty:
        if "mapped_at" in df_pic.columns:
            df_pic["mapped_at"] = pd.to_datetime(df_pic["mapped_at"], errors="coerce")
            df_pic = df_pic.sort_values(by="mapped_at", ascending=False, na_position="last")

        df_pic["UUID_Clean"] = df_pic["uuid"].fillna("").astype(str).str.strip()
        df_pic["Name_Clean"] = df_pic["name"].fillna("").astype(str).str.strip().str.lower()

        valid_uuid_pic = df_pic[df_pic["UUID_Clean"] != ""].drop_duplicates(subset=["UUID_Clean"], keep="first").set_index("UUID_Clean")
        valid_name_pic = df_pic.drop_duplicates(subset=["Name_Clean"], keep="first").set_index("Name_Clean")

        # Map PIC by UUID, fallback by Name
        final_pic = dataframe["UUID_Clean"].map(valid_uuid_pic["pic_owner"]).combine_first(
                    dataframe["Name_Clean"].map(valid_name_pic["pic_owner"])
        ).fillna("")

        dataframe["PIC Owner"] = final_pic

    # Cleanup temporary
    dataframe = dataframe.drop(columns=["UUID_Clean", "Name_Clean"])
    return dataframe


def _get_clean_uuid(row):
    raw_uuid = row.get("UUID", None)
    if raw_uuid is None or pd.isna(raw_uuid):
        return None
    cleaned = str(raw_uuid).strip()
    return cleaned if cleaned != "" else None


def save_status_updates(original_df, edited_df, updated_by):
    """
    Save perubahan ke tabel HK dan tabel PIC secara independen.
    """
    initialize_db()
    connection = get_db_connection()
    cursor = connection.cursor()

    if original_df.empty or edited_df.empty:
        connection.close()
        return 0

    name_col_original = _resolve_column(original_df, ["Name", "Nama VM"])
    name_col_edited = _resolve_column(edited_df, ["Name", "Nama VM"])
    notes_col_original = _resolve_column(original_df, ["Catatan HK", "Catatan"])
    notes_col_edited = _resolve_column(edited_df, ["Catatan HK", "Catatan"])

    # Kolom PIC Owner
    pic_col_orig = _resolve_column(original_df, ["PIC Owner"])
    pic_col_edit = _resolve_column(edited_df, ["PIC Owner"])

    if not all([name_col_original, name_col_edited, notes_col_original, notes_col_edited]):
        st.error("❌ Terjadi kesalahan: Kolom krusial (Nama VM/Catatan) hilang dari tabel.")
        connection.close()
        return 0

    hk_updates = []
    pic_updates = []
    current_time = datetime.now()

    for _, row in edited_df.iterrows():
        if name_col_edited not in row or pd.isna(row[name_col_edited]):
            continue

        vm_name = str(row[name_col_edited]).strip()
        vm_uuid = _get_clean_uuid(row) if "UUID" in edited_df.columns else None

        if vm_uuid and "UUID" in original_df.columns:
            matching_rows = original_df[original_df["UUID"] == vm_uuid]
        else:
            matching_rows = original_df[original_df[name_col_original] == vm_name]

        if matching_rows.empty:
            continue

        orig_row = matching_rows.iloc[0]
        if not vm_uuid and "UUID" in original_df.columns:
            vm_uuid = _get_clean_uuid(orig_row)

        safe_uuid = vm_uuid if vm_uuid else ""

        # -------------------------------------------------------------
        # CEK DELTA: HK STATUS & NOTES
        # -------------------------------------------------------------
        orig_status = str(orig_row.get("Status HK", "Need Confirm")).strip()
        edit_status = str(row.get("Status HK", "Need Confirm")).strip()
        orig_note = "" if pd.isna(orig_row[notes_col_original]) else str(orig_row[notes_col_original]).strip()
        edit_note = "" if pd.isna(row[notes_col_edited]) else str(row[notes_col_edited]).strip()

        if (edit_status != orig_status) or (edit_note != orig_note):
            hk_updates.append((safe_uuid, vm_name, edit_status, edit_note, updated_by, current_time))

        # -------------------------------------------------------------
        # CEK DELTA: PIC OWNER (Hanya dieksekusi jika kolom PIC ada di layar)
        # -------------------------------------------------------------
        if pic_col_orig and pic_col_edit:
            orig_pic = "" if pd.isna(orig_row[pic_col_orig]) else str(orig_row[pic_col_orig]).strip()
            edit_pic = "" if pd.isna(row[pic_col_edit]) else str(row[pic_col_edit]).strip()

            if edit_pic != orig_pic:
                # Disimpan dengan flag "Manual UI" untuk audit
                pic_updates.append((safe_uuid, vm_name, edit_pic, "Manual UI", updated_by, current_time))

    # =========================================================================
    # DATABASE BATCH EXECUTION
    # =========================================================================
    if not hk_updates and not pic_updates:
        connection.close()
        return 0

    try:
        # Eksekusi Update HK
        if hk_updates:
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
                hk_updates,
            )

        # Eksekusi Update PIC
        if pic_updates:
            cursor.executemany(
                """
                INSERT INTO vm_pic_mapping (uuid, name, pic_owner, source, mapped_by, mapped_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(uuid, name) DO UPDATE SET
                    pic_owner = excluded.pic_owner,
                    source = excluded.source,
                    mapped_by = excluded.mapped_by,
                    mapped_at = excluded.mapped_at
                """,
                pic_updates,
            )

        connection.commit()
    except sqlite3.Error as error:
        connection.close()
        st.toast(f"Gagal menyimpan ke database: {error}", icon="🚨")
        return 0

    connection.close()

    total_updates = len(hk_updates) + len(pic_updates)
    st.toast(f"Data berhasil disimpan (HK: {len(hk_updates)}, PIC: {len(pic_updates)}).", icon="✅")

    return total_updates
