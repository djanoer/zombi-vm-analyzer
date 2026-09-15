# ==============================================================================
# ZOMBIE VM ANALYZER v4.0 — MODULE: manual_book.py
# ------------------------------------------------------------------------------
# UPDATE: Manual book telah disesuaikan dengan logika sistem terbaru.
# Seluruh cacat logika pada filter Uptime, sinkronisasi UI, dan perekaman
# riwayat tren multi-periode telah diselesaikan.
# ==============================================================================

import streamlit as st

MANUAL_BOOK_MARKDOWN = """
### 🎯 Tujuan Sistem

Zombie VM Analyzer adalah *Decision-Support System* yang dirancang untuk membantu tim IT/Infrastruktur dalam melakukan triase dan *housekeeping* Virtual Machine (VM). Sistem menganalisa beban kerja VM (*Powered On*) berdasarkan persentil ke-95 (P95) dari metrik utamanya, serta memvalidasi VM (*Powered Off*) yang sudah mati melebihi batas waktu tertentu.

Sistem ini **tidak** melakukan *action* eksekusi (seperti *delete* atau *power off*) ke vCenter secara otomatis. Semua skor dan label yang dihasilkan bertujuan sebagai *evidence* objektif bagi *engineer* untuk mengambil keputusan *housekeeping* (HK) secara aman.

---

### 🧮 Logika Filter & Threshold Metrik

Untuk menentukan apakah sebuah VM berstatus "Idle" (Zombie), sistem memfilter dan mengevaluasi data melalui beberapa tahap:

#### 1. Filter Pra-Analisa (Konteks Data)
Sebelum diberi skor, VM harus lolos saringan awal berdasarkan pengaturan di *Sidebar*:
*   **Status VM:** Hanya memproses VM dengan status *power* yang dipilih (misal: *Powered On*).
*   **Target Uptime:** Memfilter VM berdasarkan masa hidupnya. **Pengecualian:** VM yang statusnya sedang mati (*Powered Off* / *Suspended*) dan VM yang data uptimenya *Tidak Diketahui* akan otomatis dibypass (diloloskan) agar datanya tidak hilang dari tabel HK.

#### 2. Kriteria Kandidat (Syarat Mutlak)
Sebuah VM diklasifikasikan sebagai **Kandidat Zombie** HANYA JIKA memenuhi keempat syarat (AND) berikut berdasarkan batas yang diatur di *Sidebar*:
1.  **CPU P95** $\le$ Threshold CPU (%)
2.  **IOPS P95** $\le$ Threshold IOPS
3.  **Throughput P95** $\le$ Threshold Throughput (KBps)
4.  **Network P95** $\le$ Threshold Network (KBps)

*Jika salah satu saja metrik di atas melebihi ambang batas, VM tersebut batal menjadi kandidat.*

---

### ⚖️ Perhitungan Bobot & Skor Idle

Setiap VM Kandidat akan diberikan **Skor Idle (0 - 100)**. Semakin mendekati 100, semakin statis/mati suri VM tersebut.
Skor dihitung secara proporsional. Jika metrik menyentuh angka 0, ia mendapat bobot penuh. Jika metrik menyentuh batas ambang (*threshold*), ia mendapat bobot 0.

**Distribusi Bobot:**
*   **Beban CPU (20%)**
*   **Storage IOPS (25%)**
*   **Storage Throughput (25%)**
*   **Trafik Network (15%)**
*   **Status Indikator Idle Asli (15%)** — *Didapat dari flag sistem eksternal (1 = 15%, 0 = 0%)*

**Rumus Komponen:**
`Maksimal dari (0, 1 - (Nilai Metrik Aktual / Threshold Metrik)) * Bobot`

---

### 🗑️ Aturan Kandidat Disposal (Powered Off)
Jika Anda mengunggah CSV Power Off pendamping, sistem akan menggabungkannya (*enrichment*) dengan CSV Metrik Master menggunakan kecocokan `UUID` (utama) atau `Name` (cadangan).
*   VM akan diberi label **Kandidat Disposal** apabila nilai `Days Powered Off` lebih besar dari batas ambang hari yang ditetapkan di Sidebar (Default: >30 hari).

---

### 📈 Analisis Tren Multi-Periode (Riwayat)

Untuk menghindari kesalahan penandaan (*false-positive*) akibat VM yang sedang kebetulan idle saat data ditarik, sistem menyimpan riwayat analisis (*snapshot*) ke dalam *database* SQLite lokal setiap kali Anda melakukan analisa.

**Cara Kerja Tren:**
1.  Sistem mencatat status *Kandidat* dan *Skor Idle* setiap VM berdasarkan **Tanggal Analisa** yang dipilih di Sidebar.
2.  Sistem menghitung **Streak** (Periode berturut-turut). Jika VM terdeteksi sebagai kandidat selama 3 periode analisa secara beruntun tanpa terputus, VM tersebut akan muncul di panel *Analisis Tren* sebagai prioritas tinggi untuk dihapus.
3.  Jika Anda memproses ulang data di tanggal yang sama, sistem akan melakukan *Upsert* (menimpa/memperbarui data di hari itu tanpa membuat baris ganda).

---

### 📝 Pencatatan Status Housekeeping (HK)

*   Tabel hasil analisis bersifat interaktif. Anda dapat mengubah kolom **Status HK** (Pending / Approved / Rejected) dan mengisi **Catatan HK**.
*   Tekan tombol **Simpan Perubahan** untuk merekam keputusan tersebut. Pastikan kolom **Identitas Anda** di *sidebar* sudah diisi agar sistem bisa merekam riwayat audit (siapa yang menyetujui).
*   Data master yang komprehensif dapat diekspor melalui tombol **Download Excel**.
"""


def render_manual_book():
    with st.expander(
        "📖 Manual Book — Panduan & Logika Analisis",
        expanded=False,
    ):
        st.markdown(MANUAL_BOOK_MARKDOWN)
