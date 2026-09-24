# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: status_tracking.py
# ==============================================================================
"""
Module untuk tracking status housekeeping (HK) VM dan PIC Owner.

PATCH NOTES (21 Sep 2026):
- Identity utama BERUBAH dari UUID+Name menjadi Identity Key
  (vCenter + UUID, fallback vCenter + Name) via app/identity_utils.py.
  Ini menutup risiko cross-vCenter collision: UUID yang sama di VC01 dan
  VC02 kini menghasilkan Identity Key yang berbeda, sehingga status HK
  dan PIC Owner tidak lagi bisa "menular" ke VM yang salah.
- Schema database (vm_status, vm_pic_mapping) DIMIGRASIKAN dari
  PRIMARY KEY (uuid, name) menjadi PRIMARY KEY (identity_key). Migrasi
  berjalan otomatis saat initialize_db() dipanggil, TANPA menghapus data
  lama -- data lama direkonstruksi dengan Identity Key legacy
  ("LEGACY::UUID::..." / "LEGACY::NAME::...") yang tidak akan pernah
  collide dengan Identity Key modern (selalu berformat "VC0x::...").
- merge_status_into_df() kini mencocokkan dengan urutan prioritas:
    1. Identity Key modern (vCenter+UUID / vCenter+Name).
    2. Identity Key legacy (UUID-only / Name-only) untuk data lama
       yang belum sempat dimigrasikan ulang oleh user (VM tidak
       dianalisis lagi setelah upgrade).
- save_status_updates() dan bulk_save_pic_mapping() kini menggunakan
  kolom "Identity Key" yang sudah dibangun oleh main.py, BUKAN
  menurunkan ulang UUID dari index DataFrame.
"""


import sqlite3
from datetime import datetime


import pandas as pd
import streamlit as st


from app_config import (
    STATUS_DATABASE_PATH,
    ensure_data_directory,
)
from identity_utils import (
    build_identity_key,
    build_legacy_identity_key,
    invalid_identity_mask,
    normalize_uuid_scalar,
    normalize_vcenter_scalar,
)


VALID_STATUSES = [
    "Need Confirm",
    "Approved",
    "Rejected",
    "No Feedback",
]


_NEW_SCHEMA_COLUMNS = {
    "vm_status": {
        "identity_key", "vcenter", "uuid", "name",
        "status", "notes", "updated_by", "updated_at",
    },
    "vm_pic_mapping": {
        "identity_key", "vcenter", "uuid", "name",
        "pic_owner", "source", "mapped_by", "mapped_at",
    },
}

_OLD_SCHEMA_COLUMNS = {
    "vm_status": {"uuid", "name", "status", "notes", "updated_by", "updated_at"},
    "vm_pic_mapping": {"uuid", "name", "pic_owner", "source", "mapped_by", "mapped_at"},
}


def normalize_uuid(value):
    """Normalisasi UUID; kosong/token null -> string kosong (bukan pd.NA)."""
    normalized = normalize_uuid_scalar(value)
    return "" if pd.isna(normalized) else normalized


def normalize_vcenter(value):
    """Normalisasi vCenter; kosong/tidak valid -> string kosong."""
    normalized = normalize_vcenter_scalar(value)
    return "" if pd.isna(normalized) else normalized


def normalize_name(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().lower()


def get_db_connection():
    ensure_data_directory()

    connection = sqlite3.connect(
        STATUS_DATABASE_PATH,
        detect_types=(
            sqlite3.PARSE_DECLTYPES
            | sqlite3.PARSE_COLNAMES
        ),
    )
    connection.row_factory = sqlite3.Row

    return connection


def _table_exists(cursor, table_name):
    cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    )
    return cursor.fetchone() is not None


