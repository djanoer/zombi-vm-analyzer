"""
Suite regresi BARU untuk zombi-vm-analyzer.

Ditulis: 30 September 2026 (task B1-alt).
BUKAN rekonstruksi skrip UAT asli (uat_fase6.py, demo_bug.py, test_fase2.py,
test_fase3.py) -- skrip-skrip tersebut hilang (tidak pernah ter-commit ke repo
dan tidak ada di mesin pengembang). Test ini ditulis secara jujur berdasarkan
skenario pada UAT_RESULT.md (25 September 2026) dan perilaku aktual modul
app/*, dieksekusi headless pada level fungsi.

Menjalankan:
    pip install -r requirements.txt
    pip install pytest
    pytest tests/ -v
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from parsers import parse_numeric, parse_numeric_verbose
from analysis import run_zombie_analysis
from csv_validation import validate_dataframe_structure
from identity_utils import build_identity_key, build_legacy_identity_key

# Threshold longgar untuk data uji (bukan threshold produksi).
THRESH = dict(max_cpu=5.0, max_iops=10.0, max_throughput=1.0, max_network=100.0)


def _vm_row(**overrides):
    row = {
        "Name": "web-srv-01",
        "State": "Powered On",
        "vCenter": "VC01",
        "UUID": "uuid-1",
        "CPU Percentile 95%": 0.5,
        "IOPS Percentile 95%": 0.5,
        "Throughput Percentile 95%": 0.05,
        "Network I/O | Usage Rate (KBps) - 95th Percentile": 5.0,
        "Status Idle": 1,
        "Uptime / Days": 30,
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------- parsers.py
# UAT-02: parsing desimal koma.

def test_parse_desimal_koma():
    # Catatan: UAT_RESULT.md menulis '"45,5" -> 45.0' -- itu typo di dokumen.
    # Perilaku kode yang benar: koma desimal dibaca sebagai desimal.
    assert parse_numeric("45,5") == pytest.approx(45.5)
    assert parse_numeric("25,5") == pytest.approx(25.5)


def test_parse_titik_selalu_desimal():
    # Bug kritis yang pernah diperbaiki: titik tunggal SELALU desimal,
    # tidak pernah dibaca sebagai pemisah ribuan ("0.123" != 123.0).
    assert parse_numeric("0.123") == pytest.approx(0.123)
    assert parse_numeric("1.5") == pytest.approx(1.5)


def test_parse_ribuan_dan_campuran():
    assert parse_numeric("1,234") == pytest.approx(1234.0)
    assert parse_numeric("1.234,56") == pytest.approx(1234.56)
    assert parse_numeric("1,234.56") == pytest.approx(1234.56)


def test_parse_gagal_dilaporkan():
    value, ok = parse_numeric_verbose("1.2.3")
    assert ok is False
    assert value == 0.0


# ---------------------------------------------------------------- analysis.py
# UAT-01: deteksi zombie dasar.

def test_zombie_kandidat_dasar():
    df = pd.DataFrame([
        _vm_row(),
        _vm_row(Name="web-srv-02", **{"CPU Percentile 95%": 45.0}),
    ])
    result, _ = run_zombie_analysis(df, **THRESH)

    r1 = result.loc[result["Name"] == "web-srv-01"].iloc[0]
    r2 = result.loc[result["Name"] == "web-srv-02"].iloc[0]

    assert bool(r1["Is Kandidat Zombie"]) is True
    assert float(r1["Skor Idle (0-100)"]) >= 70
    # web-srv-02: CPU 45% jauh di atas threshold -> bukan kandidat.
    assert bool(r2["Is Kandidat Zombie"]) is False


def test_analysis_menolak_powered_off():
    # Safety-net: analisis zombie hanya untuk VM Power On.
    df = pd.DataFrame([_vm_row(State="Powered Off")])
    with pytest.raises(ValueError, match="Powered"):
        run_zombie_analysis(df, **THRESH)


# ---------------------------------------------------------------- csv_validation.py
# UAT-06: CSV kolom salah -> pesan menyebut kolom yang hilang.

def test_validasi_kolom_uuid_wajib():
    kolom = [
        "Name", "vCenter", "State", "Uptime / Days", "Summary|vSphere Tag",
        "CPU Percentile 95%", "IOPS Percentile 95%",
        "Throughput Percentile 95%",
        "Network I/O | Usage Rate (KBps) - 95th Percentile", "Status Idle",
        "Memory|Usage (%)",
    ]  # sengaja TANPA "UUID"
    df = pd.DataFrame([{k: "x" for k in kolom}])
    with pytest.raises(ValueError, match="UUID"):
        validate_dataframe_structure(df, "Memory|Usage (%)")


# ---------------------------------------------------------------- identity_utils.py
# UAT-07: baris UUID+Name kosong terdeteksi (tidak dapat identity key).
# UAT-04: migrasi DB legacy dengan UUID kosong tidak crash.

def test_identity_key_kosong_terdeteksi():
    df = pd.DataFrame([
        {"Name": "", "vCenter": "VC01", "UUID": "", "State": "Powered On"},
    ])
    out = build_identity_key(df)
    assert out["Identity Key"].isna().all()


def test_identity_key_valid_terbentuk():
    df = pd.DataFrame([
        {"Name": "web-srv-01", "vCenter": "VC01", "UUID": "uuid-1",
         "State": "Powered On"},
    ])
    out = build_identity_key(df)
    assert out["Identity Key"].iloc[0] == "VC01::uuid-1"


def test_migrasi_legacy_uuid_kosong_tanpa_crash():
    assert build_legacy_identity_key("", "db-srv-05") == "LEGACY::NAME::db-srv-05"
    assert build_legacy_identity_key("uuid-9", "db-srv-05") == "LEGACY::UUID::uuid-9"
    assert build_legacy_identity_key(None, None) is None


# ---------------------------------------------------------------- trend_analysis.py
# UAT-03: 3 snapshot terekam -> VM muncul di daftar konsisten min. 3 periode.

def test_trend_konsisten_min_tiga_periode(tmp_path):
    trend_analysis = pytest.importorskip("trend_analysis")
    db = str(tmp_path / "trend.db")

    df = pd.DataFrame([{
        "Name": "web-srv-01", "UUID": "uuid-1", "vCenter": "VC01",
        "Identity Key": "vc01::uuid-1", "Label": "Kandidat Zombie",
        "Skor Idle (0-100)": 94.75, "PIC Owner": "-", "Status HK": "-",
        "Is Kandidat Zombie": True, "State": "Powered On",
    }])
    for tanggal in ["2026-09-20", "2026-09-21", "2026-09-22"]:
        trend_analysis.record_period_snapshot(df, tanggal, db_path=db)

    konsisten = trend_analysis.compute_consistent_idle_vms(
        min_periods=3, db_path=db
    )
    assert len(konsisten) == 1
    assert konsisten.iloc[0]["Nama VM"] == "web-srv-01"
    assert konsisten.iloc[0]["Jumlah Observasi Kandidat Berturut-turut"] == 3
