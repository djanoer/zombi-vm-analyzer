# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — MODULE: app_config.py
# ------------------------------------------------------------------------------
#  Lokasi : app/app_config.py
#  Peran  : Lokasi file data aplikasi dan penyimpanan konfigurasi filter.
#  Dipakai: status_tracking.py, trend_analysis.py, filter_settings.py
# ------------------------------------------------------------------------------
#  Struktur data runtime:
#      app/
#      data/
#          status_tracking.db
#          trend_history.db
#          filter_settings.json
# ==============================================================================
from pathlib import Path


APP_DIRECTORY = Path(__file__).resolve().parent
PROJECT_DIRECTORY = APP_DIRECTORY.parent
DATA_DIRECTORY = PROJECT_DIRECTORY / "data"

STATUS_DATABASE_PATH = DATA_DIRECTORY / "status_tracking.db"
TREND_DATABASE_PATH = DATA_DIRECTORY / "trend_history.db"
FILTER_SETTINGS_PATH = DATA_DIRECTORY / "filter_settings.json"


def ensure_data_directory():
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
