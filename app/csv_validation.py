# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — MODULE: csv_validation.py
# ------------------------------------------------------------------------------
#  Lokasi : app/csv_validation.py
#  Peran  : Validasi struktur dan kolom KUNCI (bukan validasi format numerik).
# ==============================================================================
from constants import REQUIRED_COLUMNS_BASE

def validate_dataframe_structure(dataframe, memory_column):
    required_columns = REQUIRED_COLUMNS_BASE + [memory_column]
    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if dataframe.shape[1] <= 1:
        raise ValueError(
            "CSV hanya terbaca sebagai 1 kolom. Periksa delimiter atau encoding."
        )

    if missing_columns:
        raise ValueError(
            "Kolom wajib tidak ditemukan setelah CSV dibaca: "
            f"{missing_columns}."
        )

    # Cegah KeyError dengan memastikan kolom ada sebelum dicek
    for column in ["Name", "State", "UUID"]:
        if column in dataframe.columns:
            non_empty = (
                dataframe[column]
                .fillna("")
                .astype(str)
                .str.strip()
                .ne("")
            )
            if not non_empty.any():
                raise ValueError(
                    f"Kolom kunci '{column}' ditemukan tetapi seluruh nilainya kosong."
                )

    return dataframe

def validate_key_values(dataframe):
    """Hanya memvalidasi Name & State tidak boleh KOSONG SEMUA. Format nilai
    metrik numerik (termasuk Status Idle) TIDAK divalidasi di sini — biarkan
    parse_numeric_columns() di data_loader.py yang menangani secara toleran."""
    name_values = dataframe["Name"].fillna("").astype(str).str.strip()
    state_values = dataframe["State"].fillna("").astype(str).str.strip()

    if name_values.eq("").all():
        raise ValueError("Kolom Name ditemukan tetapi seluruh nilainya kosong.")
    if state_values.eq("").all():
        raise ValueError("Kolom State ditemukan tetapi seluruh nilainya kosong.")

    return dataframe
