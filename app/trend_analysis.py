# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: trend_analysis.py
# ------------------------------------------------------------------------------
# Peran:
# - Menyimpan snapshot observasi aktual VM.
# - Menghitung streak kandidat berdasarkan Identity Key.
# - Menyimpan UUID murni, vCenter, dan Identity Key secara terpisah.
# - Menyimpan evidence dari vROps relative date range.
#
# Identity:
# - Identity Key = vCenter + UUID.
# - UUID tetap disimpan sebagai UUID murni.
# - vCenter tetap disimpan sebagai VC01/VC02.
# - VM Powered Off tanpa UUID menggunakan vCenter + Name.
#
# Kompatibilitas:
# - Primary key lama dipertahankan selama masa trial.
# - Kolom baru ditambahkan secara additive.
# ==============================================================================

import shutil
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from app_config import (
    TREND_DATABASE_PATH,
    ensure_data_directory,
)
from constants import (
    TREND_ACTIONABLE_LABELS,
    TREND_LEGACY_CANDIDATE_COLUMN,
    TREND_METRIC_WINDOW_DEFAULT,
    TREND_SNAPSHOT_SOURCE_DEFAULT,
)
from error_messages import user_error


LEGACY_DB_PATH = (
    Path(__file__).resolve().parent
    / "trend_history.db"
)


def normalize_uuid(value):
    if value is None or pd.isna(value):
        return ""

    normalized = str(value).strip().lower()

    if normalized in {
        "",
        "-",
        "nan",
        "none",
        "null",
        "<na>",
    }:
        return ""

    return normalized


def normalize_vcenter(value):
    if value is None or pd.isna(value):
        return ""

    normalized = str(value).strip().upper()

    extracted = pd.Series(
        [normalized]
    ).str.extract(
        r"(VC\d+)",
        expand=False,
    ).iloc[0]

    if pd.isna(extracted):
        return ""

    return str(extracted).strip().upper()


def normalize_vm_name(value):
    if value is None or pd.isna(value):
        return ""

    return str(value).strip()


def normalize_vm_name_key(value):
    return normalize_vm_name(value).lower()


def normalize_observation_date(value):
    parsed = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(parsed):
        raise ValueError(
            f"Tanggal observasi tidak valid: {value}"
        )

    return parsed.date().isoformat()


def normalize_identity_value(value):
    if value is None or pd.isna(value):
        return ""

    normalized = str(value).strip().lower()

    if normalized in {
        "",
        "nan",
        "none",
        "null",
        "<na>",
    }:
        return ""

    return normalized


def _column_exists(
    connection,
    table_name,
    column_name,
):
    columns = {
        row[1]
        for row in connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    }

    return column_name in columns


def _add_column_if_missing(
    connection,
    table_name,
    column_name,
    definition,
):
    if not _column_exists(
        connection,
        table_name,
        column_name,
    ):
        connection.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {definition}"
        )


def migrate_legacy_database():
    ensure_data_directory()

    if (
        TREND_DATABASE_PATH.exists()
        or not LEGACY_DB_PATH.exists()
    ):
        return

    shutil.copy2(
        LEGACY_DB_PATH,
        TREND_DATABASE_PATH,
    )


