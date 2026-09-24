# ==============================================================================
#  🧟 ZOMBIE VM ANALYZER v4.0 — MODULE: manual_book.py
# ------------------------------------------------------------------------------
#  UPDATE (24 Sep 2026):
#  - Manual diselaraskan dengan basecode final, kontrak identity, dan
#    alur analisis aktual.
#  - Sumber data diperjelas:
#      * CSV Metrik VM berasal dari dashboard vROps "Lembar Kerja".
#      * CSV Power Off berasal dari dashboard vROps "Status Power off".
#  - Informasi tools diagnosis tidak dimasukkan ke manual user-facing.
#    Tools diagnosis tetap menjadi utilitas teknis/developer terpisah.
#  - UUID dijelaskan sebagai data internal/audit yang disembunyikan dari UI.
#  - Status, trend observasi aktual, fallback identity, dan batasan
#    Power On/Power Off diselaraskan dengan implementasi final.
#  UPDATE (25 Sep 2026):
#  - Ditambah dokumentasi alur VM pindah vCenter (tawaran + konfirmasi + audit).
#  - Ditambah dokumentasi nilai flag kolom "Kualitas Data".
#  - Ditambah troubleshooting: kolom UUID hilang, parsing desimal koma.
# ==============================================================================
import streamlit as st


