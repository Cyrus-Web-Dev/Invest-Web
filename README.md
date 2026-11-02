# Stockfolio — Stock Portfolio Tracker & Analytics

Aplikasi web untuk mencatat transaksi saham (mock/simulasi), memantau portofolio, dan menganalisis kinerjanya:
floating & realized P/L, ROI, XIRR, dividend yield, alokasi aset/sektor, pertumbuhan net worth, dan grafik candlestick.

> **Catatan:** proyek ini untuk pembelajaran/pencatatan pribadi, bukan saran investasi. Data harga diambil dari
> Yahoo Finance melalui `yfinance` (pustaka tidak resmi) dan bisa tertunda, terbatas, atau berhenti sewaktu-waktu.

---

## Fitur

- Registrasi & login (JWT, password di-hash Argon2), pembatasan percobaan login
- Master data saham (tambah saham khusus admin), sinkronisasi harga harian dari Yahoo Finance
- Setor/tarik modal, transaksi beli/jual (harga rata-rata bergerak), pencatatan dividen
- Kas tidak bisa negatif, jual tidak bisa melebihi kepemilikan, aman dari *race condition* (`SELECT ... FOR UPDATE`)
- Dashboard: Net Worth, ROI, XIRR, floating/realized P/L, dividend yield & yield on cost
- Grafik: donut alokasi (per saham/sektor), line chart Net Worth vs Modal disetor, candlestick + volume
- Penjadwal otomatis: sinkron harga saham IDX (Sen–Jum 17.00 WIB) dan bursa lain (Sel–Sab 06.00 WIB)
- Cache harga di Redis (TTL 5 menit) dengan cadangan ke harga penutupan terakhir di database
- Katalog awal 30 saham IDX + 10 saham/ETF AS terisi otomatis saat halaman Saham pertama kali dibuka
- Daftar pantauan (watchlist) dan alert harga (naik ≥ / turun ≤ target), diperiksa otomatis tiap 15 menit;
  notifikasi muncul di ikon lonceng (in-app)
- Tag dan jurnal transaksi: alasan beli, tag (value, dividend, dll.), halaman Jurnal dengan return sejak beli per keputusan
  dan ringkasan per tag
- Mode demo: akun contoh dengan data simulasi 18 bulan (stack terpisah, lihat `DEMO.md`)
- Halaman Dividen: total, 12 bulan, tahun berjalan, estimasi pendapatan pasif per bulan, grafik 24 bulan, yield on cost
  per saham, dan kalender dividen perkiraan dari riwayat Anda
- Halaman Target: target jual dan stop loss per saham dengan progres, risk/reward, dan notifikasi sekali saat tersentuh
- Riwayat buku besar: ubah dan hapus transaksi, setoran/penarikan, dan dividen; tambah catatan bertanggal mundur.
  Setiap perubahan memutar ulang seluruh riwayat secara kronologis dan ditolak bila saldo kas atau jumlah saham
  akan menjadi negatif di tanggal mana pun
- Impor transaksi dari CSV (tanggal lampau, divalidasi kronologis, ditolak seluruhnya bila ada satu baris bermasalah,
  file duplikat ditolak) dan ekspor ke CSV serta Excel (.xlsx)
- Halaman Analisis: perbandingan portofolio vs indeks (IHSG, S&P 500) dengan modal yang sama, return time-weighted,
  volatilitas, max drawdown, beta, dan skor diversifikasi dengan peringatan konsentrasi
- Animasi halus (framer-motion): transisi antar-halaman, indikator menu yang meluncur, angka net worth yang menghitung naik,
  panel notifikasi beranimasi; latar 3D Three.js hanya di halaman login (dimuat malas, otomatis nonaktif jika perangkat
  tidak mendukung WebGL atau pengguna memilih "kurangi animasi")
