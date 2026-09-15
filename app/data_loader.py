# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — MODULE: data_loader.py
# ------------------------------------------------------------------------------
#  Lokasi : app/data_loader.py
#  Peran  : Loader CSV metrik utama dan CSV Power Off dengan schema berbeda.
#  UPDATE (15 Sep 2026):
#  - Mendukung dua alias durasi Power Off:
#      * Days Powered Off
#      * Power Off Days
#  - Keduanya dinormalisasi menjadi nama internal:
#      * Days Powered Off
#  - Perbedaan metadata Power Off tidak menggagalkan proses selama kolom kunci
#    Name, Power State, durasi Power Off, dan UUID tersedia.
# ==============================================================================
import re

import pandas as pd
import streamlit as st

from constants import (
    MEMORY_COL_CANDIDATES,
    NUMERIC_COLUMNS_BASE,
    UPTIME_UNKNOWN_TOKENS,
    INACTIVE_STATE_KEYWORDS,
)
from csv_validation import validate_dataframe_structure, validate_key_values
from parsers import parse_numeric_verbose


POWER_OFF_REQUIRED_COLUMNS = [
    "Name",
    "Power State",
    "Days Powered Off",
    "UUID",
]

POWER_OFF_COLUMN_ALIASES = {
    "Power Off Days": "Days Powered Off",
    "Days Power Off": "Days Powered Off",
    "Days Powered Off": "Days Powered Off",
}


def normalize_column_name(column):
    column = str(column).replace("\ufeff", "").replace("\xa0", " ")
    column = re.sub(r"\s+", " ", column).strip()
    return column.strip('"').strip("'").strip()


def normalize_power_off_columns(dataframe):
    """Normalisasi nama kolom Power Off ke schema internal yang seragam."""
    dataframe = dataframe.copy()
    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    rename_map = {
        column: POWER_OFF_COLUMN_ALIASES[column]
        for column in dataframe.columns
        if column in POWER_OFF_COLUMN_ALIASES
    }

    dataframe = dataframe.rename(columns=rename_map)
    return dataframe


def _read_candidate(file, encoding, separator):
    file.seek(0)
    return pd.read_csv(
        file,
        sep=separator,
        engine="python",
        skipinitialspace=True,
        encoding=encoding,
    )


def _score(dataframe, expected):
    detected = {
        normalize_column_name(column)
        for column in dataframe.columns
    }
    return len(detected.intersection(expected)) * 100 + dataframe.shape[1]


def _read_robust(file, expected_columns):
    candidates = []

    for encoding in ["utf-8-sig", "utf-8", "latin1"]:
        for separator in [",", ";", "\t"]:
            try:
                dataframe = _read_candidate(
                    file,
                    encoding,
                    separator,
                )

                if dataframe.shape[1] > 1:
                    dataframe.columns = [
                        normalize_column_name(column)
                        for column in dataframe.columns
                    ]
                    candidates.append(
                        (_score(dataframe, expected_columns), dataframe)
                    )

            except (
                UnicodeDecodeError,
                pd.errors.EmptyDataError,
                pd.errors.ParserError,
            ):
                continue

    if not candidates:
        raise ValueError(
            "CSV tidak dapat dibaca menjadi beberapa kolom."
        )

    dataframe = max(
        candidates,
        key=lambda item: item[0],
    )[1]

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    return dataframe.loc[
        :,
        ~dataframe.columns.duplicated(),
    ]

def process_data(file):
    expected_columns = {
        "Name",
        "State",
        "Uptime / Days",
        "Summary|vSphere Tag",
        "CPU Percentile 95%",
        "IOPS Percentile 95%",
        "Throughput Percentile 95%",
        "Network I/O | Usage Rate (KBps) - 95th Percentile",
        "Status Idle",
        *MEMORY_COL_CANDIDATES,
    }

    dataframe = _read_robust(file, expected_columns)

    if dataframe.empty:
        raise ValueError("File CSV metrik kosong.")

    memory_column = next(
        (
            column
            for column in MEMORY_COL_CANDIDATES
            if column in dataframe.columns
        ),
        MEMORY_COL_CANDIDATES[-1],
    )

    validate_dataframe_structure(
        dataframe,
        memory_column,
    )
    validate_key_values(dataframe)
    return dataframe

