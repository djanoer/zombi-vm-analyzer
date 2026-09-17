# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: status_tracking.py
# ==============================================================================
"""
Module untuk tracking status housekeeping (HK) VM.
Fitur:
- Save Status HK (Pending/Approved/Rejected) dan Catatan
- Merge status dari database ke DataFrame
- Audit trail (updated_by, updated_at)
"""

import sqlite3
import pandas as pd
from datetime import datetime
import streamlit as st

from app_config import STATUS_DATABASE_PATH, ensure_data_directory


VALID_STATUSES = ["Pending", "Approved", "Rejected"]

# Kolom yang wajib ada pada skema BARU tabel vm_status.
_EXPECTED_COLUMNS = {"uuid", "name", "status", "notes", "updated_by", "updated_at"}
# Kolom skema LAMA (versi sebelum 17 Sep 2026) yang dimigrasi otomatis.
_LEGACY_COLUMNS = {"vm_name", "uuid", "status", "catatan", "tanggal_update", "updated_by"}


def get_db_connection():
    """Get SQLite connection dengan row factory."""
    ensure_data_directory()
    connection = sqlite3.connect(
        STATUS_DATABASE_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _create_new_schema(cursor):
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


def _migrate_legacy_schema_if_needed(cursor):
    """
    FIX Bug #1: deteksi tabel `vm_status` skema lama (vm_name/uuid/status/
    catatan/tanggal_update/updated_by, PK (vm_name, uuid)) dan migrasikan
    datanya ke skema baru (uuid/name/status/notes/updated_by/updated_at,
    PK (uuid, name)) TANPA menghapus histori status HK yang sudah tersimpan.

    Tanpa migrasi ini, INSERT ke skema baru akan selalu gagal dengan
    sqlite3.OperationalError setiap kali ada database lama peninggalan versi
    sebelumnya di server produksi.
    """
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='vm_status'"
    )
    table_exists = cursor.fetchone() is not None

    if not table_exists:
        _create_new_schema(cursor)
        return

    cursor.execute("PRAGMA table_info(vm_status)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if _EXPECTED_COLUMNS.issubset(existing_columns):
        # Skema sudah benar (baru), tidak ada yang perlu dimigrasi.
        return

    # Skema lama terdeteksi -> migrasi aman: rename, buat tabel baru, copy data, drop lama.
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
    # Jika skema lama juga tidak dikenali (kasus tak terduga), tabel lama tetap
    # disimpan sebagai vm_status_legacy (tidak dihapus) agar data tidak hilang,
    # walau tidak ikut dimigrasi otomatis.
    else:
        cursor.execute("DROP TABLE IF EXISTS vm_status")
        cursor.execute("ALTER TABLE vm_status_legacy RENAME TO vm_status")
        _create_new_schema(cursor)
        return

    cursor.execute("DROP TABLE vm_status_legacy")


def initialize_db():
    """Initialize database TANPA drop table (preserve historis)."""
    connection = get_db_connection()
    cursor = connection.cursor()

    _migrate_legacy_schema_if_needed(cursor)

    connection.commit()
    connection.close()


def get_all_statuses():
    """Get semua status dari database."""
    initialize_db()
    connection = get_db_connection()
    query = "SELECT uuid, name, status, notes, updated_by, updated_at FROM vm_status"
    dataframe = pd.read_sql_query(query, connection)
    connection.close()
    return dataframe


def _resolve_column(dataframe, candidates):
    """Kembalikan nama kolom pertama dari `candidates` yang benar-benar ada
    di `dataframe`, atau None jika tidak ada satu pun yang cocok.

    FIX Bug #2: dipakai agar kode ini tidak lagi hardcode satu nama kolom
    ("Name" saja / "Catatan" saja) yang ternyata berbeda dari nama kolom
    yang benar-benar dipakai oleh tabel yang ditampilkan ke pengguna.
    """
    for candidate in candidates:
        if candidate in dataframe.columns:
            return candidate
    return None

def merge_status_into_df(dataframe):
    """
    Merge status dari database ke DataFrame VM menggunakan Vectorized Mapping.
    Teknik ini jauh lebih aman dari pd.merge untuk menghindari corrupt index.
    """
    status_df = get_all_statuses()

    # Jika DB kosong, kembalikan default untuk kedua versi nama kolom
    if status_df.empty:
        dataframe["Status HK"] = "Pending"
        dataframe["Catatan HK"] = ""
        dataframe["Catatan"] = ""
        return dataframe

    # FIX 1: Urutkan DB descending agar selalu mengambil catatan PALING BARU
    if "updated_at" in status_df.columns:
        status_df["updated_at"] = pd.to_datetime(status_df["updated_at"], errors="coerce")
        status_df = status_df.sort_values(by="updated_at", ascending=False, na_position="last")

    # FIX 2: Standarisasi Key (hindari case-sensitive dan spasi tersembunyi)
    status_df["UUID_Clean"] = status_df["uuid"].fillna("").astype(str).str.strip()
    status_df["Name_Clean"] = status_df["name"].fillna("").astype(str).str.strip().str.lower()

    dataframe["UUID_Clean"] = dataframe["UUID"].fillna("").astype(str).str.strip() if "UUID" in dataframe.columns else ""
    dataframe["Name_Clean"] = dataframe["Name"].fillna("").astype(str).str.strip().str.lower()

    # Buat dictionary index untuk VLOOKUP ala Pandas
    valid_uuid_db = status_df[status_df["UUID_Clean"] != ""].drop_duplicates(subset=["UUID_Clean"], keep="first").set_index("UUID_Clean")
    valid_name_db = status_df.drop_duplicates(subset=["Name_Clean"], keep="first").set_index("Name_Clean")

    # Eksekusi Mapping (Mencari status dan catatan berdasarkan UUID)
    status_by_uuid = dataframe["UUID_Clean"].map(valid_uuid_db["status"])
    notes_by_uuid = dataframe["UUID_Clean"].map(valid_uuid_db["notes"])

    # Eksekusi Mapping (Mencari status dan catatan berdasarkan Nama VM)
    status_by_name = dataframe["Name_Clean"].map(valid_name_db["status"])
    notes_by_name = dataframe["Name_Clean"].map(valid_name_db["notes"])

    # FIX 3: Prioritaskan UUID. Jika UUID gagal/kosong, otomatis pakai hasil Nama VM.
    final_status = status_by_uuid.combine_first(status_by_name).fillna("Pending")
    final_notes = notes_by_uuid.combine_first(notes_by_name).fillna("")

    # Validasi jika status di luar ketentuan
    invalid_mask = ~final_status.isin(VALID_STATUSES)
    final_status.loc[invalid_mask] = "Pending"

    # FIX 4: Tulis ke dua nama kolom sekaligus untuk menjamin UI Streamlit membacanya
    dataframe["Status HK"] = final_status
    dataframe["Catatan HK"] = final_notes
    dataframe["Catatan"] = final_notes

    # Bersihkan kolom temporary agar tidak muncul di tabel
    dataframe = dataframe.drop(columns=["UUID_Clean", "Name_Clean"])

    return dataframe

def _get_clean_uuid(row):
    """
    Ekstrak UUID yang valid dari row.

    FIX Bug B: NaN pada kolom UUID sebelumnya dikonversi str(NaN) -> "nan"
    (string tidak kosong), sehingga salah dianggap UUID valid dan gagal
    fallback ke VM Name. Fungsi ini memastikan NaN/None/kosong -> None.

    Returns:
        str UUID (stripped) jika valid, None jika kosong/NaN
    """
    raw_uuid = row.get("UUID", None)
    if raw_uuid is None or pd.isna(raw_uuid):
        return None
    cleaned = str(raw_uuid).strip()
    return cleaned if cleaned != "" else None


def save_status_updates(original_df, edited_df, updated_by):
    initialize_db()
    connection = get_db_connection()
    cursor = connection.cursor()

    # Validasi input
    if original_df.empty or edited_df.empty:
        connection.close()
        return 0

    name_col_original = _resolve_column(original_df, ["Name", "Nama VM"])
    name_col_edited = _resolve_column(edited_df, ["Name", "Nama VM"])
    if name_col_original is None or name_col_edited is None:
        st.error(
            "❌ Kolom nama VM ('Name' atau 'Nama VM') tidak ditemukan di DataFrame."
        )
        connection.close()
        return 0

    notes_col_original = _resolve_column(original_df, ["Catatan HK", "Catatan"])
    notes_col_edited = _resolve_column(edited_df, ["Catatan HK", "Catatan"])
    if notes_col_original is None or notes_col_edited is None:
        st.error(
            "❌ Kolom catatan ('Catatan HK' atau 'Catatan') tidak ditemukan di DataFrame."
        )
        connection.close()
        return 0

    has_uuid = "UUID" in original_df.columns and "UUID" in edited_df.columns

    changed_rows = []

    for _, row in edited_df.iterrows():
        if name_col_edited not in row or pd.isna(row[name_col_edited]):
            continue

        vm_name = str(row[name_col_edited]).strip()

        # Coba ambil UUID langsung dari edited_df (jika UI menampilkannya)
        vm_uuid = _get_clean_uuid(row) if "UUID" in edited_df.columns else None

        # Cari baris aslinya di original_df
        if vm_uuid and "UUID" in original_df.columns:
            matching_rows = original_df[original_df["UUID"] == vm_uuid]
            match_type = "UUID"
        else:
            matching_rows = original_df[original_df[name_col_original] == vm_name]
            match_type = "VM Name"

        if matching_rows.empty:
            st.warning(f"⚠️ VM '{vm_name}' tidak ditemukan di data asli.")
            continue

        orig_row = matching_rows.iloc[0]

        # FIX UTAMA: Jika UI menghilangkan kolom UUID, ambil paksa dari original_df
        if not vm_uuid and "UUID" in original_df.columns:
            vm_uuid = _get_clean_uuid(orig_row)

        # Sanitasi dan komparasi (dari perbaikan kita di chat sebelumnya)
        orig_status = str(orig_row["Status HK"]).strip()
        edit_status = str(row["Status HK"]).strip()

        orig_note = "" if pd.isna(orig_row[notes_col_original]) else str(orig_row[notes_col_original]).strip()
        edit_note = "" if pd.isna(row[notes_col_edited]) else str(row[notes_col_edited]).strip()

        if (edit_status != orig_status) or (edit_note != orig_note):
            changed_rows.append(
                {
                    "uuid": vm_uuid if vm_uuid else "",  # Fallback murni jika memang tidak punya UUID
                    "name": vm_name,
                    "status": edit_status,
                    "notes": edit_note,
                    "match_type": match_type,
                }
            )

    if not changed_rows:
        connection.close()
        return 0

    current_time = datetime.now()
    updates = [
        (
            item["uuid"] if item["uuid"] else "",  # Simpan "" bukan None ke DB (konsisten dgn PRIMARY KEY)
            item["name"],
            item["status"],
            item["notes"],
            updated_by,
            current_time,
        )
        for item in changed_rows
    ]

    try:
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
    except sqlite3.Error as error:
        connection.close()
        # FIX 1: Gunakan toast alih-alih st.error yang permanen
        st.toast(f"Gagal menyimpan ke database: {error}", icon="🚨")
        return 0

    connection.close()

    # FIX 2: Gunakan toast alih-alih st.success yang permanen
    st.toast(f"Data berhasil disimpan ({len(updates)} VM).", icon="✅")

    return len(updates)