- Polesan visual: grafik beranimasi saat data masuk atau periode berganti, kontrol periode dengan pil yang meluncur,
  bar progres beranimasi, kerangka pemuatan (skeleton) bergaya grafik, dan layar pembuka
- Atribusi kinerja: kontribusi tiap saham (terealisasi + belum terealisasi + dividen) terhadap total untung/rugi, dan heatmap
  return bulanan time-weighted di halaman Analisis
- Laporan tahunan: ringkasan penjualan, laba/rugi terealisasi per transaksi, dividen, dan posisi akhir tahun;
  unduh PDF dan CSV penjualan (bahan pelaporan pajak, bukan nasihat pajak)
- User biasa dapat menambah saham sendiri (simbol divalidasi ke penyedia harga, maks. 10 per hari)
- Tampilan modern: tema terang/gelap, hero net worth dengan sparkline, insight portofolio (konsentrasi saham/sektor,
  performa terbaik/terlemah), panduan 3 langkah untuk akun baru, responsif untuk layar kecil

---

## Tech Stack

### Frontend
| Komponen | Teknologi | Versi |
|---|---|---|
| Bahasa | TypeScript (strict) | 5.6.3 |
| Framework UI | React | 18.3.1 |
| Build tool / dev server | Vite + `@vitejs/plugin-react` | 5.4.11 / 4.3.4 |
| Routing | React Router DOM | 6.28.0 |
| Grafik pie & line | ApexCharts + `react-apexcharts` | 3.54.1 / 1.4.1 |
| Grafik candlestick | TradingView Lightweight Charts | 4.2.1 |
| Runtime | Node.js | 20+ |

### Backend
| Komponen | Teknologi | Versi |
|---|---|---|
| Bahasa | Python | 3.12 |
| Framework API | FastAPI | 0.115.6 |
| Server ASGI | Uvicorn | 0.32.1 |
| ORM (async) | SQLAlchemy 2.0 + driver `asyncpg` | 2.0.36 / 0.30.0 |
| Migrasi database | Alembic | 1.14.0 |
| Validasi & konfigurasi | Pydantic, pydantic-settings, email-validator | 2.10.3 / 2.6.1 / 2.2.1 |
| Autentikasi | PyJWT, argon2-cffi, python-multipart | 2.10.1 / 23.1.0 / 0.0.20 |
| Analisis data | Pandas | 2.2.3 |
| Data saham | yfinance | 0.2.50 |
| Retry panggilan API luar | tenacity | 9.0.0 |
| Penjadwal | APScheduler | 3.10.4 |
| Klien Redis | redis (asyncio) | 5.2.1 |
| Zona waktu | tzdata | 2024.2 |
| Pengujian (dev) | pytest, httpx | 8.3.4 / 0.28.1 |

### Database & infrastruktur
| Komponen | Teknologi |
|---|---|
| Database utama | PostgreSQL 16 (image `postgres:16-alpine`) |
| Cache & pembatas laju | Redis 7 (image `redis:7-alpine`) |
| Kontainerisasi | Docker + Docker Compose |

### API eksternal
- **Yahoo Finance** (via `yfinance`) — harga historis OHLCV dan harga terbaru.
  Simbol saham IDX memakai akhiran `.JK` (contoh: `BBCA.JK`, `TLKM.JK`); saham AS cukup `AAPL`, `NVDA`.

---

## Struktur Proyek

```
stockfolio/
├── app/
│   ├── core/            # config, security (JWT/Argon2), redis, rate limit
│   ├── db/              # koneksi & session async
│   ├── routers/         # auth, stocks, prices, portfolio, dividends, analytics
│   ├── services/        # trading, positions, metrics, performance (Pandas), prices, provider harga
│   ├── models.py        # skema database
│   ├── schemas.py       # skema request/response
│   ├── jobs.py, scheduler.py, cli.py, deps.py, main.py
├── alembic/             # migrasi database
├── tests/               # unit test + integration test
├── frontend/            # React + Vite + TypeScript
├── docker-compose.yml, Dockerfile
├── requirements.txt, requirements-dev.txt
└── .env.example
```

