# ==============================================================================
# ZOMBIE VM ANALYZER — MODULE: disposal_rules.py
# ============================================================================

import pandas as pd

POWER_OFF_DAYS_COLUMN = "Days Powered Off"
POWER_STATE_COLUMN = "Power State"
DISPOSAL_LABEL = "Kandidat Disposal"


def normalize_key(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalized_uuid(value):
    value = normalize_key(value)
    if value in {"-", "nan", "None"}:
        return ""
    return value.replace("-", "")


def normalize_power_off_dataframe(dataframe):
    result = dataframe.copy()
    for column in ["Name", "UUID"]:
        if column not in result.columns:
            result[column] = ""
    result["Name"] = result["Name"].map(normalize_key)
    result["UUID"] = result["UUID"].map(normalize_key)
    result[POWER_OFF_DAYS_COLUMN] = result[POWER_OFF_DAYS_COLUMN].apply(
        lambda value: pd.to_numeric(
            str(value).replace(",", "").strip(), errors="coerce"
        )
    )
    result["Power Off Data Valid"] = (
        result[POWER_OFF_DAYS_COLUMN].notna()
        & (result[POWER_OFF_DAYS_COLUMN] >= 0)
    )
    return result


def apply_disposal_labels(power_off_dataframe, min_off_days):
    result = normalize_power_off_dataframe(power_off_dataframe)
    candidate_mask = (
        result["Power Off Data Valid"]
        & (result[POWER_OFF_DAYS_COLUMN] > float(min_off_days))
    )
    result["Label Disposal"] = None
    result.loc[candidate_mask, "Label Disposal"] = DISPOSAL_LABEL
    result["Justifikasi Disposal"] = None
    result.loc[candidate_mask, "Justifikasi Disposal"] = result.loc[
        candidate_mask
    ].apply(
        lambda row: (
            f"Power State={row.get(POWER_STATE_COLUMN, 'Unknown')}, "
            f"Days Powered Off={int(row[POWER_OFF_DAYS_COLUMN])} hari "
            f"> ambang {int(min_off_days)} hari."
        ),
        axis=1,
    )
    return result


def _build_merge_key(dataframe):
    result = dataframe.copy()
    result["UUID Merge"] = result["UUID"].map(_normalized_uuid)
    result["Merge Key"] = result.apply(
        lambda row: (
            f"UUID::{row['UUID Merge']}"
            if row["UUID Merge"]
            else f"NAME::{normalize_key(row['Name'])}"
        ),
        axis=1,
    )
    return result


def merge_disposal_and_zombie(
    master_dataframe,
    power_off_dataframe,
    min_off_days,
):
    """Left merge Power Off ke master VM metrik; orphan Power Off diabaikan."""
    master = master_dataframe.copy()
    for column in ["Name", "UUID"]:
        if column not in master.columns:
            master[column] = ""
    master["Name"] = master["Name"].map(normalize_key)
    master["UUID"] = master["UUID"].map(normalize_key)
    master = _build_merge_key(master)

    power_off = apply_disposal_labels(power_off_dataframe, min_off_days)
    power_off = _build_merge_key(power_off)

    enrichment_columns = [
        "Merge Key",
        POWER_OFF_DAYS_COLUMN,
        POWER_STATE_COLUMN,
        "Label Disposal",
        "Justifikasi Disposal",
    ]
    enrichment_columns = [
        column for column in enrichment_columns if column in power_off.columns
    ]
    power_off = power_off[enrichment_columns].drop_duplicates(
        "Merge Key", keep="first"
    )

    merged = master.merge(
        power_off,
        on="Merge Key",
        how="left",
        suffixes=("", " Power Off"),
    )
    merged["Label"] = merged.get("Label Disposal")
    merged["Label"] = merged["Label"].fillna("Tidak Ditandai")
    merged["Name"] = merged["Name"].fillna("")
    merged["UUID"] = merged["UUID"].fillna("")
    merged.drop(columns=["UUID Merge", "Merge Key"], inplace=True, errors="ignore")
    return merged
