#!/usr/bin/env bash
# Pasang cronjob: aplikasi otomatis jalan saat mesin boot + keep-alive tiap 5 menit.
# Idempoten: aman dijalankan ulang (entri lama diganti, tidak dobel).
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -x "${DIR}/start_analyzer.sh" ]; then
    echo "[ERROR] start_analyzer.sh tidak ditemukan di ${DIR}."
    exit 1
fi

if ! command -v crontab >/dev/null 2>&1; then
    echo "[ERROR] Perintah crontab tidak ditemukan."
    exit 1
fi

mkdir -p "${DIR}/data"

MARKER="${DIR}/start_analyzer.sh"
TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT

# Ambil crontab lama tanpa entri milik aplikasi ini, lalu tambah yang baru.
crontab -l 2>/dev/null | grep -vF "${MARKER}" > "${TMP}" || true
{
    echo "@reboot ${DIR}/start_analyzer.sh >> ${DIR}/data/cron.log 2>&1"
    echo "*/5 * * * * pgrep -f \"streamlit run app/main[.]py\" >/dev/null 2>&1 || ${DIR}/start_analyzer.sh >> ${DIR}/data/cron.log 2>&1"
} >> "${TMP}"
crontab "${TMP}"

echo "[OK] Cronjob terpasang:"
echo "      - @reboot : aplikasi jalan otomatis setiap mesin menyala"
echo "      - */5     : tiap 5 menit dicek, dijalankan lagi bila mati"
echo "[INFO] Lihat daftar : crontab -l"
echo "[INFO] Log cron    : ${DIR}/data/cron.log"
echo "[INFO] Melepas     : crontab -e, hapus dua baris di atas"