def process_power_off_data(file):
    expected_columns = {
        "Name",
        "Power State",
        "Days Powered Off",
        "Power Off Days",
        "Days Power Off",
        "UUID",
    }

    dataframe = _read_robust(file, expected_columns)
    dataframe = normalize_power_off_columns(dataframe)

    missing_columns = [
        column
        for column in POWER_OFF_REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            "Kolom wajib file Power Off tidak ditemukan setelah alias mapping: "
            f"{missing_columns}. Alias durasi yang didukung: "
            "'Days Powered Off', 'Power Off Days', dan 'Days Power Off'."
        )

    if dataframe.empty:
        raise ValueError("File Power Off kosong.")

    return dataframe


def load_and_merge_uploads(uploaded_files):
    dataframe_list = []
    failed_files = []

    for file in uploaded_files:
        try:
            dataframe_list.append(process_data(file))
        except Exception as error:
            failed_files.append((file.name, str(error)))

    if not dataframe_list:
        return None, failed_files, 0

    combined = pd.concat(
        dataframe_list,
        ignore_index=True,
    )

    combined = combined.loc[
        :,
        ~combined.columns.duplicated(),
    ]

    removed = 0

    if "Name" in combined.columns:
        before = len(combined)
        keys = (
            ["Name", "UUID"]
            if "UUID" in combined.columns
            else ["Name"]
        )
        combined = combined.drop_duplicates(
            subset=keys,
            keep="first",
        )
        removed = before - len(combined)

    return combined, failed_files, removed


def load_power_off_uploads(uploaded_files):
    dataframe_list = []
    failed_files = []

    for file in uploaded_files:
        try:
            dataframe_list.append(
                process_power_off_data(file)
            )
        except Exception as error:
            failed_files.append((file.name, str(error)))

    if not dataframe_list:
        return None, failed_files

    combined = pd.concat(
        dataframe_list,
        ignore_index=True,
        sort=False,
    )

    combined = combined.drop_duplicates(
        subset=["Name", "UUID"],
        keep="first",
    )

    return combined, failed_files


def resolve_memory_column(dataframe):
    return next(
        (
            column
            for column in MEMORY_COL_CANDIDATES
            if column in dataframe.columns
        ),
        MEMORY_COL_CANDIDATES[-1],
    )


def flag_data_quality(dataframe):
    dataframe = dataframe.copy()
    dataframe["Kualitas Data"] = "Lengkap"

    mask = (
        dataframe["Uptime / Days"]
        .astype(str)
        .str.strip()
        .isin(UPTIME_UNKNOWN_TOKENS)
    )

    dataframe.loc[
        mask,
        "Kualitas Data",
    ] = "Tidak Diketahui"

    return dataframe


def parse_numeric_columns(dataframe, memory_column):
    dataframe = dataframe.copy()
    failures = {}

    for column in NUMERIC_COLUMNS_BASE + [memory_column]:
        if column in dataframe.columns:
            parsed = dataframe[column].apply(
                parse_numeric_verbose
            )

            dataframe[column] = parsed.apply(
                lambda value: value[0]
            ).astype(float)

            failed_count = int(
                (
                    ~parsed.apply(
                        lambda value: value[1]
                    )
                ).sum()
            )

            if failed_count:
                failures[column] = failed_count

    return dataframe, failures


def normalize_state_column(dataframe):
    dataframe = dataframe.copy()
    dataframe["State"] = (
        dataframe["State"]
        .astype(str)
        .str.strip()
    )

    dataframe.loc[
        dataframe["State"].str.lower() == "nan",
        "State",
    ] = "Unknown"

    states = sorted(
        dataframe["State"]
        .dropna()
        .unique()
        .tolist()
    )

    active = [
        state
        for state in states
        if not any(
            keyword in state.lower()
            for keyword in INACTIVE_STATE_KEYWORDS
        )
    ]

    return dataframe, states, active
