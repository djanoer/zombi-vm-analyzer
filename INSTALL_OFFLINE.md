# Panduan Instalasi Offline (Linux)

Menjalankan Zombie VM Analyzer di mesin **Ubuntu x86_64 tanpa internet**:
cukup salin folder project, sekali setup, lalu jalan.

## 1. Siapkan di mesin yang ada internetnya

1. Salin folder project ini ke mesin offline (mis. via USB),
   contoh tujuan: `/opt/zombi-vm-analyzer`
2. Download `wheelhouse-py3.13-manylinux_x86_64.zip` dari halaman
   [Releases](https://github.com/djanoer/zombi-vm-analyzer/releases),
   letakkan **di dalam folder project** (sejajar dengan `setup_offline.sh`).

Struktur folder di mesin offline:

```
/opt/zombi-vm-analyzer/
├── setup_offline.sh
├── install_cron.sh
├── start_analyzer.sh
├── requirements.txt
├── wheelhouse-py3.13-manylinux_x86_64.zip   <-- dari Releases
├── app/
└── ...
```

## 2. Setup sekali-jalan (di mesin offline)

```bash
cd /opt/zombi-vm-analyzer
./setup_offline.sh
```

Script ini akan:
- mengekstrak wheelhouse (bila belum diekstrak),
- membuat virtual environment Python 3.13 (`venv/`),
- menginstall dependensi **tanpa internet** (`pip --no-index --find-links=wheelhouse`),
- memverifikasi `streamlit`, `pandas`, `openpyxl` bisa di-import.

Syarat di mesin offline: `python3.13` dan `unzip` terinstall.

## 3. Menjalankan aplikasi

```bash
./start_analyzer.sh
```

## 4. Cronjob: otomatis jalan + keep-alive

Agar aplikasi **terus running** (jalan otomatis saat mesin menyala,
dan dihidupkan lagi bila mati):

```bash
./install_cron.sh
```

Yang dipasang (cek dengan `crontab -l`):

```
@reboot /opt/zombi-vm-analyzer/start_analyzer.sh >> /opt/zombi-vm-analyzer/data/cron.log 2>&1
*/5 * * * * pgrep -f "streamlit run app/main[.]py" >/dev/null 2>&1 || /opt/zombi-vm-analyzer/start_analyzer.sh >> /opt/zombi-vm-analyzer/data/cron.log 2>&1
```

- `@reboot` → aplikasi mulai otomatis setiap mesin menyala.
- `*/5` → tiap 5 menit dicek; kalau proses Streamlit tidak ditemukan, dijalankan lagi.
- Log cron: `data/cron.log`.
- Script idempoten: aman dijalankan ulang, entri lama diganti (tidak dobel).

Melepas cronjob: `crontab -e`, hapus dua baris di atas.

## Catatan

- Wheelhouse hanya untuk CPython 3.13 di Linux x86_64 (`manylinux`).
  Untuk platform/Python lain, build ulang di mesin berinternet:
  ```bash
  pip download -r requirements.txt -d wheelhouse \
    --python-version 3.13 --only-binary=:all: \
    --platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 \
    --platform manylinux2014_x86_64 --platform manylinux1_x86_64 --platform any
  ```
  (Pakai beberapa `--platform` karena sebagian package hanya menyediakan
  wheel untuk generasi manylinux tertentu.)
- Daftar versi yang ter-pin: `requirements.txt`.
- `wheelhouse/` dan `wheelhouse-*.zip` sengaja tidak masuk Git (lihat `.gitignore`).
