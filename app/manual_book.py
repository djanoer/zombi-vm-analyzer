# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: manual_book.py
# ------------------------------------------------------------------------------
# UPDATE (15 Sep 2026): Manual book ditulis ulang mengikuti hasil review kode
# menyeluruh agar isinya sesuai dengan PERILAKU SISTEM YANG SEBENARNYA saat ini
# (bukan perilaku ideal/asumsi). Ditambahkan: dokumentasi kontrol sidebar,
# dokumentasi lengkap fitur Analisis Tren Multi-Periode (sebelumnya tidak
# didokumentasikan sama sekali), dokumentasi Status HK & Ekspor, serta bagian
# "Bug Diketahui" yang mencantumkan kuirk/cacat logika yang ditemukan saat
# review agar pengguna tidak salah membaca hasil analisis. Lihat BUG_REPORT.md
# untuk detail teknis lengkap tiap temuan.
# ==============================================================================

import streamlit as st

MANUAL_BOOK_MARKDOWN = """
### 🎯 Tujuan Sistem

Zombie VM Analyzer adalah decision-support system untuk triase awal seluruh VM
pada CSV Metrik. Sistem menampilkan semua VM master, menghitung Skor Idle,
memperkaya data dengan informasi Power Off bila file tersebut tersedia, dan
mencatat riwayat multi-periode untuk membantu mendeteksi VM yang konsisten idle
dari waktu ke waktu.

Sistem ini **tidak** mengambil keputusan disposal secara otomatis. Seluruh label,
skor, dan justifikasi adalah *evidence* untuk mendukung keputusan manusia
(tim Housekeeping/Ops) — bukan pengganti keputusan itu sendiri.

### 📂 Sumber Data

#### CSV Metrik

CSV Metrik adalah sumber master. Sistem mendeteksi delimiter (`,` / `;` / tab) dan
encoding (`utf-8-sig` / `utf-8` / `latin1`) secara otomatis. Kolom yang dibutuhkan:

- Name.
- State.
- Uptime / Days.
- Summary|vSphere Tag.
- CPU Percentile 95%.
- IOPS Percentile 95%.
- Throughput Percentile 95%.
- Network I/O | Usage Rate (KBps) - 95th Percentile.
- Status Idle.
- Salah satu dari `Memory Percentile 95%` atau `Memort Percentile 95%` (alias
  historis — lihat catatan di bagian ⚠️ Batasan).
- UUID — lihat catatan penting di bawah.
- Tag dan informasi pendukung lainnya (opsional): `vCPU`, `Memory (GB)`,
  `Provisioned Space (GB)`, `Provisioned Space (TB)`.

> ⚠️ **Catatan tentang kolom UUID:** meskipun sebagian besar logika sistem (merge
> Power Off, Status HK, riwayat tren) memperlakukan UUID sebagai **opsional**
> dengan fallback ke Name, validasi awal file saat ini masih mensyaratkan kolom
> UUID *ada* di CSV (isinya boleh kosong). File metrik tanpa kolom UUID sama
> sekali akan gagal dimuat dengan pesan error yang kurang jelas. Lihat
> 🐞 Bug Diketahui, poin 4.

#### CSV Power Off

CSV Power Off adalah file enrichment opsional. File ini berisi:

- Name.
- UUID.
- Power State.
- Days Powered Off.

Alias durasi yang didukung:

```text
Days Powered Off
Power Off Days
Days Power Off
```

Semua alias dinormalisasi menjadi `Days Powered Off`.

### 🔗 Aturan Master dan Merge

1. Seluruh baris tabel berasal dari CSV Metrik.
2. File Power Off di-merge menggunakan UUID.
3. Jika UUID kosong atau `-`, sistem memakai fallback Name-only.
4. VM yang hanya ada di CSV Power Off tidak ditampilkan.
5. File Power Off hanya menambahkan Days Powered Off, Power State,
   Label Disposal, dan Justifikasi Disposal.
6. Uptime / Days tidak digantikan oleh Days Powered Off.

### 🕒 Uptime dan Days Powered Off

| Status VM | Uptime / Days | Days Powered Off |
|---|---|---|
| Powered On | Dari CSV Metrik | Kosong |
| Powered Off dan match | Dari CSV Metrik jika tersedia | Dari CSV Power Off |
| Tidak memiliki pasangan Power Off | Dari CSV Metrik | Kosong |
| Hanya ada di Power Off | Tidak ditampilkan | Tidak relevan |

> ℹ️ **Perilaku filter "Rentang Target Uptime":** slider ini di sidebar **bukan**
> filter mutlak. VM dengan `Kualitas Data = Tidak Diketahui` (Uptime kosong, `-`,
> atau gagal dibaca) akan **selalu lolos** filter ini, berapa pun Min/Max yang
> Anda atur — supaya VM dengan data tidak lengkap tidak hilang begitu saja dari
> hasil analisis. Jika Anda perlu benar-benar mengecualikan VM tanpa data uptime
> yang valid, lakukan pengecekan manual lewat Mode Debug atau kolom Status
> Justifikasi saat review.

### 🏷️ Label Disposal

VM menjadi `Kandidat Disposal` apabila:

```text
Days Powered Off > threshold
```

Default threshold adalah 30 hari dan dapat diubah pada sidebar.

VM yang tidak memenuhi aturan Disposal akan tetap tampil dengan label lain,
misalnya `Tidak Ditandai` atau label hasil analisis Zombie.

Label Disposal bukan keputusan penghapusan otomatis. Owner, dependency,
backup, compliance, retensi, change management, dan rollback tetap harus
diverifikasi secara manual.

### 🧟 Kandidat Zombie

Kandidat Zombie ditentukan dengan empat syarat AND:

```text
CPU P95 <= threshold CPU
DAN IOPS P95 <= threshold IOPS
DAN Throughput P95 <= threshold Throughput
DAN Network P95 <= threshold Network
```

Status Idle tidak menjadi syarat AND, tetapi menjadi komponen skor.

### 🧮 Skor Idle

Skor Idle memakai lima komponen:

| Komponen | Bobot |
|---|---:|
| CPU P95 | 20% |
| IOPS P95 | 25% |
| Throughput P95 | 25% |
| Network P95 | 15% |
| Status Idle 0/1 | 15% |
| Total | 100% |

Rumus setiap komponen metrik:

```text
max(0, 1 - nilai aktual / threshold) × bobot
```

Rumus Status Idle:

```text
Status Idle × 15
```

Semua VM tetap memiliki kolom `Skor Idle (0-100)`.

- VM yang lolos seluruh threshold menerima skor hasil perhitungan.
- VM yang tidak lolos threshold menerima skor 0.
- Skor bukan probabilitas dan bukan keputusan otomatis.

### 📝 Justifikasi

Kolom `Status Justifikasi` berisi kalimat ringkas yang mencantumkan State, Uptime
(atau catatan tidak diketahui — lihat catatan bug di bawah), CPU/IOPS/Throughput
P95, RAM P95 (jika kolomnya terbaca), lalu salah satu dari dua blok penutup:

- **VM Kandidat** (lolos seluruh threshold AND): menampilkan Network P95, Status
  Idle (0/1), dan Skor Idle.
- **VM Bukan Kandidat**: menampilkan daftar metrik mana saja yang melebihi
  threshold, format `{metrik} > {threshold}`.

Contoh VM Kandidat:

```text
VM berstatus Powered On dengan Uptime 500 hari, beban CPU (0.5%), IOPS (1), dan
throughput (1) sangat rendah dengan network 1 KBps, Status Idle=0; Skor
Idle=72.67/100.
```

Contoh VM Bukan Kandidat:

```text
VM berstatus Powered On dengan Uptime 500 hari, beban CPU (85%), IOPS (40), dan
throughput (120) sangat rendah. Namun tidak menjadi kandidat karena CPU P95 85%
> 3%; IOPS P95 40 > 5; throughput P95 120 > 10; network P95 50 KBps > 10 KBps.
```

> ⚠️ **Bug diketahui:** pada contoh "Bukan Kandidat" di atas, frasa "...sangat
> rendah." tetap muncul apa pun nilai metriknya — termasuk saat metriknya justru
> **tinggi** (seperti CPU 85%). Kalimat ini kontradiktif dengan penjelasan
> setelahnya. **Jangan** menyimpulkan idle/tidak-idle hanya dari kata "sangat
> rendah" di awal kalimat pada baris Bukan Kandidat — selalu baca bagian setelah
> "Namun tidak menjadi kandidat karena..." Lihat 🐞 Bug Diketahui, poin 2.

> ⚠️ **Bug diketahui:** frasa "Uptime tidak diketahui" saat ini **tidak pernah
> muncul** di kolom ini, meskipun `Kualitas Data` VM tersebut adalah "Tidak
> Diketahui". VM dengan data uptime kosong/`-` akan tetap ditampilkan sebagai
> "Uptime 0 hari". Untuk memastikan status data uptime yang sebenarnya, rujuk
> kolom `Kualitas Data` lewat Mode Debug, bukan kalimat justifikasi. Lihat
> 🐞 Bug Diketahui, poin 3.

Kolom `Justifikasi Metrik & Bobot` tidak digunakan sebagai kolom terpisah.
Informasi justifikasi disimpan pada satu kolom `Status Justifikasi`.

### 📋 Kolom Tabel

Tabel utama menampilkan:

- Nama VM.
- State.
- Uptime / Days.
- Days Powered Off.
- Skor Idle.
- Metrik CPU, IOPS, Throughput, dan Network.
- Status Idle.
- Label.
- Status Justifikasi.
- Justifikasi Disposal.
- Status HK.
- Catatan HK.

### 🖥️ Kontrol Sidebar & Pengaturan

| Kontrol | Fungsi |
|---|---|
| 🐞 Mode Debug | Menampilkan kolom/dtype/preview data mentah dan ringkasan jumlah baris di tiap tahap pipeline (aktif/sesuai filter/kandidat), berguna untuk menelusuri kenapa data berkurang drastis di suatu tahap. |
| 👤 Identitas Anda | Nama yang dicatat sebagai `updated_by` saat menyimpan Status HK. Wajib diisi sebelum tombol "💾 Simpan Perubahan Status HK" berfungsi. |
| 🗓️ Periode Analisa | Tanggal snapshot untuk fitur tren (`tanggal_proses`). Merekam ulang pada tanggal yang sama akan **menimpa (upsert)** snapshot periode itu, bukan menambah entri baru. |
| 🔌 Filter Status VM | Status mana dari kolom `State` yang dianggap "aktif" untuk dianalisis Skor Idle/Zombie. Default: seluruh state yang tidak mengandung kata `off`, `disconnect`, `suspend`, `invalid`, `orphan`. VM berstatus OFF tetap bisa dianalisis lewat CSV Power Off secara terpisah. |
| 🗓️ Rentang Target Uptime | Batas hari uptime minimum/maksimum untuk analisis (lihat catatan di bagian 🕒 Uptime — VM "Tidak Diketahui" selalu lolos). |
| 🏷️ Filter Tag Kritikalitas | Filter berdasarkan tag `Criticality-...` pada kolom `Summary|vSphere Tag`. Kosongkan untuk menyertakan semua tag. |
| ⚙️ Threshold Skor Idle P95 | Preset "Konservatif", "Agresif", atau "Custom (Atur Manual)" untuk 4 ambang CPU/IOPS/Throughput/Network. Memilih preset akan mengunci slider ke nilai preset (tidak bisa diubah manual). |
| 🏷️ Aturan Disposal Tambahan | Ambang jumlah hari `Days Powered Off` untuk menjadi `Kandidat Disposal` (default 30 hari). |
| 💾 Simpan Pengaturan Filter | Menyimpan kombinasi filter & threshold saat ini ke `data/filter_settings.json`. Pengaturan ini dipakai sebagai **nilai default** saat sesi berikutnya dibuka — bukan diterapkan otomatis secara real-time ke sesi yang sedang berjalan. |

### 📈 Analisis Tren Multi-Periode

Fitur ini melacak apakah sebuah VM tercatat sebagai kandidat idle secara
**konsisten** di beberapa periode analisis berturut-turut, sebagai sinyal
prioritas tambahan (bukan sinyal satu-satunya).

**Cara kerja:**

1. Setiap kali analisis dijalankan, sistem merekam *snapshot* berisi
   `Nama VM`, `UUID`, `Is Kandidat Disposal` (hasil analisis Zombie saat itu),
   dan `Skor Idle`, dikaitkan dengan tanggal pada kontrol "🗓️ Periode Analisa".
2. Merekam ulang pada **tanggal yang sama** akan menimpa (upsert) snapshot
   tersebut — bukan menambah entri baru untuk tanggal itu.
3. "Periode berturut-turut" dihitung mundur dari periode **terbaru** yang
   tercatat untuk VM tersebut. Begitu ditemukan satu periode di mana VM
   **tidak** menjadi kandidat, hitungan berhenti (gap = reset hitungan ke 0).
4. VM ditampilkan sebagai "konsisten idle" hanya jika jumlah periode
   berturut-turut tersebut ≥ slider "📈 Min. Periode Konsisten Idle"
   (default 3, rentang 2–12).
5. Section ini baru menampilkan hasil setelah jumlah **total periode unik**
   yang tercatat di seluruh riwayat (lintas semua VM) mencapai minimum
   tersebut.

> 🔴 **Bug kritis diketahui:** saat ini pemanggilan perekaman snapshot di
> `main.py` memakai dataframe **sebelum** analisis Zombie dijalankan, sehingga
> kolom `Is Kandidat Disposal` dan `Skor Idle` yang benar-benar tersimpan ke
> database **selalu `0` / `0.0` untuk setiap VM, di setiap periode** — apa pun
> hasil analisis yang sebenarnya tampil di layar. Akibatnya, section ini
> **akan selalu menampilkan "Tidak ada VM yang idle N+ periode berturut-turut"**,
> tanpa error apa pun, meskipun secara aktual ada VM yang konsisten idle.
> **Jangan mengandalkan section ini untuk keputusan saat ini** sampai bug ini
> diperbaiki. Lihat `BUG_REPORT.md` — temuan #1 — untuk detail dan lokasi kode.

### 💾 Status HK & Ekspor

- Kolom `Status HK` (Pending / Approved / Rejected) dan `Catatan HK` dapat
  diedit langsung pada tabel utama.
- Perubahan disimpan per VM (kunci `Nama VM` + `UUID`) ke database lokal
  `data/status_tracking.db` — **bukan** per periode seperti riwayat tren.
  Menyimpan status baru akan menimpa status sebelumnya untuk VM yang sama.
- Kolom "🗓️ Identitas Anda" wajib diisi sebelum tombol simpan berfungsi;
  nama ini dicatat sebagai `updated_by`.
- Tombol "📥 Download Excel Master VM" mengekspor **seluruh kolom** tabel
  master (termasuk kolom yang tidak tampil di preview) ke file
  `Master_VM_Analysis.xlsx`.

### ✅ Alur Penggunaan

1. Upload CSV Metrik sebagai master.
2. Upload CSV Power Off jika analisis Disposal diperlukan.
3. (Opsional) Aktifkan Mode Debug jika ingin menelusuri kolom/dtype/preview data.
4. Isi Nama Anda di sidebar bila Anda berencana menyimpan Status HK di langkah 10.
5. Atur Tanggal Analisa Ini bila ingin merekam snapshot untuk fitur tren.
6. Pilih status VM yang menjadi konteks analisis.
7. Atur rentang uptime dan filter tag jika diperlukan.
8. Atur threshold Skor Idle dan threshold Days Powered Off.
9. (Opsional) Simpan kombinasi filter saat ini sebagai default sesi berikutnya.
10. Review seluruh master VM pada tabel, termasuk Skor Idle dan Status Justifikasi.
11. Verifikasi owner, dependency, backup, compliance, dan rollback secara manual.
12. Simpan Status HK dan Catatan HK per VM.
13. Download Excel jika hasil perlu dibagikan/diarsipkan di luar aplikasi.
14. Lihat section Analisis Tren Multi-Periode untuk sinyal konsistensi lintas
    periode — **dengan catatan bug kritis di atas, sinyal ini belum dapat
    diandalkan pada versi saat ini.**

### ⚠️ Batasan

- Nilai numerik yang gagal diparse dapat di-default ke 0 sesuai konfigurasi loader.
- Uptime kosong ditampilkan sebagai angka `0` pada teks justifikasi, bukan
  sebagai "tidak diketahui" — lihat 🐞 Bug Diketahui poin 3. Kualitas data yang
  sebenarnya hanya terlihat lewat Mode Debug.
- Days Powered Off kosong tidak menghasilkan Kandidat Disposal.
- UUID kosong dan fallback Name-only dapat menyebabkan konflik nama.
- CSV Metrik tanpa kolom UUID sama sekali saat ini akan gagal dimuat dengan
  pesan error yang kurang jelas — lihat 🐞 Bug Diketahui poin 4.
- VM yang hanya ada pada CSV Power Off tidak dibuat sebagai master baru.
- Skor Idle tidak membuktikan bahwa VM aman untuk dihapus.
- Kalimat "sangat rendah" pada Status Justifikasi bisa muncul untuk VM dengan
  metrik yang sebenarnya tinggi — lihat 🐞 Bug Diketahui poin 2.
- Fitur Analisis Tren Multi-Periode saat ini tidak merekam hasil analisis yang
  sebenarnya — lihat 🐞 Bug Diketahui poin 1.
- Alias kolom Memory mencantumkan `"Memort Percentile 95%"`; belum dikonfirmasi
  apakah ini alias yang disengaja atau salah ketik.
- Keputusan disposal tetap membutuhkan validasi operasional dan persetujuan.

### 🐞 Bug Diketahui (Catatan Teknis — Review 15 Sep 2026)

Daftar ringkas hasil review kode menyeluruh. Detail lokasi kode, bukti
reproduksi, dan rekomendasi perbaikan ada di `BUG_REPORT.md`.

1. **[Kritis]** Snapshot tren merekam dataframe sebelum analisis Zombie
   dijalankan → `Is Kandidat Disposal`/`Skor Idle` yang tersimpan selalu 0.
   Fitur Analisis Tren Multi-Periode tidak berfungsi secara substansi.
2. **[Tinggi]** Kalimat justifikasi selalu menyebut metrik "sangat rendah"
   walau VM gagal jadi kandidat karena metriknya tinggi — kalimat menjadi
   kontradiktif untuk baris Bukan Kandidat.
3. **[Tinggi]** Frasa "Uptime tidak diketahui" tidak pernah muncul akibat
   urutan pipeline (nilai Uptime sudah di-default ke 0 sebelum teks
   justifikasi dibuat).
4. **[Sedang]** Validasi CSV bisa gagal dengan pesan error mentah (`KeyError`)
   yang tidak jelas jika kolom UUID tidak ada di file metrik.
5. **[Rendah]** Kalimat justifikasi bisa memiliki titik ganda/format pecah
   saat kolom Memory P95 tidak terbaca.
6. **[Rendah]** Default status HK "Belum Ditinjau" tidak pernah benar-benar
   dipakai (selalu tertimpa "Pending") — berisiko jadi bug tersembunyi jika
   urutan kode berubah di masa depan.

Belum ada perubahan kode aplikasi yang diterapkan untuk temuan-temuan di atas
pada update manual book ini — silakan koordinasikan prioritas perbaikan dengan
tim engineering.
"""


def render_manual_book():
    with st.expander(
        "📖 Manual Book — Panduan & Logika Analisis",
        expanded=False,
    ):
        st.markdown(MANUAL_BOOK_MARKDOWN)