MANUAL_BOOK_MARKDOWN = """
### 🎯 Tentang Aplikasi Ini

**Zombie VM Analyzer** adalah *Decision-Support System* (DSS) yang membantu proses pengelolaan siklus hidup Virtual Machine (VM) secara objektif, terukur, dan terdokumentasi.

Aplikasi menganalisis utilisasi aktual VM, seperti CPU, IOPS, throughput, network, uptime, dan status power. Hasilnya berupa kandidat, skor idle, dan justifikasi terstruktur yang dapat digunakan sebagai evidence untuk proses housekeeping (HK), review PIC, decommission, atau penghapusan VM yang sudah tidak digunakan.

**Penting:** Sistem ini hanya melakukan *screening* dan menyediakan evidence. Sistem tidak menghapus, mematikan, atau melakukan decommission VM secara otomatis. Keputusan final tetap berada pada user, PIC, dan tim eksekutor.

---

### 🔑 Identity VM: vCenter + UUID

Setiap VM diidentifikasi menggunakan **Identity Key**, bukan hanya Name atau UUID.

Hal ini penting karena:

- Nama VM dapat berubah.
- UUID yang sama dapat muncul pada vCenter berbeda.
- Name saja tidak aman digunakan sebagai identity lintas-vCenter.

Identity utama:

```text
Identity Key = vCenter + UUID
Contoh       = VC02::50299c9a-f543-aebe-a32f-597a07b83e20
```

Untuk VM Powered Off tanpa UUID:

```text
Identity Key = vCenter + Name
Contoh       = VC02::NAME::nama-vm
```

Aturan identity:

- `vCenter` wajib tersedia pada CSV Metrik VM.
- `vCenter` wajib tersedia pada CSV Power Off, baik sebagai `vCenter`, `Parent vCenter`, maupun `Summary|Parent vCenter`.
- Nilai seperti `TBN-VC01` dan `TBN-VC02` dinormalisasi menjadi `VC01` dan `VC02`.
- UUID tetap disimpan sebagai UUID murni untuk data, audit, merge, dan trend.
- UUID disembunyikan dari tabel UI utama agar tampilan lebih ringkas.
- UUID tetap tersedia pada file export Excel.
- VM Power On tanpa UUID tidak dapat dianalisis secara aman dan akan ditolak.
- VM Power Off tanpa UUID masih dapat diproses jika `vCenter` dan `Name` tersedia.

---

### 📊 Sumber Data

#### 1. CSV Metrik VM — Dashboard vROps "Lembar Kerja"

CSV Metrik VM diambil dari dashboard vROps **"Lembar Kerja"**.

File ini merupakan **master list** dan harus berisi keseluruhan VM, baik:

- VM `Powered On`.
- VM `Powered Off`.

CSV ini menjadi sumber utama untuk identitas VM, metrik utilisasi, resource, State, vCenter, UUID, dan metadata VM.

**Kolom wajib:**

- `Name` — Nama VM.
- `vCenter` — vCenter sumber VM, misalnya `TBN-VC01` atau `TBN-VC02`.
- `UUID` — UUID VM. Kolom wajib ada; nilainya wajib untuk Power On dan boleh kosong untuk Power Off.
- `State` — Status VM, misalnya `Powered On` atau `Powered Off`.
- `CPU Percentile 95%` — CPU P95 dalam persen.
- `IOPS Percentile 95%` — IOPS P95.
- `Throughput Percentile 95%` — Throughput P95 dalam KBps.
- `Network I/O | Usage Rate (KBps) - 95th Percentile` — Network P95 dalam KBps.
- `Status Idle` — Status idle, biasanya 0 atau 1.
- `Uptime / Days` — Uptime VM dalam hari.
- `Summary|vSphere Tag` — Tag kritikalitas dan metadata tag VM.
- Salah satu kolom memory yang didukung: `Memory Percentile 95%` atau format legacy `Memort Percentile 95%`.

**Kolom opsional:**

- `vCPU`.
- `Memory (GB)`.
- `Provisioned Space (GB)`.
- `Provisioned Space (TB)`.
- Host, Cluster, Datastore, Guest OS, dan metadata lainnya.

#### 2. CSV Power Off — Dashboard vROps "Status Power off"

CSV Power Off diambil dari dashboard vROps **"Status Power off"**.

File ini berisi subset VM yang Power Off dan digunakan sebagai **enrichment** untuk menambahkan informasi durasi mati (`Days Powered Off`) ke master list dari CSV Metrik VM.

CSV Power Off bukan pengganti CSV Metrik VM. VM Power On tetap berasal dari master list dan tidak boleh hilang ketika CSV Power Off digabungkan.

**Kolom wajib:**

- `Name` — Nama VM.
- `Power State` — Status Power Off.
- `Days Powered Off` — Durasi VM dalam kondisi Power Off.
- `Parent vCenter` — vCenter sumber VM.

Nama kolom vCenter yang didukung:

- `vCenter`.
- `Parent vCenter`.
- `Summary|Parent vCenter`.
- Variasi lain yang mengandung kata `vCenter` dapat dikenali otomatis jika hanya ada satu kolom yang cocok.

**Kolom opsional:**

- `UUID` — digunakan sebagai identity utama jika tersedia.
- `Parent Cluster`.
- `Parent Host`.
- `Datastore`.
- `Guest OS`.
- `Reclaimable Disk Space (GB)`.
- `Provisioned Space (GB)`.
- `Provisioned Space (TB)`.

Jika UUID Power Off kosong, sistem menggunakan fallback `vCenter + Name`.

---

### 👤 Data PIC / Owner

Data PIC/Owner dapat diunggah melalui CSV atau Excel.

Kolom identitas yang dapat digunakan:

- `Name`.
- `Nama VM`.
- `UUID`.
- `vCenter`.

Kolom pemilik yang didukung:

- `PIC`.
- `Owner`.
- `PIC Owner`.
- `Application Owner`.

Sebaiknya file PIC memiliki `vCenter` dan `UUID` agar mapping lintas-vCenter lebih aman. Jika UUID tidak tersedia, sistem menggunakan `vCenter + Name` sebagai fallback. Mapping yang tidak dapat dipastikan identity-nya akan ditolak agar PIC tidak salah dipasang ke VM lain.

Klik tombol **"Ekstrak & Simpan PIC ke Database"** untuk menyimpan mapping secara persisten.

---

### 🎯 Threshold Preset — VM Powered On

Threshold preset digunakan untuk analisis VM aktif atau `Powered On`.

#### 1. Ultra Konservatif

- CPU P95: ≤ 0.5%.
- IOPS P95: ≤ 1.5.
- Throughput P95: ≤ 0.07 KBps.
- Network P95: ≤ 30 KBps.
- Cocok untuk production critical dan sistem dengan toleransi false positive sangat rendah.

#### 2. Konservatif — Rekomendasi ⭐

- CPU P95: ≤ 0.8%.
- IOPS P95: ≤ 2.0.
- Throughput P95: ≤ 0.10 KBps.
- Network P95: ≤ 50 KBps.
- Cocok sebagai titik awal untuk lingkungan production.

#### 3. Moderat

- CPU P95: ≤ 1.5%.
- IOPS P95: ≤ 3.0.
- Throughput P95: ≤ 0.15 KBps.
- Network P95: ≤ 75 KBps.
- Cocok untuk development, testing, dan non-critical.

#### 4. Agresif

- CPU P95: ≤ 2.5%.
- IOPS P95: ≤ 5.0.
- Throughput P95: ≤ 0.25 KBps.
- Network P95: ≤ 100 KBps.
- Gunakan dengan validasi manual lebih ketat.

Semua metrik harus memenuhi threshold secara bersamaan (*AND logic*). Aplikasi tidak menambahkan syarat baru berupa `Skor Idle >= 75`.

---

### 🔌 Independensi VM Aktif dan VM Mati

#### VM Powered On — Kandidat Zombie

VM Powered On dianalisis menggunakan:

- CPU P95.
- IOPS P95.
- Throughput P95.
- Network P95.
- Status Idle untuk perhitungan skor.

VM Powered On dengan metrik di bawah seluruh threshold dapat diberi label `Kandidat Zombie`.

#### VM Powered Off — Kandidat Disposal

VM Powered Off tidak dianalisis menggunakan scoring zombie. VM dievaluasi berdasarkan:

```text
Days Powered Off > Ambang Days Powered Off
```

Jika memenuhi aturan, VM diberi label `Kandidat Disposal`.

Threshold Zombie dan threshold Disposal bersifat independen. Mengubah preset Zombie tidak mengubah ambang Days Powered Off.

---

### 📈 Analisis Tren Observasi Aktual

Trend dihitung berdasarkan observasi yang benar-benar direkam oleh aplikasi.

- Setiap eksekusi analisis pada tanggal tertentu menghasilkan satu observasi.
- Tanggal yang tidak dianalisis tidak dibuat sebagai record.
- Interval antaranalisis boleh tidak beraturan.
- Sistem tidak mengisi tanggal kosong dengan nilai buatan.
- Minimum observasi default adalah 3 observasi kandidat berturut-turut.
- Streak dihitung berdasarkan Identity Key.
- Rename VM tidak memutus histori jika Identity Key tetap sama.
- UUID dan vCenter tersedia pada export trend untuk audit.

Jalankan analisis pada tanggal observasi baru agar histori trend bertambah. Menjalankan ulang tanggal yang sama melakukan update pada snapshot tanggal tersebut, bukan menambah observasi baru.

---

### 📋 Manajemen Status HK dan PIC

Status HK dan PIC disimpan dalam database lokal berdasarkan Identity Key.

Status yang tersedia:

- `Need Confirm` — Belum ada konfirmasi final.
- `Approved` — VM dikonfirmasi tidak digunakan dan disetujui untuk proses berikutnya.
- `Rejected` — VM dikonfirmasi masih digunakan atau tidak boleh diproses.
- `No Feedback` — Belum ada respons dari PIC.

`Approved` tidak berarti aplikasi menghapus VM. Status tersebut hanya menjadi evidence dan reminder untuk proses eksekusi yang dilakukan oleh tim berwenang.

`Rejected` mencegah Kandidat Zombie ditampilkan kembali pada eksekusi analisis berikutnya selama identity dan statusnya tetap sama.

---

### 🔀 VM Pindah vCenter

Jika sebuah VM tercatat di vCenter berbeda dari sebelumnya (misalnya pindah dari VC01 ke VC02) tetapi UUID-nya sama, aplikasi menawarkannya di panel **"VM Terdeteksi Pindah vCenter"**.

- Histori Status HK, PIC, dan trend **tidak** dipindahkan otomatis.
- Penautan histori ke lokasi baru hanya terjadi setelah kamu klik **setuju** pada tawaran tersebut.
- Setiap penautan yang disetujui tercatat di tabel audit `vm_identity_moves`.
- Jika UUID yang sama muncul dua kali dalam satu upload, tawaran tidak ditampilkan karena datanya konflik dan perlu diperiksa manual.

---

### 🏷️ Kualitas Data

Kolom **"Kualitas Data"** menandai kelengkapan metrik tiap baris:

- `Lengkap` — semua metrik kritis tersedia.
- `Tidak Diketahui` — uptime tidak diketahui (dipakai oleh filter uptime).
- `Metrik Tidak Lengkap` — satu atau lebih metrik kritis (CPU, IOPS, Throughput, Network) kosong atau tidak terbaca.

Baris bertanda `Metrik Tidak Lengkap` tetap tampil sebagai kandidat dan wajib diverifikasi manual, karena metrik yang hilang diperlakukan sebagai 0.0 saat penilaian.

---

### ✅ Sanity Check

Setelah analisis selesai, periksa:

- Total VM master dibandingkan jumlah VM setelah filter State.
- Jumlah VM setelah filter Uptime dan Tag.
- Jumlah Kandidat Zombie.
- Jumlah Kandidat Disposal.
- Kegagalan parsing numerik.
- vCenter dan Identity Key pada Mode Debug jika diperlukan.

Lakukan sampling manual 10–20 VM kandidat dan cek:

- CPU P95.
- IOPS P95.
- Throughput P95.
- Network P95.
- Status aplikasi dan criticality tag.
- Konfirmasi penggunaan kepada PIC atau owner.

Jangan mengambil keputusan decommission hanya berdasarkan satu snapshot atau satu hasil screening.

---

### 🐞 Troubleshooting

#### CSV Metrik gagal karena vCenter

Pastikan CSV dari dashboard vROps **"Lembar Kerja"** memiliki kolom `vCenter`.

#### CSV Metrik ditolak karena kolom UUID hilang

Kolom `UUID` wajib ada di CSV Metrik VM. Jika kolomnya tidak ada, upload ditolak dengan pesan error yang menyebut kolom yang hilang; aplikasi tidak crash.

#### Angka desimal koma terbaca salah

Aplikasi membedakan koma desimal dari koma pemisah ribuan. Contoh: `"45,5"` dibaca `45.0` (bukan `455.0`), sedangkan `"2,809.25"` dibaca `2809.25`.

#### CSV Power Off gagal karena vCenter

Pastikan CSV dari dashboard vROps **"Status Power off"** memiliki salah satu kolom:

- `vCenter`.
- `Parent vCenter`.
- `Summary|Parent vCenter`.

#### VM Power On tanpa UUID

VM Power On wajib memiliki UUID. Periksa kembali hasil export vROps dan jangan mengganti UUID dengan Name secara manual.

#### Identity Key duplikat

Periksa apakah file master terunggah lebih dari satu kali atau terdapat dua baris VM yang sama dengan metrik berbeda.

#### Tidak ada Kandidat Zombie

Periksa threshold, kualitas metrik, filter State, filter Uptime, filter Tag, dan apakah Network P95 menyebabkan VM gagal pada AND logic.

#### Tidak ada tabel Trend

Trend hanya menampilkan tabel jika terdapat minimal jumlah observasi kandidat berturut-turut sesuai kontrol `Min. Observasi Kandidat Berturut-turut`. Tanggal yang tidak dianalisis tidak dihitung sebagai observasi negatif.

#### UUID tidak terlihat di tabel

UUID sengaja disembunyikan dari tabel utama dan tabel trend agar UI lebih ringkas. UUID tetap disimpan secara internal dan tersedia di file export Excel.

---

### 📋 Langkah-Langkah Analisis

1. Ambil CSV Metrik VM dari dashboard vROps **"Lembar Kerja"**.
2. Pastikan CSV Metrik VM berisi seluruh VM, termasuk Powered On dan Powered Off.
3. Ambil CSV Power Off dari dashboard vROps **"Status Power off"**.
4. Upload CSV Metrik VM sebagai file master.
5. Upload CSV Power Off sebagai enrichment jika analisis disposal diperlukan.
6. Upload data PIC/Owner jika diperlukan.
7. Pilih State, filter Uptime (inklusif, misalnya 30 hari mencakup tepat 30 hari), filter Tag, dan threshold pada sidebar.
8. Review Kandidat Zombie dan Kandidat Disposal.
9. Isi PIC Owner, Status HK, dan Catatan jika sudah ada hasil koordinasi.
10. Klik **Simpan Perubahan** untuk menyimpan status ke database.
11. Gunakan **Download Excel Master VM** untuk mengekspor kandidat aktif saja, yaitu Kandidat Zombie dan Kandidat Disposal.
12. Jalankan analisis pada tanggal observasi berikutnya untuk membangun trend observasi aktual.
13. Gunakan **Download Data Trend (Excel)** untuk mengekspor VM yang memenuhi streak observasi.

---

### ℹ️ FAQ

**Q: Apakah aplikasi menghapus VM otomatis?**

**A:** Tidak. Aplikasi hanya melakukan screening dan menyediakan evidence. Keputusan dan eksekusi tetap dilakukan user/PIC/tim berwenang.

**Q: Dari mana CSV Metrik VM harus diambil?**

**A:** Dari dashboard vROps **"Lembar Kerja"**.

**Q: Dari mana CSV Power Off harus diambil?**

**A:** Dari dashboard vROps **"Status Power off"**.

**Q: Apakah CSV Power Off menggantikan CSV Metrik VM?**

**A:** Tidak. CSV Power Off hanya enrichment untuk Days Powered Off. Master tetap berasal dari CSV Metrik VM.

**Q: Apakah UUID harus terlihat di tabel?**

**A:** Tidak. UUID disembunyikan dari UI, tetapi tetap ada di export Excel dan database untuk audit serta identity.

**Q: Berapa observasi yang diperlukan untuk trend?**

**A:** Default-nya 3 observasi kandidat berturut-turut. Observasi berarti eksekusi analisis yang benar-benar tercatat, bukan tanggal kalender yang diasumsikan.

**Q: Apakah threshold bersifat fixed?**

**A:** Tidak. Threshold dapat dipilih melalui preset atau diatur manual. Formula scoring dan bobot tetap mengikuti konfigurasi aplikasi.

**Q: Apa arti Approved?**

**A:** Approved berarti VM dikonfirmasi tidak digunakan dan dapat diteruskan ke proses eksekusi sesuai prosedur. Approved bukan instruksi delete otomatis.

**Q: Apa arti Rejected?**

**A:** Rejected berarti VM dikonfirmasi masih digunakan atau tidak boleh diproses. Status ini mencegah kandidat zombie yang sama muncul kembali pada eksekusi berikutnya.

---

### 📞 Kontak dan Support

Jika ada pertanyaan atau issue, hubungi tim Surrounding Compute Recovery Operation (SCR).

**Versi:** v4.0
**Last Update:** 25 Sep 2026 — alur pindah vCenter, flag Kualitas Data, troubleshooting UUID dan desimal koma, filter uptime inklusif.
"""


def render_manual_book():
    with st.expander(
        "📖 Manual Book — Panduan & Logika Analisis",
        expanded=False,
    ):
        st.markdown(MANUAL_BOOK_MARKDOWN)
