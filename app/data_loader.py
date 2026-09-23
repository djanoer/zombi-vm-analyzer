# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — MODULE: data_loader.py
# ------------------------------------------------------------------------------
#  Lokasi : app/data_loader.py
#  Peran  : Loader CSV metrik utama dan CSV Power Off dengan schema berbeda.
#
#  PATCH NOTES (24 Sep 2026, v3):
#  - Ditemukan: berbagai file Power Off dari tool export berbeda memakai
#    nama kolom vCenter yang BERBEDA-BEDA ("Summary|Parent vCenter",
#    "Parent vCenter", dst.) -- menambah alias literal satu-per-satu
#    tidak scalable.
#  - DITAMBAHKAN: fallback AUTO-DETECT di normalize_power_off_columns().
#    Jika setelah pencocokan alias literal TIDAK ADA kolom "vCenter",
#    sistem mencari kolom lain yang namanya mengandung kata "vcenter"
#    (case-insensitive). Jika TEPAT SATU ditemukan, otomatis dipetakan
#    ke "vCenter" dengan info ke pengguna. Jika LEBIH DARI SATU
#    ditemukan, sistem menolak dengan error yang jelas (tidak menebak).
#  - Alias literal di POWER_OFF_COLUMN_ALIASES tetap dipertahankan
#    sebagai lapis pertama (lebih cepat & tidak perlu peringatan) untuk
#    variasi yang SUDAH diketahui.
# ==============================================================================
import re


import pandas as pd
import streamlit as st


from constants import (
    MEMORY_COL_CANDIDATES,
    NUMERIC_COLUMNS_BASE,
    UPTIME_UNKNOWN_TOKENS,
    INACTIVE_STATE_KEYWORDS,
    POWER_OFF_REQUIRED_COLUMNS,
    POWER_OFF_OPTIONAL_COLUMNS,
    POWER_OFF_COLUMN_ALIASES,
    PIC_COLUMN_ALIASES,
)
from csv_validation import validate_dataframe_structure, validate_key_values
from parsers import parse_numeric_verbose



def normalize_column_name(column):
    column = str(column).replace("\ufeff", "").replace("\xa0", " ")
    column = re.sub(r"\s+", " ", column).strip()
    return column.strip('"').strip("'").strip()



def _normalize_alias_lookup_key(column):
    """
    Normalisasi kunci untuk pencocokan alias yang TOLERAN terhadap:
    - Perbedaan kapitalisasi ("VCenter" vs "vCenter").
    - Spasi ekstra di sekitar tanda "|" ("Summary | Parent vCenter"
      vs "Summary|Parent vCenter").
    """
    normalized = normalize_column_name(column)
    normalized = re.sub(r"\s*\|\s*", "|", normalized)
    return normalized.lower()



_POWER_OFF_ALIAS_LOOKUP = {
    _normalize_alias_lookup_key(key): value
    for key, value in POWER_OFF_COLUMN_ALIASES.items()
}



