# Panduan Mode Demo Stockfolio

Mode demo menyiapkan **akun contoh dengan data simulasi** (±18 bulan riwayat) agar aplikasi langsung terlihat hidup
untuk presentasi, portofolio, atau tangkapan layar. Semua angka berasal dari generator deterministik, bukan dari pasar nyata.

# Jalankan mode demo (terpisah)
docker compose -f docker-compose.demo.yml up -d --build
docker compose -f docker-compose.demo.yml exec api alembic upgrade head
docker compose -f docker-compose.demo.yml exec api python -m app.cli seed-demo --reset
## Prinsip

- **Selalu sebut sebagai demo/simulasi.** Aplikasi menampilkan pita "MODE DEMO" di bagian atas untuk akun demo. Jangan
  menyajikan angka ini sebagai hasil investasi sungguhan atau kinerja yang bisa dijanjikan kepada siapa pun.
- Harga saham dan indeks pada demo adalah **hasil simulasi**: nama emiten nyata hanya dipakai agar tampilan realistis.
- Stack demo **terpisah** dari data nyata Anda (database, volume, dan port sendiri). Perintah seed menolak berjalan jika
  `DEMO_MODE` tidak aktif, supaya harga simulasi tidak pernah mencemari data asli.

## Menjalankan

```bash
copy .env.demo.example .env.demo       # Windows (CMD): copy .env.demo.example .env.demo
# edit .env.demo: ganti password (di dua tempat) dan SECRET_KEY (min. 32 karakter)

docker compose -f docker-compose.demo.yml up -d --build

# Migrasi memakai file revisi yang sama dengan stack utama (folder alembic/versions).
# Jika belum ada revisi untuk perubahan terbaru (tag, is_demo), buat dulu di stack utama:
#  
docker compose exec api alembic revision --autogenerate -m "tags demo"

docker compose -f docker-compose.demo.yml exec api alembic upgrade head
docker compose -f docker-compose.demo.yml exec api python -m app.cli seed-demo --reset
```
docker compose -f docker-compose.demo.yml ps
docker compose -f docker-compose.demo.yml restart frontend


Perintah terakhir mencetak email dan password akun demo. Buka **http://localhost:5273** dan masuk.
Gunakan `--password` untuk menetapkan password sendiri, atau `--seed 7` untuk variasi data lain. Jalankan ulang dengan
`--reset` kapan pun untuk mengembalikan data demo ke keadaan awal (hanya akun yang bertanda demo yang akan dihapus).

Menghentikan: `docker compose -f docker-compose.demo.yml down` (tambahkan `-v` untuk menghapus data demo).

## Isi data demo

- 1 akun (Demo Investor): modal awal Rp50 juta + setoran bulanan Rp5 juta, 1 penarikan.
- ±27 transaksi pada 11 saham IDX (beli bertahap, 5 penjualan: ambil untung dan cut loss), lengkap dengan **alasan dan tag**.
- ±25 pencatatan dividen sehingga halaman Dividen, yield, dan kalender terisi.
- Harga harian simulasi untuk seluruh saham, 3 saham pantauan, dan indeks pembanding (IHSG simulasi), jadi halaman
  Analisis (perbandingan dengan indeks, volatilitas, drawdown, beta) dan candlestick langsung berfungsi tanpa internet.
- Pantauan, alert harga (aktif dan terpicu), target/stop loss (satu sudah tercapai), dan notifikasi contoh.

## Urutan tangkapan layar yang disarankan

1. **Dashboard** (mode terang): kartu net worth, insight, donut alokasi, dan grafik pertumbuhan 1 tahun.
2. **Dashboard** (mode gelap): tombol bulan/matahari di bar atas.
3. **Analisis**: pilih IHSG, periode 1 tahun: perbandingan dengan indeks, risiko, dan skor diversifikasi.
4. **Saham**: pilih BBCA.JK, rentang 6 bulan: candlestick dan volume.
5. **Dividen**: grafik 24 bulan dan kalender perkiraan.
6. **Target**: progres ke target, risk/reward, dan status.
7. **Jurnal**: ringkasan per tag dan alasan beli.
8. **Riwayat**: tabel buku besar dengan tag, dan form ubah.
9. **Impor / Ekspor**: pratinjau impor yang valid.

Tips: gunakan jendela browser 1440 px, zoom 100%, dan sembunyikan bookmark bar. Untuk tampilan ponsel, pakai mode
perangkat di DevTools (lebar ±390 px).

## Alur presentasi singkat (3 menit)

1. Masalah: investor ritel mencatat di Excel dan sulit melihat gambaran utuh.
2. Dashboard: satu angka net worth, untung/rugi, dan XIRR.
3. Analisis: "apakah saya mengalahkan IHSG?" dengan modal yang sama, plus risiko.
4. Disiplin: target/stop loss, alert, dan jurnal alasan beli.
5. Data aman: validasi buku besar (kas tidak pernah negatif), impor CSV, ekspor Excel.
6. Teknologi: FastAPI, PostgreSQL, Redis, React + TypeScript, Docker.
