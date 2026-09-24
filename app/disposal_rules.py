# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: disposal_rules.py
# ------------------------------------------------------------------------------
# PATCH NOTES (21 Sep 2026):
# - SEBELUMNYA: modul ini membangun sistem identity paralel sendiri
#   ("Merge Key" = UUID tanpa dash tanpa lowercase, atau Name saja tanpa
#   vCenter). Ini menyimpang dari Identity Key (vCenter::UUID) yang
#   dipakai di main.py, menyebabkan:
#     1. Silent mismatch UUID akibat perbedaan casing/dash antara file
#        metrik dan file Power Off.
#     2. Risiko cross-vCenter collision karena fallback Name tidak
#        menyertakan vCenter.
# - SEKARANG: menggunakan app/identity_utils.py sebagai satu-satunya
#   sumber logika identity, SAMA PERSIS dengan main.py. File Power Off
#   kini diketahui memiliki kolom "Summary|Parent vCenter" yang dialiaskan
#   menjadi "vCenter" oleh data_loader.py, sehingga Identity Key penuh
#   (vCenter+UUID, fallback vCenter+Name) dapat dibentuk dari sisi Power
#   Off tanpa perlu menebak.
# - Duplicate enrichment rows dengan Identity Key sama tetapi
#   "Days Powered Off" BERBEDA sekarang di-raise sebagai error, bukan
#   di-drop diam-diam (silent data loss).
# - Baris Power Off yang tidak dapat dibentuk Identity Key (vCenter kosong,
#   atau Power On tanpa UUID -- seharusnya tidak terjadi tapi dijaga)
#   dilaporkan sebagai orphan yang diabaikan, dengan peringatan eksplisit
#   alih-alih hilang tanpa jejak.
# ==============================================================================

import pandas as pd
import streamlit as st

from identity_utils import (
    build_identity_key,
    invalid_identity_mask,
)


POWER_OFF_DAYS_COLUMN = "Days Powered Off"
POWER_STATE_COLUMN = "Power State"
DISPOSAL_LABEL = "Kandidat Disposal"


def _parse_days_scalar(value):
    """Parse satu nilai Days Powered Off.

    FIX-03: bedakan koma desimal ("25,5" -> 25.5) dari koma pemisah
    ribuan ("1,000" -> 1000). Aturan:
    - Ada "." dan ",": pemisah TERAKHIR adalah desimal ("1.234,5"->1234.5).
    - Hanya ",": koma tunggal + 1-2 digit akhir = desimal ("25,5"->25.5);
      selain itu pemisah ribuan ("1,234,567"->1234567).
    """
    text = str(value).strip()

    if "." in text and "," in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if (
            len(parts) == 2
            and parts[1].isdigit()
            and len(parts[1]) in (1, 2)
        ):
            text = f"{parts[0]}.{parts[1]}"
        else:
            text = text.replace(",", "")

    return pd.to_numeric(text, errors="coerce")


def _parse_days_powered_off(series):
    return series.apply(_parse_days_scalar)


