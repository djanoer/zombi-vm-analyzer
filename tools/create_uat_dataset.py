# ==============================================================================
#  ZOMBIE VM ANALYZER — UAT DATASET GENERATOR
# ------------------------------------------------------------------------------
#  File      : create_uat_dataset.py
#  Tujuan    : Membuat dataset UAT dari CSV existing untuk menguji:
#              1. UAT-07 — pengacakan urutan baris.
#              2. UAT-09 — penghapusan VM dari snapshot.
#              3. UAT-07+09 — pengacakan sekaligus penghapusan VM.
#  Prinsip   :
#              - Tidak mengubah file sumber.
#              - Tidak mengubah nilai Name/UUID kecuali barisnya dihapus.
#              - Memvalidasi struktur sebelum dan sesudah transformasi.
#              - Tidak melakukan edit CSV berbasis teks.
#  Cara pakai:
#      python create_uat_dataset.py "source.csv" --mode shuffle
#      python create_uat_dataset.py "source.csv" --mode remove --names "VM-A" "VM-B"
#      python create_uat_dataset.py "source.csv" --mode shuffle-remove --names "VM-A"
#      python create_uat_dataset.py "source.csv" --mode remove --count 10
# ------------------------------------------------------------------------------
#  Output default:
#      shuffle       -> <source>__UAT07_SHUFFLE.csv
#      remove        -> <source>__UAT09_REMOVE.csv
#      shuffle-remove-> <source>__UAT07_UAT09_SHUFFLE_REMOVE.csv
# ==============================================================================
import argparse
from pathlib import Path

import pandas as pd


SUPPORTED_ENCODINGS = ["utf-8-sig", "utf-8", "latin1"]
SUPPORTED_SEPARATORS = [",", ";", "\t"]
REQUIRED_COLUMNS = ["Name", "State", "UUID"]
KEY_COLUMNS = ["Name", "UUID"]


def normalize_column_name(column):
    column = str(column).replace("\ufeff", "").replace("\xa0", " ")
    return " ".join(column.strip().split())


def read_csv_robust(file_path):
    candidates = []

    for encoding in SUPPORTED_ENCODINGS:
        for separator in SUPPORTED_SEPARATORS:
            try:
                dataframe = pd.read_csv(
                    file_path,
                    sep=separator,
                    engine="python",
                    skipinitialspace=True,
                    encoding=encoding,
                )
            except (
                UnicodeDecodeError,
                pd.errors.EmptyDataError,
                pd.errors.ParserError,
            ):
                continue

            if dataframe.shape[1] <= 1:
                continue

            dataframe.columns = [
                normalize_column_name(column)
                for column in dataframe.columns
            ]

            score = sum(
                column in dataframe.columns
                for column in REQUIRED_COLUMNS
            )
            candidates.append((score, len(dataframe.columns), dataframe))

    if not candidates:
        raise ValueError(
            "File sumber tidak berhasil dibaca sebagai CSV multi-kolom. "
            "Pastikan file belum berubah menjadi satu kolom setelah diedit Excel."
        )

    _, _, dataframe = max(candidates, key=lambda item: (item[0], item[1]))
    return dataframe


def validate_input(dataframe):
    if dataframe.shape[1] <= 1:
        raise ValueError("CSV hanya memiliki satu kolom.")

    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError(f"Kolom kunci tidak ditemukan: {missing_columns}")

    for column in KEY_COLUMNS:
        dataframe[column] = dataframe[column].fillna("").astype(str).str.strip()

    empty_name = dataframe["Name"].eq("").sum()
    if empty_name:
        raise ValueError(f"Ditemukan {empty_name} baris dengan Name kosong.")

    duplicate_keys = dataframe.duplicated(subset=KEY_COLUMNS).sum()
    if duplicate_keys:
        raise ValueError(
            f"Ditemukan {duplicate_keys} pasangan Name+UUID duplikat. "
            "Perbaiki dataset sumber sebelum UAT."
        )


def validate_output(source_dataframe, output_dataframe):
    if source_dataframe.shape[1] != output_dataframe.shape[1]:
        raise ValueError("Jumlah kolom berubah setelah transformasi.")

    if list(source_dataframe.columns) != list(output_dataframe.columns):
        raise ValueError("Nama atau urutan kolom berubah setelah transformasi.")

    output_keys = set(
        zip(output_dataframe["Name"], output_dataframe["UUID"])
    )
    if not output_keys.issubset(
        set(zip(source_dataframe["Name"], source_dataframe["UUID"]))
    ):
        raise ValueError("Output mengandung pasangan Name+UUID yang tidak ada di sumber.")

    duplicate_keys = output_dataframe.duplicated(subset=KEY_COLUMNS).sum()
    if duplicate_keys:
        raise ValueError("Output memiliki pasangan Name+UUID duplikat.")


