# Panduan Portable Windows 11 (WPy64)

Menjalankan Zombie VM Analyzer di Windows 11 secara portable memakai
WinPython: cukup salin folder bundle, klik dua kali langsung jalan —
tanpa install Python di sistem.

## 1. Siapkan bundle (sekali saja, di PC berinternet)

1. Download **WinPython dot** versi Python 3.13 (64-bit) dari
   https://winpython.github.io/ (pilih varian "dot", mis. `WPy64-xxxxx`).
2. Buat folder bundle, contoh: `D:\zombi-portable\`
3. Ekstrak WinPython ke dalam folder bundle → menghasilkan `WPy64-xxxxx\`
   (di dalamnya ada `python-3.13.x.amd64\`).
4. Salin folder project ini ke dalam bundle sebagai `zombi-vm-analyzer\`.

Struktur akhir:

```
D:\zombi-portable\
├── WPy64-xxxxx\
│   └── python-3.13.x.amd64\
│       └── python.exe
└── zombi-vm-analyzer\          <-- folder project (dari repo ini)
    ├── Jalankan-Analyzer.bat  <-- klik dua kali untuk menjalankan
    ├── Setup-Windows.bat      <-- sekali saja (dengan internet)
    ├── app\
    ├── requirements.txt
    └── ...
```

## 2. Setup sekali-jalan (butuh internet)

Klik dua kali `Setup-Windows.bat` → menginstall dependensi
(`requirements.txt`) ke Python portable di dalam bundle.

## 3. Pakai sehari-hari

Klik dua kali `Jalankan-Analyzer.bat` → Streamlit Server langsung jalan.

Folder bundle ini portable: bisa dicopy ke PC Windows 11 lain dan
langsung diklik tanpa setup ulang.

## Catatan

- **Tanpa administrator.** Seluruh alur (setup + launcher) berjalan sebagai
  user biasa: tidak menyentuh registry, folder sistem, service, atau firewall.
  Streamlit di-bind ke `127.0.0.1` (localhost) sehingga Windows tidak
  memunculkan dialog firewall. Syaratnya: letakkan folder bundle di lokasi
  yang bisa ditulis user (mis. `D:\`, Documents, Desktop) — jangan di
  `C:\Program Files`.
- Jika suatu saat dashboard perlu diakses dari perangkat lain dalam satu
  jaringan, hapus `--server.address 127.0.0.1` dari `Jalankan-Analyzer.bat`
  (saat itu Windows akan meminta izin firewall satu kali).
- Disarankan WinPython Python 3.13 (mengikuti `.python-version` project).
- Kedua file `.bat` otomatis mendeteksi folder `WPy64-*` dan
  `python-3.*.amd64` apa pun versinya — tidak perlu edit file.
  Bila pola nama folder tidak cocok, launcher mencari `python.exe`
  secara rekursif di dalam folder `WPy64-*`.
- Jika kedua `.bat` tidak menemukan WinPython, pastikan folder project
  (`zombi-vm-analyzer`) sejajar dengan folder `WPy64-*` seperti struktur di atas.

## Troubleshooting

- **Kotak "Open File - Security Warning" setiap klik `.bat`**: file masih
  membawa Mark of the Web (tanda file berasal dari internet). Unblock sekali
  saja — klik kanan file `.bat` → Properties → centang "Unblock" → OK;
  atau via PowerShell biasa (tanpa administrator):
  `Get-ChildItem -Path 'D:\zombi-portable' -Recurse | Unblock-File`
  (sesuaikan path dengan lokasi bundle). Setelah itu klik dua kali langsung
  jalan tanpa peringatan. Ulangi sekali setiap menyalin bundle ke PC lain.
- **`[ERROR] WinPython tidak ditemukan`** padahal folder sudah sejajar:
  cek isi folder `WPy64-*` — pastikan ada `python.exe` di dalamnya.
  Diagnosis cepat dari dalam folder induk bundle:
  `dir WPy64-*\python.exe /s`
  harus menampilkan minimal satu hasil.
- **`[ERROR] Dependensi belum terinstall`** saat klik `Jalankan-Analyzer.bat`:
  jalankan `Setup-Windows.bat` terlebih dahulu (sekali saja, butuh internet).