def normalize_power_off_dataframe(dataframe):
    """
    Normalisasi kolom dasar Power Off dan validasi Days Powered Off.
    Identity Key TIDAK dibentuk di sini -- dibentuk terpisah di
    merge_disposal_and_zombie() menggunakan identity_utils, karena
    membutuhkan kolom "State" sintetis (Power Off selalu dianggap
    non-aktif untuk keperluan fallback identity).
    """
    result = dataframe.copy()

    for column in ["Name", "UUID", "vCenter"]:
        if column not in result.columns:
            result[column] = pd.NA

    if POWER_OFF_DAYS_COLUMN not in result.columns:
        raise ValueError(
            f"Kolom '{POWER_OFF_DAYS_COLUMN}' tidak ditemukan pada "
            "dataframe Power Off."
        )

    result[POWER_OFF_DAYS_COLUMN] = _parse_days_powered_off(
        result[POWER_OFF_DAYS_COLUMN]
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


def _build_power_off_identity(power_off_dataframe):
    """
    Bentuk Identity Key untuk dataframe Power Off menggunakan
    identity_utils.build_identity_key(), dengan "State" sintetis
    "Powered Off" agar fallback vCenter+Name aktif untuk baris tanpa UUID.
    """
    result = power_off_dataframe.copy()

    if "State" not in result.columns:
        result["State"] = "Powered Off"

    result = build_identity_key(
        result,
        name_column="Name",
        vcenter_column="vCenter",
        uuid_column="UUID",
        state_column="State",
    )

    return result


def merge_disposal_and_zombie(
    master_dataframe,
    power_off_dataframe,
    min_off_days,
):
    """
    Left merge Power Off enrichment ke master VM metrik, berdasarkan
    Identity Key (vCenter + UUID, fallback vCenter + Name).

    Kontrak:
    - master_dataframe HARUS sudah memiliki kolom "Identity Key" valid
      (dibentuk oleh main.py sebelum fungsi ini dipanggil).
    - Baris Power Off yang Identity Key-nya tidak valid (vCenter kosong,
      dsb.) diabaikan sebagai orphan DENGAN peringatan eksplisit.
    - Baris Power Off dengan Identity Key sama tetapi Days Powered Off
      BERBEDA memicu error (konflik data), bukan silent drop.
    """
    master = master_dataframe.copy()

    if "Identity Key" not in master.columns:
        raise ValueError(
            "master_dataframe belum memiliki kolom 'Identity Key'. "
            "Panggil build_identity_key()/validate_identity_column() "
            "terlebih dahulu di main.py sebelum merge disposal."
        )

    master_identity_invalid = invalid_identity_mask(master["Identity Key"])
    if master_identity_invalid.any():
        raise ValueError(
            "master_dataframe memiliki Identity Key tidak valid pada "
            f"{int(master_identity_invalid.sum())} baris. Perbaiki "
            "sebelum merge disposal."
        )

    power_off = apply_disposal_labels(power_off_dataframe, min_off_days)
    power_off = _build_power_off_identity(power_off)

    power_off_identity_invalid = invalid_identity_mask(
        power_off["Identity Key"]
    )

    if power_off_identity_invalid.any():
        orphan_count = int(power_off_identity_invalid.sum())
        orphan_preview = (
            power_off.loc[
                power_off_identity_invalid,
                [
                    column
                    for column in ["Name", "vCenter", "UUID"]
                    if column in power_off.columns
                ],
            ]
            .head(10)
            .to_dict("records")
        )
        st.warning(
            f"⚠️ {orphan_count} baris pada file Power Off diabaikan "
            "karena tidak dapat dibentuk Identity Key yang valid "
            "(vCenter kosong atau Name kosong tanpa UUID). "
            f"Contoh: {orphan_preview}"
        )

    power_off_valid = power_off.loc[~power_off_identity_invalid].copy()

    enrichment_columns = [
        "Identity Key",
        POWER_OFF_DAYS_COLUMN,
        POWER_STATE_COLUMN,
        "Label Disposal",
        "Justifikasi Disposal",
    ]
    enrichment_columns = [
        column for column in enrichment_columns if column in power_off_valid.columns
    ]
    power_off_valid = power_off_valid[enrichment_columns]

    # PATCH: deteksi konflik alih-alih silent drop_duplicates(keep="first").
    duplicate_mask = power_off_valid["Identity Key"].duplicated(keep=False)
    if duplicate_mask.any():
        duplicate_rows = power_off_valid.loc[duplicate_mask]
        conflicting_keys = []

        for identity_key, group in duplicate_rows.groupby("Identity Key"):
            distinct_days = group[POWER_OFF_DAYS_COLUMN].drop_duplicates()
            if len(distinct_days) > 1:
                conflicting_keys.append(identity_key)

        if conflicting_keys:
            conflict_preview = (
                duplicate_rows[
                    duplicate_rows["Identity Key"].isin(conflicting_keys)
                ]
                .sort_values("Identity Key")
                .to_dict("records")
            )
            raise ValueError(
                "Ditemukan Identity Key duplikat pada file Power Off "
                f"dengan 'Days Powered Off' yang BERBEDA: {conflicting_keys}. "
                "Tidak dapat digabungkan secara aman -- periksa data sumber. "
                f"Detail: {conflict_preview}"
            )

        # Duplikat identik (Days Powered Off sama) -- aman direduksi.
        power_off_valid = power_off_valid.drop_duplicates(
            subset=["Identity Key"],
            keep="first",
        )

    merged = master.merge(
        power_off_valid,
        on="Identity Key",
        how="left",
        suffixes=("", " Power Off"),
        validate="many_to_one",
    )

    if "Label Disposal" in merged.columns:
        merged["Label"] = merged["Label Disposal"].fillna("Tidak Ditandai")
    else:
        merged["Label"] = "Tidak Ditandai"

    merged.drop(columns=["Label Disposal"], inplace=True, errors="ignore")

    return merged