def remove_rows(dataframe, names=None, count=None):
    if names:
        names = {str(name).strip() for name in names}
        result = dataframe[~dataframe["Name"].isin(names)].copy()
        removed = dataframe[dataframe["Name"].isin(names)].copy()

        missing_names = names.difference(set(removed["Name"]))
        if missing_names:
            raise ValueError(
                f"Name berikut tidak ditemukan sehingga tidak dihapus: {sorted(missing_names)}"
            )
        return result, removed

    if count is None or count <= 0:
        raise ValueError("Gunakan --names atau --count dengan nilai lebih dari 0.")

    if count >= len(dataframe):
        raise ValueError("Jumlah baris yang dihapus tidak boleh >= total baris.")

    removed = dataframe.head(count).copy()
    result = dataframe.iloc[count:].copy()
    return result, removed


def build_output_path(source_path, mode):
    suffix = {
        "shuffle": "__UAT07_SHUFFLE",
        "remove": "__UAT09_REMOVE",
        "shuffle-remove": "__UAT07_UAT09_SHUFFLE_REMOVE",
    }[mode]
    return source_path.with_name(f"{source_path.stem}{suffix}.csv")


def write_manifest(source_path, output_path, mode, source_df, output_df, removed_df):
    manifest_path = output_path.with_suffix(".manifest.txt")
    lines = [
        "ZOMBIE VM ANALYZER — UAT DATASET MANIFEST",
        f"Source file : {source_path}",
        f"Output file : {output_path}",
        f"Mode        : {mode}",
        f"Source rows : {len(source_df)}",
        f"Output rows : {len(output_df)}",
        f"Removed rows: {len(removed_df)}",
        f"Columns     : {len(output_df.columns)}",
        "",
        "Removed Name/UUID:",
    ]

    if removed_df.empty:
        lines.append("  Tidak ada baris yang dihapus.")
    else:
        for _, row in removed_df.iterrows():
            lines.append(f"  {row['Name']} || {row['UUID']}")

    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    return manifest_path


def main():
    parser = argparse.ArgumentParser(
        description="Membuat file UAT shuffle/remove dari CSV existing."
    )
    parser.add_argument("source", help="Path CSV sumber")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["shuffle", "remove", "shuffle-remove"],
        help="Mode transformasi UAT",
    )
    parser.add_argument(
        "--names",
        nargs="*",
        help="Daftar Name VM yang akan dihapus",
    )
    parser.add_argument(
        "--count",
        type=int,
        help="Jumlah baris awal yang dihapus jika --names tidak digunakan",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260914,
        help="Seed pengacakan agar hasil dapat direproduksi",
    )
    parser.add_argument(
        "--output",
        help="Path output opsional; jika kosong, nama output dibuat otomatis",
    )
    args = parser.parse_args()

    source_path = Path(args.source).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"File sumber tidak ditemukan: {source_path}")

    source_df = read_csv_robust(source_path)
    validate_input(source_df)
    original_df = source_df.copy()
    removed_df = source_df.iloc[0:0].copy()

    if args.mode in ["remove", "shuffle-remove"]:
        source_df, removed_df = remove_rows(
            source_df,
            names=args.names,
            count=args.count,
        )

    if args.mode in ["shuffle", "shuffle-remove"]:
        source_df = source_df.sample(
            frac=1,
            random_state=args.seed,
        ).reset_index(drop=True)

    output_df = source_df.reset_index(drop=True)
    validate_output(original_df, output_df)

    output_path = (
        Path(args.output).resolve()
        if args.output
        else build_output_path(source_path, args.mode)
    )

    output_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    manifest_path = write_manifest(
        source_path,
        output_path,
        args.mode,
        original_df,
        output_df,
        removed_df,
    )

    print("UAT dataset berhasil dibuat.")
    print(f"Mode         : {args.mode}")
    print(f"Source       : {source_path}")
    print(f"Output       : {output_path}")
    print(f"Manifest     : {manifest_path}")
    print(f"Baris sumber : {len(original_df)}")
    print(f"Baris output : {len(output_df)}")
    print(f"Baris dihapus: {len(removed_df)}")
    print(f"Jumlah kolom : {len(output_df.columns)}")
    print("Validasi Name+UUID: PASS")


if __name__ == "__main__":
    main()