---

## Cara Pemasangan (Docker — disarankan)

### 1. Prasyarat
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (atau Docker Engine + Compose v2)
- Port **8000** (API) dan **5173** (frontend) harus kosong

### 2. Siapkan file `.env`
```bash
docker compose down #untuk menghapus data table
cp .env.example .env          # Windows (CMD): copy .env.example .env
```
Lalu edit `.env`:
1. Ganti `POSTGRES_PASSWORD` dan **samakan** password yang sama di dalam `DATABASE_URL`.
2. Isi `SECRET_KEY` dengan string acak minimal 32 karakter. Cara membuatnya:
   ```bash
   docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
   Aplikasi menolak start jika `SECRET_KEY` terlalu pendek atau masih berupa nilai contoh.

### 3. Jalankan semua layanan
```bash
docker compose up -d --build
```
Pertama kali, layanan `frontend` menjalankan `npm install` terlebih dahulu. Pantau dengan:
```bash
docker compose logs -f frontend
```

### 4. Buat tabel database (migrasi)
```bash
docker compose exec api alembic revision --autogenerate -m "init"
docker compose exec api alembic upgrade head
```
Periksa sekilas file migrasi yang terbentuk di `alembic/versions/` sebelum `upgrade`.

### 5. Buat akun dan jadikan admin
1. Buka **http://localhost:5173** dan daftar akun.
2. Jadikan akun tersebut admin (admin dibutuhkan untuk menambah saham):
   ```bash
   docker compose exec api python -m app.cli make-admin email-anda@contoh.com
   ```

### 6. Mulai memakai
1. Halaman **Saham** → pilih saham dari katalog awal (terisi otomatis; bisa juga dijalankan manual dengan
   `docker compose exec api python -m app.cli seed-stocks`) → klik **Sync harga**. Admin dapat menambah saham lain.
2. Halaman **Transaksi** → setor modal → catat pembelian/penjualan/dividen.
3. Halaman **Dashboard** → lihat ringkasan dan grafik.

Alamat penting:

| Layanan | URL |
|---|---|
| Aplikasi (frontend) | http://localhost:5173 |
| API | http://localhost:8000 |
| Dokumentasi API interaktif (Swagger) | http://localhost:8000/docs |
| Cek kesehatan | http://localhost:8000/health |

---

## Pemasangan Manual (tanpa Docker untuk backend)

Butuh Python 3.12, Node.js 20+, serta PostgreSQL 16 dan Redis 7 yang berjalan di komputer.

```bash
# Backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # ubah host: db -> localhost, redis -> localhost
#   DATABASE_URL=postgresql+asyncpg://USER:PASS@localhost:5432/NAMA_DB
#   REDIS_URL=redis://localhost:6379/0
alembic revision --autogenerate -m "init"
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (terminal lain)
cd frontend
npm install
npm run dev
```
Vite meneruskan permintaan `/api` ke `http://localhost:8000` (ubah lewat variabel `VITE_API_PROXY` bila perlu).

---

## Variabel Lingkungan (`.env`)

| Variabel | Wajib | Keterangan |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | ya | Kredensial database (dipakai kontainer Postgres) |
| `DATABASE_URL` | ya | `postgresql+asyncpg://USER:PASS@db:5432/DB` (password harus sama dengan di atas) |
| `REDIS_URL` | tidak | Bawaan `redis://redis:6379/0` |
| `SECRET_KEY` | ya | Kunci penandatangan JWT, min. 32 karakter |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | tidak | Masa berlaku token, bawaan 60 |
| `ALLOW_REGISTRATION` | tidak | `false` untuk menutup pendaftaran (bawaan `true`) |
| `ENABLE_DOCS` | tidak | `false` untuk menyembunyikan `/docs` (bawaan `true`) |
| `SCHEDULER_ENABLED` | tidak | Penjadwal sync harga; jalankan hanya di 1 proses (bawaan `true`) |
| `PRICE_CACHE_TTL_SECONDS` | tidak | TTL cache harga, bawaan 300 |
| `SYNC_COOLDOWN_SECONDS` | tidak | Jeda minimal sync manual per saham, bawaan 60 |
| `HISTORY_BACKFILL_DAYS` | tidak | Rentang data awal saat sync pertama, bawaan 365 |