def normalize_power_off_columns(dataframe):
    """
    Normalisasi nama kolom Power Off ke schema internal yang seragam.

    Urutan pencocokan kolom vCenter:
    1. Alias literal (POWER_OFF_COLUMN_ALIASES), case/space-tolerant.
    2. Auto-detect: kolom TERSISA yang namanya mengandung kata "vcenter"
       (case-insensitive). Hanya diterima jika PERSIS SATU kandidat
       ditemukan -- jika lebih dari satu, sistem menolak dan meminta
       standardisasi nama kolom, bukan menebak.
    """
    dataframe = dataframe.copy()
    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    rename_map = {}
    for column in dataframe.columns:
        lookup_key = _normalize_alias_lookup_key(column)
        if lookup_key in _POWER_OFF_ALIAS_LOOKUP:
            rename_map[column] = _POWER_OFF_ALIAS_LOOKUP[lookup_key]

    dataframe = dataframe.rename(columns=rename_map)

    if "vCenter" not in dataframe.columns:
        vcenter_like_columns = [
            column
            for column in dataframe.columns
            if "vcenter" in _normalize_alias_lookup_key(column)
        ]

        if len(vcenter_like_columns) == 1:
            detected_column = vcenter_like_columns[0]
            dataframe = dataframe.rename(columns={detected_column: "vCenter"})
            st.info(
                f"ℹ️ Kolom **'{detected_column}'** otomatis dikenali sebagai "
                "kolom vCenter (nama kolom tidak cocok dengan alias standar, "
                "tapi mengandung kata 'vCenter'). Mohon verifikasi hasil "
                "analisis Power Off pada file ini."
            )
        elif len(vcenter_like_columns) > 1:
            raise ValueError(
                "Ditemukan lebih dari satu kolom yang mengandung kata "
                f"'vCenter': {vcenter_like_columns}. Sistem tidak dapat "
                "menentukan otomatis kolom mana yang benar -- mohon "
                "standardisasi nama kolom pada file export, atau beri "
                "tahu developer untuk menambahkan alias eksplisit."
            )
        # Jika tidak ada kandidat sama sekali, biarkan validasi
        # POWER_OFF_REQUIRED_COLUMNS di bawah menangani error-nya
        # dengan pesan yang menyertakan daftar kolom aktual.

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
        "vCenter",
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

    if "vCenter" not in dataframe.columns:
        raise ValueError(
            "Kolom 'vCenter' tidak ditemukan pada file metrik. "
            "Kolom ini wajib untuk membangun Identity Key "
            "(vCenter + UUID) dan mencegah VM dari vCenter berbeda "
            "tercampur pada identity yang sama."
        )

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
    """
    Loader CSV Power Off (enrichment).

    Kontrak:
    - Name + Power State + Days Powered Off wajib tersedia.
    - vCenter wajib tersedia (via alias literal ATAU auto-detect).
    - UUID bersifat opsional pada file ini.
    """
    expected_columns = {
        "Name",
        "Power State",
        "Days Powered Off",
        "Power Off Days",
        "Days Power Off",
        "UUID",
        "Summary|Parent vCenter",
        "Parent vCenter",
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
            "Kolom wajib file Power Off tidak ditemukan setelah alias "
            f"mapping & auto-detect: {missing_columns}. Alias durasi yang "
            "didukung: 'Days Powered Off', 'Power Off Days', 'Days Power "
            "Off'. Alias vCenter yang didukung: 'Summary|Parent vCenter', "
            "'Parent vCenter', atau kolom apapun yang mengandung kata "
            "'vCenter'. Kolom yang terbaca dari file: "
            f"{list(dataframe.columns)}"
        )

    if dataframe.empty:
        raise ValueError("File Power Off kosong.")

    for column in POWER_OFF_OPTIONAL_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = pd.NA

    name_clean = (
        dataframe["Name"].astype(str).str.strip().str.lower()
    )
    uuid_clean = (
        dataframe["UUID"].astype("string").str.strip().str.lower()
        if "UUID" in dataframe.columns
        else pd.Series("", index=dataframe.index)
    )
    vcenter_clean = (
        dataframe["vCenter"].astype(str).str.strip().str.upper()
    )

    check_frame = pd.DataFrame(
        {
            "vcenter_clean": vcenter_clean,
            "name_clean": name_clean,
            "uuid_clean": uuid_clean.fillna(""),
        }
    )

    duplicated_mask = check_frame[["vcenter_clean", "name_clean"]].duplicated(keep=False)

    if duplicated_mask.any():
        ambiguous_groups = (
            check_frame.loc[duplicated_mask]
            .groupby(["vcenter_clean", "name_clean"])["uuid_clean"]
            .nunique()
        )
        truly_ambiguous = ambiguous_groups[ambiguous_groups > 1]

        if not truly_ambiguous.empty:
            raise ValueError(
                "File Power Off memiliki kombinasi vCenter+Name yang sama "
                f"dengan UUID berbeda: {truly_ambiguous.index.tolist()}. "
                "Tidak dapat diproses secara aman -- periksa data sumber."
            )

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

    before = len(combined)
    combined = combined.drop_duplicates(keep="first")
    removed = before - len(combined)

    if removed:
        st.info(
            f"ℹ️ {removed} baris duplikat identik (seluruh kolom sama) "
            "ditemukan saat penggabungan file dan dihapus otomatis."
        )

    return combined, failed_files, removed



def load_power_off_uploads(uploaded_files):
    """
    Muat & gabungkan CSV Power Off.

    CATATAN PENTING: setiap file diproses secara TERPISAH lewat
    process_power_off_data() sebelum digabung. Ini krusial karena file
    Anda terbukti memakai nama kolom vCenter yang BERBEDA antar file
    (mis. "Summary|Parent vCenter" di file 1, "Parent vCenter" di file
    2) -- masing-masing dinormalisasi ke "vCenter" secara independen
    SEBELUM digabung, sehingga penggabungan tetap konsisten walau
    format sumber berbeda-beda.
    """
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

    combined = combined.drop_duplicates(keep="first")

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



def process_pic_data(file):
    file_name = file.name.lower()

    if file_name.endswith(('.xls', '.xlsx')):
        file.seek(0)
        dataframe = pd.read_excel(file)
        dataframe.columns = [normalize_column_name(c) for c in dataframe.columns]
    else:
        expected_columns = {
            "Name", "UUID", "PIC Owner", "PIC", "Owner", "vCenter",
        }
        dataframe = _read_robust(file, expected_columns)

    rename_map = {}
    for col in dataframe.columns:
        lower_col = col.lower()
        if lower_col in PIC_COLUMN_ALIASES:
            rename_map[col] = PIC_COLUMN_ALIASES[lower_col]

    dataframe = dataframe.rename(columns=rename_map)

    if "Name" not in dataframe.columns and "UUID" not in dataframe.columns:
        raise ValueError("File harus memiliki setidaknya kolom Nama VM atau UUID.")
    if "PIC Owner" not in dataframe.columns:
        raise ValueError("File harus memiliki kolom PIC atau Owner.")

    if "Name" not in dataframe.columns:
        dataframe["Name"] = ""
    if "UUID" not in dataframe.columns:
        dataframe["UUID"] = ""
    if "vCenter" not in dataframe.columns:
        dataframe["vCenter"] = pd.NA

    dataframe["PIC Owner"] = dataframe["PIC Owner"].fillna("").astype(str).str.strip()

    return dataframe[["Name", "UUID", "vCenter", "PIC Owner"]]



def load_pic_uploads(uploaded_files):
    dataframe_list = []
    failed_files = []

    for file in uploaded_files:
        try:
            dataframe_list.append(process_pic_data(file))
        except Exception as error:
            failed_files.append((file.name, str(error)))

    if not dataframe_list:
        return None, failed_files

    combined = pd.concat(dataframe_list, ignore_index=True, sort=False)
    combined = combined.drop_duplicates(
        subset=["Name", "UUID", "vCenter"],
        keep="last",
    )
    return combined, failed_files
