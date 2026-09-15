# ==============================================================================
#  🧟 ZOMBIE VM ANALYZER v4.0 — MODULE: manual_book.py
# ------------------------------------------------------------------------------
#  UPDATE (16 Sep 2026):
#  - Gunakan st.expander() untuk collapsible section
#  - Tambah section Threshold Preset (4 varian)
#  - Tambah section Cara Menggunakan Number Input
#  - Tambah section Independensi Threshold Aktif vs Mati
#  - Tambah section Sanity Check Validation
#  - Tambah section Troubleshooting Hasil
#  - Hapus estimasi jumlah VM yang dinamis
# ==============================================================================
import streamlit as st


MANUAL_BOOK_MARKDOWN = """
### 🎯 Tentang Aplikasi Ini

**Zombie VM Analyzer** adalah Decision-Support System (DSS) untuk membantu pengelolaan siklus hidup Virtual Machine (VM).

**Goal:** Menyediakan evidence (bukti objektif) berupa skor idle dan justifikasi terstruktur agar tim operasional dapat mengajukan daftar VM yang layak untuk di-decommission atau dihapus.

---

### 📊 Sumber Data

#### 1. CSV Metrik VM (Master)
Berisi daftar seluruh VM (aktif/Powered On maupun mati) beserta metrik beban kerja persentil ke-95 (P95).

**Kolom Wajib:**
- `Name` — Nama VM
- `State` — Status (Powered On/Off)
- `CPU Percentile 95%` — CPU P95 (%)
- `IOPS Percentile 95%` — IOPS P95
- `Throughput Percentile 95%` — Throughput P95 (KBps)
- `Network I/O | Usage Rate (KBps) - 95th Percentile` — Network P95 (KBps)
- `Status Idle` — Status Idle (0/1)
- `Uptime / Days` — Uptime VM (hari)
- `Summary|vSphere Tag` — Tag kritikalitas

**Kolom Opsional:**
- `vCPU`, `Memory (GB)`, `Provisioned Space (GB)`, dll

#### 2. CSV Power Off (Opsional)
Berisi daftar VM yang mati beserta durasi Days Powered Off.

**Kolom Wajib:**
- `Name` — Nama VM
- `Power State` — Status (harus "Powered Off")
- `Power Off Days` — Durasi mati (hari)
- `UUID` — UUID VM (untuk join dengan CSV Master)

---

### 🎯 Threshold Preset — Rekomendasi Cepat

Untuk memudahkan pemilihan threshold, tersedia 4 preset yang sudah dioptimalkan berdasarkan analisis distribusi data vROps:

#### 1. Ultra Konservatif (False Positive < 5%)
- **CPU P95:** ≤ 0.5%
- **IOPS P95:** ≤ 1.5
- **Throughput P95:** ≤ 0.07 KBps
- **Network P95:** ≤ 30 KBps
- **Use Case:** Production critical, banking core system
- **False Positive Rate:** < 5%
- **Rekomendasi:** Untuk VM critical yang tidak boleh ada false positive

#### 2. Konservatif (False Positive < 10%) — ⭐ REKOMENDASI
- **CPU P95:** ≤ 0.8%
- **IOPS P95:** ≤ 2.0
- **Throughput P95:** ≤ 0.10 KBps
- **Network P95:** ≤ 50 KBps
- **Use Case:** Production banking (recommended)
- **False Positive Rate:** < 10%
- **Rekomendasi:** Balance optimal antara risk dan coverage

#### 3. Moderat (False Positive ~15%)
- **CPU P95:** ≤ 1.5%
- **IOPS P95:** ≤ 3.0
- **Throughput P95:** ≤ 0.15 KBps
- **Network P95:** ≤ 75 KBps
- **Use Case:** Development, testing, non-critical
- **False Positive Rate:** ~15%
- **Rekomendasi:** Untuk non-production atau housekeeping besar-besaran

#### 4. Agresif (False Positive ~20%)
- **CPU P95:** ≤ 2.5%
- **IOPS P95:** ≤ 5.0
- **Throughput P95:** ≤ 0.25 KBps
- **Network P95:** ≤ 100 KBps
- **Use Case:** Housekeeping besar-besaran, non-production only
- **False Positive Rate:** ~20%
- **Rekomendasi:** Hanya untuk non-production, banyak false positive

💡 **Tips:** Mulai dengan preset "Konservatif", lalu sesuaikan berdasarkan hasil validasi manual.

---

### ⚙️ Cara Menggunakan Number Input (Threshold Manual)

Jika Anda memilih "Custom (Atur Manual)", gunakan number input untuk set threshold secara presisi:

#### Cara Input Nilai:

1. **Ketik Langsung:**
   - Klik pada kolom input
   - Ketik nilai (mis. `0.8` untuk CPU, `0.10` untuk Throughput)
   - Tekan Enter

2. **Gunakan Tombol ▲▼:**
   - Klik tombol ▲ untuk naikkan nilai (step: 0.1, 0.5, 0.01, 1.0)
   - Klik tombol ▼ untuk turunkan nilai
   - Lebih presisi daripada slider!

3. **Format Desimal:**
   - CPU: 1 desimal (mis. `0.8`, `1.5`)
   - IOPS: 1 desimal (mis. `2.0`, `3.5`)
   - Throughput: 2 desimal (mis. `0.10`, `0.15`)
   - Network: 0 desimal (mis. `50`, `75`)

#### Contoh Nilai Threshold:

| Metrik | Nilai Sangat Rendah | Nilai Rendah | Nilai Moderat |
|--------|---------------------|--------------|---------------|
| CPU P95 (%) | 0.3 - 0.5 | 0.6 - 1.0 | 1.1 - 2.0 |
| IOPS P95 | 0.5 - 1.5 | 1.6 - 3.0 | 3.1 - 5.0 |
| Throughput P95 (KBps) | 0.05 - 0.10 | 0.11 - 0.20 | 0.21 - 0.50 |
| Network P95 (KBps) | 20 - 30 | 31 - 60 | 61 - 100 |

💡 **Tips:** VM production normal biasanya CPU > 5%, IOPS > 50, Throughput > 1.0 KBps.

---

### 🔌 Independensi Threshold VM Aktif vs VM Mati

Sistem ini memisahkan analisis VM menjadi dua kategori:

#### 1. VM Aktif (Powered On) — Analisis Zombie
- **Threshold:** CPU, IOPS, Throughput, Network P95
- **Kriteria:** Semua threshold harus terpenuhi (AND logic)
- **Contoh:** VM dengan CPU rendah, IOPS rendah, Throughput rendah → Kandidat Zombie

#### 2. VM Mati (Powered Off) — Analisis Disposal
- **Threshold:** Days Powered Off (> 30 hari default)
- **Kriteria:** Hanya durasi mati yang diperhitungkan
- **Contoh:** VM yang sudah mati > 30 hari → Kandidat Disposal

#### ⚠️ PENTING: Kedua threshold INDEPENDEN!

- Memilih preset "Konservatif" → Hanya mempengaruhi threshold Zombie VM (Aktif)
- Ambang Days Powered Off → **TETAP AKTIF**, tidak terpengaruh preset
- Anda bisa set Days Powered Off = 45 hari terlepas dari preset yang dipilih

**Mengapa dipisah?**
- VM Aktif idle → Butuh validasi metrik (CPU, IOPS, dll)
- VM Mati lama → Hanya butuh validasi durasi (Days Powered Off)
- Kriteria berbeda, tujuan berbeda, threshold berbeda

---

### ✅ Sanity Check — Validasi Hasil Analisis

Setelah menjalankan analisis, lakukan validasi berikut:

#### 1. Cek Persentase VM Terdeteksi

**Jika hasil terlalu banyak (> 50%):**
- Threshold terlalu longgar (terlalu tinggi)
- Turunkan threshold (mis. CPU dari 1.5 → 0.8)
- Atau pilih preset yang lebih konservatif
- Filter Tag Kritikalitas (exclude C_01_Critical)

**Jika hasil terlalu sedikit (< 2%):**
- Threshold terlalu ketat (terlalu rendah)
- VM memang produktif semua
- Naikkan threshold (mis. CPU dari 0.5 → 0.8)
- Atau pilih preset yang lebih agresif

**Range normal:** 5-30% VM terdeteksi (tergantung environment)

#### 2. Sample Manual 10-20 VM

Ambil 10-20 VM secara acak dari hasil, lalu validasi:

**Checklist Validasi:**
- [ ] CPU P95 benar-benar rendah (< threshold)?
- [ ] IOPS P95 benar-benar rendah (< threshold)?
- [ ] Throughput P95 benar-benar rendah (< threshold)?
- [ ] VM memang tidak produktif (cek aplikasi, owner, tag)?
- [ ] Bukan VM critical/production?

**Jika > 20% false positive:**
- Turunkan threshold (lebih konservatif)
- Atau tambahkan filter Tag Kritikalitas

#### 3. Cross-Check dengan Owner/Requestor

Kirim list VM ke owner/requestor untuk konfirmasi:

**Pertanyaan Kunci:**
- "Apakah VM ini masih digunakan?"
- "Apakah ada aplikasi critical di VM ini?"
- "Apakah aman untuk di-decommission?"

**Jika banyak penolakan:**
- Threshold terlalu agresif → pilih yang lebih konservatif
- Atau tambahkan filter Tag Kritikalitas (exclude C_01_Critical)

#### 4. Monitoring Trend Idle

Gunakan fitur "Trend Idle" untuk cek konsistensi:

- VM zombie sejati → Idle konsisten > 3 periode
- VM idle temporer → Idle hanya 1-2 periode (skip!)

💡 **Tips:** Jangan decommission VM hanya berdasarkan 1 snapshot! Cek trend minimal 3 periode.

---

### 🐞 Troubleshooting — Hasil Tidak Sesuai Ekspektasi

#### Problem: VM Terdeteksi Terlalu Banyak (> 50%)

**Kemungkinan Penyebab:**
- Threshold terlalu longgar (terlalu tinggi)
- Data CSV periode terlalu panjang (90+ hari)
- Mayoritas VM memang underutilized

**Solusi:**
1. Pilih preset "Ultra Konservatif" atau "Konservatif"
2. Pastikan periode P95 = 30 hari (bukan 90+)
3. Filter Tag Kritikalitas (exclude C_01_Critical)
4. Validasi manual 10-20 VM — berapa % false positive?

#### Problem: VM Terdeteksi Terlalu Sedikit (< 2%)

**Kemungkinan Penyebab:**
- Threshold terlalu ketat (terlalu rendah)
- VM memang produktif semua
- Data CSV periode terlalu pendek (< 14 hari)

**Solusi:**
1. Pilih preset "Moderat" atau "Agresif"
2. Pastikan periode P95 = 30 hari
3. Cek distribusi metrik — berapa P25, P50, P75?
4. Gunakan script `tools/analyze_distribution_detailed.py` untuk insight

#### Problem: VM Critical Terdeteksi sebagai Zombie

**Kemungkinan Penyebab:**
- Tidak ada filter Tag Kritikalitas
- Threshold terlalu agresif

**Solusi:**
1. Filter Tag Kritikalitas → Exclude "C_01_Critical", "C_02_Very High"
2. Pilih preset "Ultra Konservatif"
3. Tambahkan validasi manual wajib untuk semua VM

#### Problem: Error "All numerical arguments must be of the same type"

**Kemungkinan Penyebab:**
- Bug lama (sudah fixed di versi terbaru)

**Solusi:**
1. Update ke versi terbaru (git pull)
2. Restart Streamlit (Ctrl+C, lalu streamlit run app/main.py)
3. Clear browser cache (Ctrl+Shift+Delete)

---

### 📋 Langkah-Langkah Analisis

1. **Upload CSV Metrik VM** — Klik "Browse files" atau drag & drop CSV
2. **Set Filter dan Threshold** — Pilih status VM, preset threshold, filter Tag
3. **Jalankan Analisis** — Klik tombol "🔍 Analisa VM Zombie"
4. **Review Hasil** — Lihat list VM kandidat zombie, review Skor Idle
5. **Export Laporan** — Klik "💾 Export ke Excel"
6. **Tindak Lanjut** — Kirim nodin ke owner, monitor approval, update Status HK

---

### ℹ️ FAQ

**Q: Berapa periode P95 yang ideal?**
**A:** 30 hari (rolling window). Ini mencakup variasi beban kerja bulanan tanpa terlalu panjang.

**Q: Apakah semua VM harus dianalisis?**
**A:** Tidak. Exclude VM critical (C_01_Critical), DR, atau compliance requirement.

**Q: Bagaimana jika hasil analisis berbeda dengan ekspektasi?**
**A:** Lakukan sanity check (lihat section di atas). Adjust threshold atau filter sesuai kebutuhan.

**Q: Apakah threshold ini fixed?**
**A:** Tidak. Anda bisa set manual atau pilih preset. Threshold default adalah rekomendasi, bukan aturan baku.

**Q: Berapa lama proses analisis?**
**A:** Tergantung jumlah VM. Untuk 3000 VM, biasanya < 1 menit.

---

### 📞 Kontak & Support

Jika ada pertanyaan atau issue, hubungi tim IT Operations atau Cloud Operations.

**Versi:** v4.0
**Last Update:** 16 Sep 2026
"""


def render_manual_book():
    with st.expander(
        "📖 Manual Book — Panduan & Logika Analisis",
        expanded=False,
    ):
        st.markdown(MANUAL_BOOK_MARKDOWN)