---

## Menjalankan Tes

```bash
# Unit test backend
docker compose exec api pytest

# Integration test (butuh database sudah dimigrasi). Menguji alur lengkap termasuk
# dua pembelian bersamaan; data uji dihapus otomatis di akhir.
docker compose exec -e RUN_INTEGRATION=1 api pytest tests/test_integration.py -v

# Pengecekan tipe frontend
cd frontend && npm run typecheck
```

---

## Ringkasan Endpoint API (prefix `/api/v1`)

| Grup | Endpoint |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Saham | `GET /stocks`, `POST /stocks` (admin), `GET /stocks/{id}` |
| Harga | `GET /stocks/{id}/prices`, `GET /stocks/{id}/quote`, `POST /stocks/{id}/sync` |
| Portofolio | `POST /portfolio/cash`, `POST/GET /portfolio/transactions`, `GET /portfolio/holdings` |
| Dividen | `POST/GET /portfolio/dividends` |
| Pantauan | `GET/POST /watchlist`, `DELETE /watchlist/{stock_id}` |
| Alert | `GET/POST /alerts`, `DELETE /alerts/{id}` |
| Notifikasi | `GET /notifications`, `POST /notifications/read-all`, `POST /notifications/{id}/read` |
| Atribusi | `GET /analytics/attribution`, `GET /analytics/monthly` |
| Analisis | `GET /analytics/benchmarks`, `/analytics/benchmark?benchmark_id=&days=`, `/analytics/risk?days=&benchmark_id=` |
| Laporan | `GET /reports/years`, `/reports/annual?year=`, `/reports/annual.pdf?year=`, `/reports/realized.csv?year=` |
| Jurnal | `GET /analytics/journal` |
| Target | `GET /targets`, `PUT /targets/{stock_id}`, `DELETE /targets/{stock_id}` |
| Dividen | `GET /analytics/dividends` |
| Riwayat | `GET /portfolio/ledger`, `PATCH/DELETE /portfolio/transactions/{id}`, `/portfolio/cash/{id}`, `/portfolio/dividends/{id}` |
| Impor/Ekspor | `POST /portfolio/import?dry_run=true|false`, `GET /portfolio/import/template.csv`, `GET /export/transactions.csv`, `/export/holdings.csv`, `/export/report.xlsx` |
| Analitik | `GET /analytics/summary`, `/analytics/allocation`, `/analytics/performance?days=365` |

Nilai uang dikirim sebagai **string** (Decimal) agar presisi terjaga.

---

## Pemecahan Masalah

