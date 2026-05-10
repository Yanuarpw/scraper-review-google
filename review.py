"""
SCRAPING REVIEW KLIK INDOMARET
---------------------------------
Fitur:
- Scraping ribuan review
- Filter tanggal
- Filter versi aplikasi
- Klasifikasi tema otomatis
- Deduplikasi review
- Sensor nama akun pengguna
- Export multi-sheet Excel

Library:
pip install google-play-scraper pandas openpyxl
"""

from google_play_scraper import reviews
import pandas as pd
import time
from datetime import date

# =====================================
# KONFIGURASI PENELITIAN
# =====================================

# ID aplikasi Klik Indomaret
APP_ID = 'com.indomaret.klikindomaret'

# Filter versi aplikasi
# Isi None jika semua versi ingin diambil
TARGET_VERSION = None

# Ambil review mulai tanggal tertentu
START_DATE = date(2026, 1, 1)

# Jumlah batch scraping
TOTAL_BATCH = 20

# Jumlah review per batch
REVIEW_PER_BATCH = 200

# =====================================
# KATA KUNCI KLASIFIKASI TEMA
# =====================================

KEYWORDS = {
    'Keterlambatan': [
        'telat',
        'terlambat',
        'lama',
        'belum sampai',
        'pengiriman'
    ],
    'Kurir': [
        'kurir',
        'driver'
    ],
    'Refund': [
        'refund',
        'pengembalian',
        'dana kembali'
    ],
    'Aplikasi Error': [
        'error',
        'crash',
        'force close',
        'bug',
        'login gagal'
    ]
}

# =====================================
# PROSES SCRAPING
# =====================================

all_reviews = []
token = None
user_counter = 1  # Counter terpisah agar ID anonim selalu unik

for i in range(TOTAL_BATCH):

    print(f'Mengambil batch {i+1}/{TOTAL_BATCH}...')

    try:
        result, token = reviews(
            APP_ID,
            lang='id',
            country='id',
            count=REVIEW_PER_BATCH,
            continuation_token=token
        )
    except Exception as e:
        print(f'  [ERROR] Batch {i+1} gagal: {e}')
        time.sleep(5)  # Tunggu lebih lama sebelum coba batch berikutnya
        continue

    if not result:
        print('  Tidak ada review lagi, scraping dihentikan.')
        break

    # =====================================
    # LOOP REVIEW
    # =====================================

    for r in result:

        review_text = r['content'].lower()

        # -------------------------------
        # FILTER TANGGAL
        # FIX: pakai < bukan >, agar review sebelum START_DATE yang dilewati
        # -------------------------------

        review_date = r['at'].date()

        if review_date < START_DATE:
            continue

        # -------------------------------
        # FILTER VERSI APLIKASI
        # -------------------------------

        app_version = r.get('reviewCreatedVersion')

        if TARGET_VERSION and app_version != TARGET_VERSION:
            continue

        # -------------------------------
        # KLASIFIKASI TEMA OTOMATIS
        # -------------------------------

        tema = None

        for kategori, kata_list in KEYWORDS.items():
            if any(k in review_text for k in kata_list):
                tema = kategori
                break

        # Jika tidak ada tema cocok, lewati
        if not tema:
            continue

        # -------------------------------
        # SENSOR NAMA AKUN
        # FIX: gunakan counter terpisah agar ID tidak pernah duplikat
        # -------------------------------

        anonymous_id = f'USER_{user_counter:04d}'
        user_counter += 1

        # -------------------------------
        # SIMPAN DATA
        # -------------------------------

        all_reviews.append({
            'anonymous_user': anonymous_id,
            'review': r['content'],
            'score': r['score'],
            'date': r['at'].date(),  # Simpan hanya tanggal, bukan datetime
            'app_version': app_version,
            'likes': r['thumbsUpCount'],
            'tema': tema
        })

    # Hentikan lebih awal jika token habis
    if token is None:
        print('Token habis, semua review sudah diambil.')
        break

    # Jeda agar scraping lebih aman
    time.sleep(2)

# =====================================
# VALIDASI DATA
# =====================================

if not all_reviews:
    print('\nTidak ada review yang berhasil dikumpulkan. File Excel tidak dibuat.')
    exit()

# =====================================
# MEMBUAT DATAFRAME
# =====================================

df = pd.DataFrame(all_reviews)

# =====================================
# DEDUPLIKASI REVIEW
# =====================================

before = len(df)
df = df.drop_duplicates(subset=['review'])
after = len(df)

print(f'\nDeduplikasi: {before - after} review duplikat dihapus.')

# =====================================
# STATISTIK OTOMATIS
# =====================================

stats = df['tema'].value_counts()
avg_score = df.groupby('tema')['score'].mean().round(2)

summary = pd.DataFrame({
    'jumlah': stats,
    'rata_rata_bintang': avg_score
})

# =====================================
# EXPORT KE EXCEL
# =====================================

output_file = 'hasil_penelitian_klik_indomaret.xlsx'

try:
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:

        # Sheet utama
        df.to_excel(writer, sheet_name='Review', index=False)

        # Sheet statistik (sekarang include rata-rata bintang)
        summary.to_excel(writer, sheet_name='Statistik')

    print(f'\nFile berhasil disimpan: {output_file}')

except Exception as e:
    print(f'\n[ERROR] Gagal menyimpan file Excel: {e}')

# =====================================
# OUTPUT
# =====================================

print(f'\nScraping selesai')
print(f'Total review bersih : {len(df)}')
print(f'\nDistribusi tema:')
print(summary.to_string())