def init_db(db_path=TREND_DATABASE_PATH):
    migrate_legacy_database()
    ensure_data_directory()

    connection = sqlite3.connect(db_path)

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS vm_trend_history (
                vm_name TEXT NOT NULL,
                uuid TEXT NOT NULL DEFAULT '',
                tanggal_proses TEXT NOT NULL,
                is_kandidat_disposal INTEGER NOT NULL,
                skor_idle REAL DEFAULT 0.0,
                PRIMARY KEY (
                    vm_name,
                    uuid,
                    tanggal_proses
                )
            )
            """
        )

        _add_column_if_missing(
            connection,
            "vm_trend_history",
            "pic_owner",
            "TEXT DEFAULT ''",
        )

        _add_column_if_missing(
            connection,
            "vm_trend_history",
            "status_hk",
            "TEXT DEFAULT ''",
        )

        _add_column_if_missing(
            connection,
            "vm_trend_history",
            "metric_window",
            (
                "TEXT DEFAULT "
                f"'{TREND_METRIC_WINDOW_DEFAULT}'"
            ),
        )

        _add_column_if_missing(
            connection,
            "vm_trend_history",
            "snapshot_source",
            (
                "TEXT DEFAULT "
                f"'{TREND_SNAPSHOT_SOURCE_DEFAULT}'"
            ),
        )

        _add_column_if_missing(
            connection,
            "vm_trend_history",
            "vcenter",
            "TEXT DEFAULT ''",
        )

        _add_column_if_missing(
            connection,
            "vm_trend_history",
            "identity_key",
            "TEXT DEFAULT ''",
        )

        _add_column_if_missing(
            connection,
            "vm_trend_history",
            "is_actionable_candidate",
            "INTEGER DEFAULT 0",
        )

        connection.commit()

    except sqlite3.Error as error:
        # HARD-06: rollback agar tidak ada skema setengah tertulis.
        connection.rollback()
        st.error(
            user_error(
                "Gagal menyiapkan database riwayat trend",
                str(error),
                "periksa folder data aplikasi bisa ditulis, "
                "lalu muat ulang halaman",
            )
        )
        raise

    finally:
        connection.close()


def _resolve_candidate_column(dataframe):
    if (
        "is_actionable_candidate"
        in dataframe.columns
    ):
        return "is_actionable_candidate"

    if (
        TREND_LEGACY_CANDIDATE_COLUMN
        in dataframe.columns
    ):
        return TREND_LEGACY_CANDIDATE_COLUMN

    return None


def _row_is_actionable_candidate(row):
    label = str(
        row.get("Label", "")
    ).strip()

    return int(
        label in set(
            TREND_ACTIONABLE_LABELS
        )
    )


def _build_identity_key(
    vm_uuid,
    vcenter,
    vm_name,
    state="",
):
    normalized_uuid = normalize_uuid(vm_uuid)
    normalized_vcenter = normalize_vcenter(vcenter)
    normalized_name = normalize_vm_name_key(vm_name)

    if normalized_uuid and normalized_vcenter:
        # FIX-02: format kanonis SELALU lowercase (selaras dengan
        # normalize_identity_value) agar streak trend tidak terpecah
        # menjadi dua grup ("VC01::.." vs "vc01::..").
        return (
            f"{normalized_vcenter.lower()}"
            f"::{normalized_uuid}"
        )

    state_text = str(
        state or ""
    ).strip().lower()

    is_powered_off = any(
        keyword in state_text
        for keyword in [
            "off",
            "suspend",
            "inactive",
        ]
    )

    if is_powered_off and normalized_name:
        # FIX-02: kanonis lowercase, lihat komentar di atas.
        vcenter_key = (
            normalized_vcenter.lower()
            or "unknown_vcenter"
        )

        return (
            f"{vcenter_key}"
            f"::NAME::{normalized_name}"
        )

    return ""


def _ensure_required_snapshot_columns(dataframe):
    required_columns = [
        "Name",
        "UUID",
        "vCenter",
        "Identity Key",
        "Label",
        "Skor Idle (0-100)",
        "PIC Owner",
        "Status HK",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            "Kolom snapshot wajib hilang: "
            + ", ".join(missing_columns)
        )


def record_period_snapshot(
    filtered_vms,
    tanggal_proses,
    db_path=TREND_DATABASE_PATH,
):
    """
    Simpan satu observasi aktual.

    Tanggal yang tidak dianalisis tidak dibuat
    sebagai record.
    """
    connection = None

    try:
        init_db(db_path)

        dataframe = filtered_vms.copy()

        _ensure_required_snapshot_columns(
            dataframe
        )

        observation_date = (
            normalize_observation_date(
                tanggal_proses
            )
        )

        dataframe["UUID"] = dataframe[
            "UUID"
        ].map(normalize_uuid)

        dataframe["vCenter"] = dataframe[
            "vCenter"
        ].map(normalize_vcenter)

        dataframe["Identity Key"] = (
            dataframe["Identity Key"]
            .map(normalize_identity_value)
        )

        invalid_identity_mask = (
            dataframe["Identity Key"] == ""
        )

        if invalid_identity_mask.any():
            invalid_rows = dataframe.loc[
                invalid_identity_mask
            ].head(10)

            raise ValueError(
                "Ditemukan Identity Key kosong "
                "pada snapshot. "
                f"Contoh: "
                f"{invalid_rows.to_dict('records')}"
            )

        if (
            dataframe["Identity Key"]
            .duplicated()
            .any()
        ):
            raise ValueError(
                "Ditemukan Identity Key duplikat "
                "dalam snapshot."
            )

        records = []

        for _, row in dataframe.iterrows():
            vm_name = normalize_vm_name(
                row.get("Name")
            )

            vm_uuid = normalize_uuid(
                row.get("UUID")
            )

            vcenter = normalize_vcenter(
                row.get("vCenter")
            )

            identity_key = normalize_identity_value(
                row.get("Identity Key")
            )

            if not identity_key:
                identity_key = _build_identity_key(
                    vm_uuid,
                    vcenter,
                    vm_name,
                    row.get("State", ""),
                )

            if not identity_key:
                raise ValueError(
                    f"Identity Key tidak valid "
                    f"untuk VM '{vm_name}'."
                )

            is_actionable_candidate = (
                _row_is_actionable_candidate(
                    row
                )
            )

            score = pd.to_numeric(
                row.get(
                    "Skor Idle (0-100)",
                    0.0,
                ),
                errors="coerce",
            )

            score = (
                0.0
                if pd.isna(score)
                else float(score)
            )

            pic_owner = str(
                row.get(
                    "PIC Owner",
                    "",
                )
            ).strip()

            status_hk = str(
                row.get(
                    "Status HK",
                    "",
                )
            ).strip()

            records.append(
                (
                    vm_name,
                    vm_uuid,
                    observation_date,
                    is_actionable_candidate,
                    score,
                    pic_owner,
                    status_hk,
                    TREND_METRIC_WINDOW_DEFAULT,
                    TREND_SNAPSHOT_SOURCE_DEFAULT,
                    vcenter,
                    identity_key,
                    is_actionable_candidate,
                )
            )

        connection = sqlite3.connect(db_path)

        connection.executemany(
            """
            INSERT INTO vm_trend_history (
                vm_name,
                uuid,
                tanggal_proses,
                is_kandidat_disposal,
                skor_idle,
                pic_owner,
                status_hk,
                metric_window,
                snapshot_source,
                vcenter,
                identity_key,
                is_actionable_candidate
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                vm_name,
                uuid,
                tanggal_proses
            )
            DO UPDATE SET
                is_kandidat_disposal =
                    excluded.is_kandidat_disposal,
                skor_idle =
                    excluded.skor_idle,
                pic_owner =
                    excluded.pic_owner,
                status_hk =
                    excluded.status_hk,
                metric_window =
                    excluded.metric_window,
                snapshot_source =
                    excluded.snapshot_source,
                vcenter =
                    excluded.vcenter,
                identity_key =
                    excluded.identity_key,
                is_actionable_candidate =
                    excluded.is_actionable_candidate
            """,
            records,
        )

        connection.commit()

        return True, None

    except Exception as error:
        if connection is not None:
            connection.rollback()

        return False, str(error)

    finally:
        if connection is not None:
            connection.close()


def load_trend_history(
    db_path=TREND_DATABASE_PATH,
):
    try:
        init_db(db_path)

        connection = sqlite3.connect(db_path)

        try:
            dataframe = pd.read_sql_query(
                "SELECT * FROM vm_trend_history",
                connection,
            )
        finally:
            connection.close()

        defaults = {
            "metric_window": (
                TREND_METRIC_WINDOW_DEFAULT
            ),
            "snapshot_source": (
                TREND_SNAPSHOT_SOURCE_DEFAULT
            ),
            "vcenter": "",
            "identity_key": "",
            "is_actionable_candidate": 0,
        }

        for column, default in defaults.items():
            if column not in dataframe.columns:
                dataframe[column] = default

        return dataframe

    except Exception:
        return pd.DataFrame(
            columns=[
                "vm_name",
                "uuid",
                "tanggal_proses",
                "is_kandidat_disposal",
                "skor_idle",
                "pic_owner",
                "status_hk",
                "metric_window",
                "snapshot_source",
                "vcenter",
                "identity_key",
                "is_actionable_candidate",
            ]
        )


def _reconstruct_legacy_identity_key(row):
    existing_identity = normalize_identity_value(
        row.get("identity_key", "")
    )

    if existing_identity:
        return existing_identity

    vm_uuid = normalize_uuid(
        row.get("uuid")
    )

    vcenter = normalize_vcenter(
        row.get("vcenter")
    )

    vm_name = normalize_vm_name(
        row.get("vm_name")
    )

    if vm_uuid and vcenter:
        # FIX-02: format kanonis SELALU lowercase agar konsisten dengan
        # key baru (normalize_identity_value). Key legacy yang tersimpan
        # tanpa identity_key tidak lagi terpecah menjadi grup "VC01::..".
        return (
            f"{vcenter.lower()}::{vm_uuid}"
        )

    if vm_name:
        return (
            "LEGACY::NAME::"
            f"{normalize_vm_name_key(vm_name)}"
        )

    return ""


def _empty_consistent_result():
    return pd.DataFrame(
        columns=[
            "Nama VM",
            "vCenter",
            "UUID",
            "Identity Key",
            "PIC Owner",
            "Status HK",
            "Jumlah Observasi Kandidat Berturut-turut",
            "Total Observasi",
            "Observasi Pertama",
            "Observasi Terakhir",
            "Jeda Observasi Maksimum (Hari)",
            "Skor Idle Terakhir",
            "Relative Period",
            "Sumber Snapshot",
        ]
    )


def _calculate_observation_gaps(group):
    dates = (
        group["tanggal_sortir"]
        .dropna()
        .sort_values(ascending=False)
    )

    if len(dates) <= 1:
        return None

    gaps = (
        dates
        - dates.shift(-1)
    ).dt.days.dropna()

    if gaps.empty:
        return None

    return int(gaps.max())


def compute_consistent_idle_vms(
    min_periods,
    db_path=TREND_DATABASE_PATH,
):
    history = load_trend_history(db_path)

    if history.empty:
        return _empty_consistent_result()

    history["identity_key"] = history.apply(
        _reconstruct_legacy_identity_key,
        axis=1,
    )

    history = history[
        history["identity_key"] != ""
    ].copy()

    if history.empty:
        return _empty_consistent_result()

    history["tanggal_sortir"] = pd.to_datetime(
        history["tanggal_proses"],
        errors="coerce",
    )

    history = history[
        history["tanggal_sortir"].notna()
    ].copy()

    if history.empty:
        return _empty_consistent_result()

    candidate_column = _resolve_candidate_column(
        history
    )

    if candidate_column is None:
        return _empty_consistent_result()

    results = []

    for identity_key, group in history.groupby(
        "identity_key",
        sort=False,
    ):
        group = group.sort_values(
            "tanggal_sortir",
            ascending=False,
        ).copy()

        group[candidate_column] = pd.to_numeric(
            group[candidate_column],
            errors="coerce",
        ).fillna(0).astype(int)

        streak = 0

        for _, row in group.iterrows():
            if row[candidate_column] == 1:
                streak += 1
            else:
                break

        if streak < int(min_periods):
            continue

        latest_record = group.iloc[0]
        oldest_record = group.iloc[-1]

        results.append(
            {
                "Nama VM": latest_record.get(
                    "vm_name",
                    "",
                ),
                "vCenter": normalize_vcenter(
                    latest_record.get(
                        "vcenter",
                        "",
                    )
                ),
                "UUID": normalize_uuid(
                    latest_record.get(
                        "uuid",
                        "",
                    )
                ),
                "Identity Key": identity_key,
                "PIC Owner": latest_record.get(
                    "pic_owner",
                    "",
                ),
                "Status HK": latest_record.get(
                    "status_hk",
                    "",
                ),
                "Jumlah Observasi Kandidat Berturut-turut": (
                    streak
                ),
                "Total Observasi": len(group),
                "Observasi Pertama": oldest_record.get(
                    "tanggal_proses",
                    "",
                ),
                "Observasi Terakhir": latest_record.get(
                    "tanggal_proses",
                    "",
                ),
                "Jeda Observasi Maksimum (Hari)": (
                    _calculate_observation_gaps(group)
                ),
                "Skor Idle Terakhir": latest_record.get(
                    "skor_idle",
                    0.0,
                ),
                "Relative Period": latest_record.get(
                    "metric_window",
                    TREND_METRIC_WINDOW_DEFAULT,
                ),
                "Sumber Snapshot": latest_record.get(
                    "snapshot_source",
                    TREND_SNAPSHOT_SOURCE_DEFAULT,
                ),
            }
        )

    result = pd.DataFrame(results)

    if result.empty:
        return _empty_consistent_result()

    return result.sort_values(
        [
            "Jumlah Observasi Kandidat "
            "Berturut-turut",
            "Observasi Terakhir",
        ],
        ascending=[False, False],
    ).reset_index(drop=True)


def count_recorded_observations(
    db_path=TREND_DATABASE_PATH,
):
    history = load_trend_history(db_path)

    if history.empty:
        return 0

    return history["tanggal_proses"].nunique()


def count_recorded_periods(
    db_path=TREND_DATABASE_PATH,
):
    """Wrapper kompatibilitas; makna aktual adalah observasi tercatat."""
    return count_recorded_observations(db_path)