| Masalah | Solusi |
|---|---|
| API gagal start: `SECRET_KEY terlalu lemah` | Isi `SECRET_KEY` dengan string acak ≥ 32 karakter (lihat langkah 2) |
| Sync harga selalu gagal / 0 baris | Pastikan simbol benar (IDX → `.JK`). Yahoo sering mengubah sistemnya: coba naikkan versi `yfinance` di `requirements.txt` lalu `docker compose up -d --build` |
| `Permission denied` saat membuat migrasi (Linux) | `docker compose exec -u root api alembic revision --autogenerate -m "init"` lalu `sudo chown -R $USER alembic/versions` |
| Muncul 429 "terlalu banyak percobaan" | Tunggu ±15 menit, atau bersihkan cache/pembatas: `docker compose exec redis redis-cli FLUSHALL` |
| Menambah saham ditolak (403) | Akun belum admin: jalankan perintah `make-admin` (langkah 5) |
| Muncul error tabel `price_alerts`/`notifications` tidak ada | Buat migrasi baru: `alembic revision --autogenerate -m "alerts"` lalu `alembic upgrade head` |
| Error kolom `tags` / `is_demo` tidak ada | Buat migrasi: `alembic revision --autogenerate -m "tags demo"` lalu `alembic upgrade head` |
| Error `Failed to resolve import "framer-motion"` / `"three"` | Pasang dependensi baru: `docker compose restart frontend` (menjalankan `npm install` ulang) atau `cd frontend && npm install` |
| Latar 3D di halaman login tidak muncul | Normal bila layar sempit, WebGL tidak tersedia, atau sistem diatur "kurangi animasi"; fitur lain tidak terpengaruh |
| Ingin data demo untuk presentasi | Ikuti `DEMO.md` (stack terpisah `docker-compose.demo.yml`, perintah `seed-demo`) |
| Error tabel `position_targets` tidak ada | Buat migrasi: `alembic revision --autogenerate -m "targets"` lalu `alembic upgrade head` |
| Error kolom `kind` pada tabel `stocks` tidak ada | Buat migrasi: `alembic revision --autogenerate -m "stock kind"` lalu `alembic upgrade head` |
| Halaman Analisis: "Belum ada data harga untuk indeks" | Klik **Sync 1/3/5 tahun** pada kartu perbandingan (indeks IHSG = `^JKSE`) |
| Error tabel `import_batches` tidak ada | Buat migrasi: `alembic revision --autogenerate -m "import batches"` lalu `alembic upgrade head` |
| Unduh PDF laporan menjawab 501 | Bangun ulang image agar `reportlab` terpasang: `docker compose up -d --build` |
| Ekspor Excel menjawab 501 | Bangun ulang image agar `openpyxl` terpasang: `docker compose up -d --build` |
| Impor ditolak karena "Simbol tidak ada di katalog" | Minta admin menambah saham tersebut di halaman Saham (simbol IDX berakhiran `.JK`) |
| Ingin menguji alert tanpa menunggu 15 menit | `docker compose exec api python -m app.cli check-alerts` |
| Database sudah dimigrasi sebelum kolom `is_admin` ada | Buat migrasi baru: `alembic revision --autogenerate -m "add is_admin"` lalu `alembic upgrade head` |
| Mengulang dari nol (**menghapus semua data**) | `docker compose down -v` lalu ulangi dari langkah 3 |
| Port 5173/8000 bentrok | Ubah pemetaan port di `docker-compose.yml` |

---

## Catatan Keamanan

Sudah diterapkan: hash Argon2, JWT dengan kedaluwarsa, pembatasan login/registrasi (Redis), tambah saham khusus admin,
validasi & batas nilai input, kunci baris database untuk transaksi, header keamanan dasar, kontainer API non-root,
database/Redis tidak dipublikasikan ke host.

Sebelum dipublikasikan ke internet, tambahkan: HTTPS lewat reverse proxy (Caddy/Nginx) dan build frontend produksi
(`npm run build`, bukan server dev Vite), `ENABLE_DOCS=false`, `ALLOW_REGISTRATION=false` setelah akun dibuat,
`uvicorn --proxy-headers`, pertimbangkan cookie httpOnly (token saat ini di `localStorage`), verifikasi email/2FA,
backup rutin PostgreSQL (`pg_dump`), serta jalankan `pip-audit` dan `npm audit` lalu perbarui versi dependensi.

## Batasan Saat Ini

- Kas satu mata uang (belum ada konversi kurs).
- Transaksi memakai waktu server (belum bisa di-backdate); tanggal dihitung dalam UTC.
- Belum ada perbandingan dengan indeks (IHSG/S&P 500), drawdown, dan volatilitas.
