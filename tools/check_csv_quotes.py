# ==============================================================================
#  ZOMBIE VM ANALYZER v4.0 — UTILITY: check_csv_quotes.py
# ------------------------------------------------------------------------------
#  Lokasi   : app/check_csv_quotes.py (boleh di folder mana saja, standalone)
#  Peran    : Alat diagnosis mandiri — memindai file CSV baris per baris dan
#             melaporkan baris mana yang jumlah tanda kutip (") GANJIL, yaitu
#             kandidat utama penyebab parser CSV "macet" (kolom lain jadi
#             kosong total setelah baris tersebut).
#  Cara pakai (dari folder app/, dengan venv aktif):
#      python check_csv_quotes.py "nama_file_anda.csv"
# ------------------------------------------------------------------------------
#  Tidak dipanggil oleh main.py — murni tool debugging manual, boleh dihapus
#  kapan saja tanpa memengaruhi aplikasi utama.
# ==============================================================================
import sys

if len(sys.argv) < 2:
    print("Cara pakai: python check_csv_quotes.py <nama_file.csv>")
    sys.exit(1)

file_path = sys.argv[1]

encodings_to_try = ["utf-8", "latin1"]
lines = None
used_encoding = None

for enc in encodings_to_try:
    try:
        with open(file_path, "r", encoding=enc) as f:
            lines = f.readlines()
        used_encoding = enc
        break
    except UnicodeDecodeError:
        continue

if lines is None:
    print("❌ Gagal membaca file dengan encoding utf-8 maupun latin1.")
    sys.exit(1)

print(f"Membaca '{file_path}' dengan encoding '{used_encoding}'. Total baris: {len(lines)}\n")

odd_quote_lines = []
running_quote_count = 0

for i, line in enumerate(lines, start=1):
    q_in_line = line.count('"')
    running_quote_count += q_in_line
    # Baris dengan jumlah kutip ganjil ADALAH kandidat titik mulai/akhir korupsi,
    # tapi yang lebih penting: status kumulatif GENAP/GANJIL menentukan apakah
    # parser sedang "di dalam" field berkutip saat masuk ke baris berikutnya.
    if q_in_line % 2 != 0:
        odd_quote_lines.append((i, q_in_line, line.strip()[:120]))

print(f"Total baris dengan JUMLAH KUTIP GANJIL di baris itu sendiri: {len(odd_quote_lines)}")
if odd_quote_lines:
    print("(Ini kandidat baris paling mencurigakan — biasanya persis 1 kutip hilang/berlebih)\n")
    for line_no, count, preview in odd_quote_lines[:20]:
        print(f"  Baris {line_no}: {count} tanda kutip -> {preview}...")
    if len(odd_quote_lines) > 20:
        print(f"  ... dan {len(odd_quote_lines) - 20} baris lainnya.")
else:
    print("Tidak ada baris individual dengan kutip ganjil — kemungkinan korupsi berasal dari")
    print("kombinasi 2+ baris (mis. field yang sengaja membungkus newline literal).")

print(f"\nTotal kutip di seluruh file: {running_quote_count} ({'GENAP - normal' if running_quote_count % 2 == 0 else 'GANJIL - ada 1 kutip yang benar-benar hilang/berlebih di seluruh file!'})")