def _get_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _create_new_schema(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vm_status (
            identity_key TEXT NOT NULL,
            vcenter TEXT NOT NULL DEFAULT '',
            uuid TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Need Confirm',
            notes TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP,
            PRIMARY KEY (identity_key)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vm_pic_mapping (
            identity_key TEXT NOT NULL,
            vcenter TEXT NOT NULL DEFAULT '',
            uuid TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT '',
            pic_owner TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            mapped_by TEXT NOT NULL DEFAULT '',
            mapped_at TIMESTAMP,
            PRIMARY KEY (identity_key)
        )
        """
    )


def _migrate_table_to_identity_key(cursor, table_name, insert_columns):
    """
    Migrasi satu tabel dari PRIMARY KEY (uuid, name) lama menjadi
    PRIMARY KEY (identity_key), TANPA menghapus data. Identity Key
    lama direkonstruksi dengan namespace "LEGACY::" (lihat
    identity_utils.build_legacy_identity_key), sehingga tidak akan
    bertabrakan dengan Identity Key modern yang selalu berformat
    "VC0x::...".
    """
    legacy_table = f"{table_name}_legacy_uuidname"

    cursor.execute(
        f"ALTER TABLE {table_name} RENAME TO {legacy_table}"
    )

    _create_new_schema(cursor)

    cursor.execute(f"SELECT * FROM {legacy_table}")
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()

    migrated_rows = []
    skipped_count = 0

    for row in rows:
        row_dict = dict(zip(columns, row))
        legacy_uuid = row_dict.get("uuid", "")
        legacy_name = row_dict.get("name", "")

        identity_key = build_legacy_identity_key(legacy_uuid, legacy_name)

        if not identity_key:
            skipped_count += 1
            continue

        values = [identity_key, ""]  # identity_key, vcenter (unknown="")
        # FIX-01: pakai normalize_uuid() (aman pd.NA -> ""), bukan
        # normalize_uuid_scalar(...) or "" yang crash saat hasil pd.NA.
        values.append(normalize_uuid(legacy_uuid))
        values.append(str(legacy_name or ""))
        values.extend(
            row_dict.get(column, "") for column in insert_columns
        )
        migrated_rows.append(tuple(values))

    if migrated_rows:
        placeholders = ", ".join(["?"] * (4 + len(insert_columns)))
        column_list = ", ".join(
            ["identity_key", "vcenter", "uuid", "name"] + insert_columns
        )
        cursor.executemany(
            f"""
            INSERT INTO {table_name} ({column_list})
            VALUES ({placeholders})
            ON CONFLICT(identity_key) DO NOTHING
            """,
            migrated_rows,
        )

    if skipped_count:
        st.warning(
            f"⚠️ Migrasi database '{table_name}': {skipped_count} baris "
            "lama dilewati karena tidak memiliki UUID maupun Name yang "
            "dapat digunakan untuk membentuk identity."
        )

    cursor.execute(f"DROP TABLE {legacy_table}")


def _migrate_legacy_schema_if_needed(cursor):
    table_insert_columns = {
        "vm_status": ["status", "notes", "updated_by", "updated_at"],
        "vm_pic_mapping": ["pic_owner", "source", "mapped_by", "mapped_at"],
    }

    for table_name, insert_columns in table_insert_columns.items():
        if not _table_exists(cursor, table_name):
            continue

        existing_columns = _get_columns(cursor, table_name)

        if "identity_key" in existing_columns:
            # Sudah schema modern.
            continue

        if _OLD_SCHEMA_COLUMNS[table_name].issubset(existing_columns):
            _migrate_table_to_identity_key(
                cursor, table_name, insert_columns
            )
        else:
            # Schema tidak dikenali sama sekali -- backup dan mulai baru
            # agar aplikasi tidak crash. Data lama tetap tersimpan di
            # tabel *_unknown_schema untuk investigasi manual.
            backup_table = f"{table_name}_unknown_schema"
            cursor.execute(
                f"ALTER TABLE {table_name} RENAME TO {backup_table}"
            )
            st.warning(
                f"⚠️ Schema tabel '{table_name}' tidak dikenali. Data "
                f"lama diarsipkan ke '{backup_table}' untuk investigasi "
                "manual; tabel baru dibuat kosong."
            )

    _create_new_schema(cursor)


def initialize_db():
    connection = get_db_connection()

    try:
        cursor = connection.cursor()
        _migrate_legacy_schema_if_needed(cursor)
        connection.commit()
    finally:
        connection.close()


def get_all_statuses():
    initialize_db()

    connection = get_db_connection()

    try:
        query_hk = """
            SELECT identity_key, vcenter, uuid, name, status, notes, updated_at
            FROM vm_status
        """

        query_pic = """
            SELECT identity_key, vcenter, uuid, name, pic_owner, mapped_at
            FROM vm_pic_mapping
        """

        df_hk = pd.read_sql_query(query_hk, connection)
        df_pic = pd.read_sql_query(query_pic, connection)

        return df_hk, df_pic
    finally:
        connection.close()


def _prepare_master_identity(dataframe):
    """
    Pastikan dataframe punya kolom "Identity Key" valid. Jika sudah ada
    (kasus normal -- dibangun oleh main.py), gunakan langsung. Jika
    belum ada (dataframe berdiri sendiri, mis. dari upload PIC), bangun
    di sini menggunakan identity_utils dengan fallback Name TANPA syarat
    Powered Off (karena file PIC tidak punya kolom State).
    """
    result = dataframe.copy()

    if "Identity Key" in result.columns:
        result["Identity Key"] = (
            result["Identity Key"].astype("string").str.strip()
        )
        return result

    result = build_identity_key(
        result,
        require_powered_off_for_fallback=False,
    )
    return result


def _legacy_identity_lookup_keys(dataframe):
    """
    Bangun Identity Key legacy (namespace LEGACY::) dari UUID/Name pada
    dataframe master, untuk mencocokkan histori status/PIC lama yang
    belum sempat dimigrasikan ulang.
    """
    uuid_column = dataframe["UUID"] if "UUID" in dataframe.columns else pd.Series("", index=dataframe.index)
    name_column = dataframe["Name"] if "Name" in dataframe.columns else pd.Series("", index=dataframe.index)

    return pd.Series(
        [
            build_legacy_identity_key(uuid_value, name_value) or ""
            for uuid_value, name_value in zip(uuid_column, name_column)
        ],
        index=dataframe.index,
    )


def merge_status_into_df(dataframe):
    """
    Merge status HK dan PIC Owner menggunakan Identity Key.

    Prioritas matching:
    1. Identity Key modern (vCenter + UUID, atau vCenter + Name untuk
       Power Off tanpa UUID).
    2. Identity Key legacy (data lama sebelum vCenter dikenal sistem).
    """
    result = _prepare_master_identity(dataframe)
    result["_Legacy_Identity"] = _legacy_identity_lookup_keys(result)

    df_hk, df_pic = get_all_statuses()

    result["Status HK"] = "Need Confirm"
    result["Catatan HK"] = ""
    result["Catatan"] = ""
    result["PIC Owner"] = ""

    if not df_hk.empty:
        if "updated_at" in df_hk.columns:
            df_hk["updated_at"] = pd.to_datetime(
                df_hk["updated_at"], errors="coerce"
            )
            df_hk = df_hk.sort_values(
                by="updated_at", ascending=False, na_position="last"
            )

        hk_by_identity = (
            df_hk.drop_duplicates(subset=["identity_key"], keep="first")
            .set_index("identity_key")
        )

        final_status = (
            result["Identity Key"]
            .map(hk_by_identity["status"])
            .combine_first(
                result["_Legacy_Identity"].map(hk_by_identity["status"])
            )
            .fillna("Need Confirm")
        )

        final_notes = (
            result["Identity Key"]
            .map(hk_by_identity["notes"])
            .combine_first(
                result["_Legacy_Identity"].map(hk_by_identity["notes"])
            )
            .fillna("")
        )

        invalid_status_mask = ~final_status.isin(VALID_STATUSES)
        final_status.loc[invalid_status_mask] = "Need Confirm"

        result["Status HK"] = final_status
        result["Catatan HK"] = final_notes
        result["Catatan"] = final_notes

    if not df_pic.empty:
        if "mapped_at" in df_pic.columns:
            df_pic["mapped_at"] = pd.to_datetime(
                df_pic["mapped_at"], errors="coerce"
            )
            df_pic = df_pic.sort_values(
                by="mapped_at", ascending=False, na_position="last"
            )

        pic_by_identity = (
            df_pic.drop_duplicates(subset=["identity_key"], keep="first")
            .set_index("identity_key")
        )

        final_pic = (
            result["Identity Key"]
            .map(pic_by_identity["pic_owner"])
            .combine_first(
                result["_Legacy_Identity"].map(pic_by_identity["pic_owner"])
            )
            .fillna("")
        )

        result["PIC Owner"] = final_pic

    return result.drop(columns=["_Legacy_Identity"], errors="ignore")


def _resolve_column(dataframe, candidates):
    for candidate in candidates:
        if candidate in dataframe.columns:
            return candidate
    return None


def _clean_cell(value):
    return "" if pd.isna(value) else str(value).strip()


def save_status_updates(original_df, edited_df, updated_by):
    """
    Simpan perubahan Status HK, Catatan, dan PIC Owner.

    Identity Key (vCenter+UUID / vCenter+Name) menjadi kunci utama,
    BUKAN UUID/index DataFrame. original_df dan edited_df WAJIB memiliki
    kolom "Identity Key" yang identik urutannya (dijamin oleh
    results_view.py karena keduanya diturunkan dari display_dataframe
    yang sama).
    """
    initialize_db()

    if original_df.empty or edited_df.empty:
        return 0

    if "Identity Key" not in original_df.columns:
        st.error("❌ Kolom 'Identity Key' tidak tersedia pada data asal.")
        return 0

    if "Identity Key" not in edited_df.columns:
        st.error("❌ Kolom 'Identity Key' tidak tersedia pada data editor.")
        return 0

    notes_col_original = _resolve_column(original_df, ["Catatan", "Catatan HK"])
    notes_col_edited = _resolve_column(edited_df, ["Catatan", "Catatan HK"])
    pic_col_original = _resolve_column(original_df, ["PIC Owner"])
    pic_col_edited = _resolve_column(edited_df, ["PIC Owner"])

    if not notes_col_original or not notes_col_edited:
        st.error("❌ Kolom Catatan tidak tersedia pada data.")
        return 0

    original_by_identity = (
        original_df.set_index(
            original_df["Identity Key"].astype("string").str.strip()
        )
    )

    connection = get_db_connection()
    cursor = connection.cursor()

    hk_updates = []
    pic_updates = []
    current_time = datetime.now()

    try:
        for _, row in edited_df.iterrows():
            identity_key = str(row.get("Identity Key", "")).strip()

            if not identity_key or identity_key.lower() in {"nan", "none", "null"}:
                continue

            if identity_key not in original_by_identity.index:
                st.error(
                    f"Baris asal tidak ditemukan untuk Identity Key "
                    f"'{identity_key}'."
                )
                continue

            original_row = original_by_identity.loc[identity_key]
            if isinstance(original_row, pd.DataFrame):
                original_row = original_row.iloc[0]

            vm_name = str(original_row.get("Name", "")).strip()
            vm_uuid = normalize_uuid(original_row.get("UUID", ""))
            vm_vcenter = normalize_vcenter(original_row.get("vCenter", ""))

            original_status = str(
                original_row.get("Status HK", "Need Confirm")
            ).strip()
            edited_status = str(
                row.get("Status HK", "Need Confirm")
            ).strip()

            if edited_status not in VALID_STATUSES:
                edited_status = "Need Confirm"

            original_note = _clean_cell(original_row.get(notes_col_original))
            edited_note = _clean_cell(row.get(notes_col_edited))

            if edited_status != original_status or edited_note != original_note:
                hk_updates.append(
                    (
                        identity_key,
                        vm_vcenter,
                        vm_uuid,
                        vm_name,
                        edited_status,
                        edited_note,
                        updated_by,
                        current_time,
                    )
                )

            if pic_col_original and pic_col_edited:
                original_pic = _clean_cell(original_row.get(pic_col_original))
                edited_pic = _clean_cell(row.get(pic_col_edited))

                if edited_pic != original_pic:
                    pic_updates.append(
                        (
                            identity_key,
                            vm_vcenter,
                            vm_uuid,
                            vm_name,
                            edited_pic,
                            "Manual UI",
                            updated_by,
                            current_time,
                        )
                    )

        if not hk_updates and not pic_updates:
            return 0

        if hk_updates:
            cursor.executemany(
                """
                INSERT INTO vm_status (
                    identity_key, vcenter, uuid, name,
                    status, notes, updated_by, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(identity_key) DO UPDATE SET
                    vcenter = excluded.vcenter,
                    uuid = excluded.uuid,
                    name = excluded.name,
                    status = excluded.status,
                    notes = excluded.notes,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at
                """,
                hk_updates,
            )

        if pic_updates:
            cursor.executemany(
                """
                INSERT INTO vm_pic_mapping (
                    identity_key, vcenter, uuid, name,
                    pic_owner, source, mapped_by, mapped_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(identity_key) DO UPDATE SET
                    vcenter = excluded.vcenter,
                    uuid = excluded.uuid,
                    name = excluded.name,
                    pic_owner = excluded.pic_owner,
                    source = excluded.source,
                    mapped_by = excluded.mapped_by,
                    mapped_at = excluded.mapped_at
                """,
                pic_updates,
            )

        connection.commit()

    except sqlite3.Error as error:
        connection.rollback()
        st.toast(f"Gagal menyimpan ke database: {error}", icon="🚨")
        return 0

    finally:
        connection.close()

    total_updates = len(hk_updates) + len(pic_updates)

    st.toast(
        f"Data berhasil disimpan "
        f"(HK: {len(hk_updates)}, PIC: {len(pic_updates)}).",
        icon="✅",
    )

    return total_updates


def bulk_save_pic_mapping(pic_dataframe, updated_by):
    """
    Simpan data PIC dari upload Excel/CSV.

    Identity Key dibangun dari vCenter+UUID (jika ada), fallback
    vCenter+Name TANPA syarat Powered Off (karena file PIC tidak
    memiliki kolom State). Baris tanpa vCenter DITOLAK secara eksplisit
    -- tidak ada fallback Name-only tanpa vCenter, karena berisiko
    ambigu lintas-vCenter.
    """
    if pic_dataframe is None or pic_dataframe.empty:
        return 0

    initialize_db()

    identity_dataframe = build_identity_key(
        pic_dataframe,
        require_powered_off_for_fallback=False,
    )

    invalid_mask = invalid_identity_mask(identity_dataframe["Identity Key"])

    if invalid_mask.any():
        invalid_rows = identity_dataframe.loc[invalid_mask].head(10)
        st.error(
            f"❌ {int(invalid_mask.sum())} baris PIC dilewati karena "
            "tidak dapat dibentuk Identity Key (vCenter kosong, atau "
            "Name & UUID kosong). "
            f"Contoh: {invalid_rows[['Name', 'vCenter', 'UUID']].to_dict('records')}"
        )

    valid_dataframe = identity_dataframe.loc[~invalid_mask].copy()

    connection = get_db_connection()
    cursor = connection.cursor()
    current_time = datetime.now()
    updates = []

    try:
        for _, row in valid_dataframe.iterrows():
            pic_owner = str(row.get("PIC Owner", "")).strip()

            if not pic_owner or pic_owner.lower() == "nan":
                continue

            identity_key = str(row["Identity Key"]).strip()
            vm_name = str(row.get("Name", "")).strip()
            vm_uuid = normalize_uuid(row.get("UUID", ""))
            vm_vcenter = normalize_vcenter(row.get("vCenter", ""))

            updates.append(
                (
                    identity_key,
                    vm_vcenter,
                    vm_uuid,
                    vm_name,
                    pic_owner,
                    "Bulk Upload",
                    updated_by,
                    current_time,
                )
            )

        if not updates:
            return 0

        cursor.executemany(
            """
            INSERT INTO vm_pic_mapping (
                identity_key, vcenter, uuid, name,
                pic_owner, source, mapped_by, mapped_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(identity_key) DO UPDATE SET
                vcenter = excluded.vcenter,
                uuid = excluded.uuid,
                name = excluded.name,
                pic_owner = excluded.pic_owner,
                source = excluded.source,
                mapped_by = excluded.mapped_by,
                mapped_at = excluded.mapped_at
            """,
            updates,
        )

        connection.commit()

    except sqlite3.Error as error:
        connection.rollback()
        st.toast(f"Gagal bulk insert PIC: {error}", icon="🚨")
        return 0

    finally:
        connection.close()

    return len(updates)
