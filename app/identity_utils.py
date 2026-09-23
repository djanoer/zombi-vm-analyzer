# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: identity_utils.py
# ------------------------------------------------------------------------------
# PATCH v2 (21 Sep 2026):
# - build_identity_key() mendapat parameter baru
#   `require_powered_off_for_fallback` (default True, TIDAK mengubah
#   perilaku main.py/disposal_rules.py). Jika False, fallback
#   vCenter+Name aktif untuk SEMUA baris tanpa UUID (bukan hanya Power
#   Off) -- dibutuhkan oleh status_tracking.py untuk PIC mapping, karena
#   file PIC tidak memiliki kolom State sama sekali sehingga fallback
#   Power-Off-only tidak akan pernah aktif untuk kasus tersebut.
# - Ditambahkan build_legacy_identity_key() untuk migrasi database lama
#   (status_tracking.py) yang belum memiliki vCenter sama sekali.
# ==============================================================================

import pandas as pd

from constants import (
    IDENTITY_INVALID_TOKENS,
    IDENTITY_KEY_SEPARATOR,
    INACTIVE_STATE_KEYWORDS,
)


LEGACY_UUID_PREFIX = "LEGACY::UUID::"
LEGACY_NAME_PREFIX = "LEGACY::NAME::"


def normalize_uuid_series(series):
    normalized = series.astype("string").str.strip().str.lower()
    return normalized.mask(
        normalized.isna() | normalized.isin(IDENTITY_INVALID_TOKENS),
        pd.NA,
    )


def normalize_uuid_scalar(value):
    if value is None or pd.isna(value):
        return pd.NA
    normalized = str(value).strip().lower()
    if normalized in IDENTITY_INVALID_TOKENS:
        return pd.NA
    return normalized


def normalize_vcenter_series(series):
    normalized = (
        series.astype("string")
        .fillna("")
        .str.strip()
        .str.upper()
    )
    extracted = normalized.str.extract(r"(VC\d+)", expand=False)
    return extracted.mask(
        extracted.isna()
        | extracted.str.lower().isin(IDENTITY_INVALID_TOKENS),
        pd.NA,
    )


def normalize_vcenter_scalar(value):
    if value is None or pd.isna(value):
        return pd.NA
    normalized = str(value).strip().upper()
    extracted = pd.Series([normalized]).str.extract(
        r"(VC\d+)", expand=False
    ).iloc[0]
    if pd.isna(extracted):
        return pd.NA
    return str(extracted).strip().upper()


def normalize_text_series(series):
    return series.astype("string").fillna("").str.strip().str.lower()


def normalize_name_scalar(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().lower()


def is_powered_off_series(dataframe, state_column="State"):
    if state_column not in dataframe.columns:
        return pd.Series(False, index=dataframe.index)

    pattern = "|".join(INACTIVE_STATE_KEYWORDS)
    return (
        dataframe[state_column]
        .astype("string")
        .str.lower()
        .str.contains(pattern, na=False)
    )


def invalid_identity_mask(series):
    normalized = series.astype("string").str.strip()
    return (
        normalized.isna()
        | normalized.str.lower().isin(IDENTITY_INVALID_TOKENS)
    )


def build_identity_key(
    dataframe,
    name_column="Name",
    vcenter_column="vCenter",
    uuid_column="UUID",
    state_column="State",
    require_powered_off_for_fallback=True,
):
    """
    Identity Key = vCenter + UUID untuk baris dengan UUID valid.

    Fallback vCenter + Name:
    - Jika require_powered_off_for_fallback=True (default, dipakai
      main.py/disposal_rules.py): HANYA untuk baris berstatus Powered Off.
    - Jika False (dipakai status_tracking.py untuk PIC mapping): aktif
      untuk SEMUA baris tanpa UUID, selama vCenter valid. Ini diperlukan
      karena file PIC tidak memiliki kolom State.
    """
    result = dataframe.copy()
    result[vcenter_column] = normalize_vcenter_series(result[vcenter_column])
    result[uuid_column] = normalize_uuid_series(result[uuid_column])
    result["_Name_Clean"] = normalize_text_series(result[name_column])

    result["Identity Key"] = pd.NA
    valid_uuid_mask = (
        result[vcenter_column].notna()
        & result[uuid_column].notna()
    )

    result.loc[valid_uuid_mask, "Identity Key"] = (
        result.loc[valid_uuid_mask, vcenter_column].astype(str)
        + IDENTITY_KEY_SEPARATOR
        + result.loc[valid_uuid_mask, uuid_column].astype(str)
    )

    if require_powered_off_for_fallback:
        fallback_eligible_mask = is_powered_off_series(result, state_column)
    else:
        fallback_eligible_mask = pd.Series(True, index=result.index)

    fallback_name_mask = (
        result["Identity Key"].isna()
        & fallback_eligible_mask
        & result["_Name_Clean"].ne("")
        & result[vcenter_column].notna()
    )

    result.loc[fallback_name_mask, "Identity Key"] = (
        result.loc[fallback_name_mask, vcenter_column].astype(str)
        + IDENTITY_KEY_SEPARATOR
        + "NAME"
        + IDENTITY_KEY_SEPARATOR
        + result.loc[fallback_name_mask, "_Name_Clean"].astype(str)
    )

    return result.drop(columns=["_Name_Clean"], errors="ignore")


def build_legacy_identity_key(uuid_value, name_value):
    """
    Rekonstruksi Identity Key untuk data lama (sebelum ada kolom vCenter)
    saat migrasi database status_tracking.py. Diberi namespace terpisah
    ("LEGACY::UUID::" / "LEGACY::NAME::") agar TIDAK BISA collide dengan
    Identity Key modern (yang selalu berformat "VC0x::...") -- mencegah
    data lama tanpa vCenter salah menyatu dengan data baru yang punya
    vCenter.
    """
    clean_uuid = normalize_uuid_scalar(uuid_value)
    if pd.notna(clean_uuid) and clean_uuid:
        return f"{LEGACY_UUID_PREFIX}{clean_uuid}"

    clean_name = normalize_name_scalar(name_value)
    if clean_name:
        return f"{LEGACY_NAME_PREFIX}{clean_name}"

    return None
