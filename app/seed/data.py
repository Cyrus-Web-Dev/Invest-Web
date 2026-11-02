"""Katalog saham awal (data murni). Simbol mengikuti format Yahoo Finance.
Saham IDX memakai akhiran .JK. Cek kebenaran simbol dengan tombol "Sync harga"."""

_IDX = [
    ("BBCA.JK", "Bank Central Asia Tbk", "Keuangan"),
    ("BBRI.JK", "Bank Rakyat Indonesia (Persero) Tbk", "Keuangan"),
    ("BMRI.JK", "Bank Mandiri (Persero) Tbk", "Keuangan"),
    ("BBNI.JK", "Bank Negara Indonesia (Persero) Tbk", "Keuangan"),
    ("BRIS.JK", "Bank Syariah Indonesia Tbk", "Keuangan"),
    ("TLKM.JK", "Telkom Indonesia (Persero) Tbk", "Telekomunikasi"),
    ("EXCL.JK", "XL Axiata Tbk", "Telekomunikasi"),
    ("ISAT.JK", "Indosat Tbk", "Telekomunikasi"),
    ("TOWR.JK", "Sarana Menara Nusantara Tbk", "Infrastruktur"),
    ("JSMR.JK", "Jasa Marga (Persero) Tbk", "Infrastruktur"),
    ("PGAS.JK", "Perusahaan Gas Negara Tbk", "Energi"),
    ("PTBA.JK", "Bukit Asam Tbk", "Energi"),
    ("ITMG.JK", "Indo Tambangraya Megah Tbk", "Energi"),
    ("ASII.JK", "Astra International Tbk", "Industri"),
    ("UNTR.JK", "United Tractors Tbk", "Industri"),
    ("UNVR.JK", "Unilever Indonesia Tbk", "Konsumer"),
    ("ICBP.JK", "Indofood CBP Sukses Makmur Tbk", "Konsumer"),
    ("INDF.JK", "Indofood Sukses Makmur Tbk", "Konsumer"),
    ("HMSP.JK", "H.M. Sampoerna Tbk", "Konsumer"),
    ("AMRT.JK", "Sumber Alfaria Trijaya Tbk", "Konsumer"),
    ("CPIN.JK", "Charoen Pokphand Indonesia Tbk", "Konsumer"),
    ("KLBF.JK", "Kalbe Farma Tbk", "Kesehatan"),
    ("MIKA.JK", "Mitra Keluarga Karyasehat Tbk", "Kesehatan"),
    ("GOTO.JK", "GoTo Gojek Tokopedia Tbk", "Teknologi"),
    ("ANTM.JK", "Aneka Tambang Tbk", "Bahan Baku"),
    ("INCO.JK", "Vale Indonesia Tbk", "Bahan Baku"),
    ("MDKA.JK", "Merdeka Copper Gold Tbk", "Bahan Baku"),
    ("SMGR.JK", "Semen Indonesia (Persero) Tbk", "Bahan Baku"),
    ("BSDE.JK", "Bumi Serpong Damai Tbk", "Properti"),
    ("CTRA.JK", "Ciputra Development Tbk", "Properti"),
]

_US = [
    ("AAPL", "Apple Inc.", "NASDAQ", "Teknologi"),
    ("MSFT", "Microsoft Corporation", "NASDAQ", "Teknologi"),
    ("NVDA", "NVIDIA Corporation", "NASDAQ", "Teknologi"),
    ("GOOGL", "Alphabet Inc.", "NASDAQ", "Teknologi"),
    ("META", "Meta Platforms, Inc.", "NASDAQ", "Teknologi"),
    ("AMZN", "Amazon.com, Inc.", "NASDAQ", "Konsumer"),
    ("TSLA", "Tesla, Inc.", "NASDAQ", "Konsumer"),
    ("JPM", "JPMorgan Chase & Co.", "NYSE", "Keuangan"),
    ("KO", "The Coca-Cola Company", "NYSE", "Konsumer"),
    ("VOO", "Vanguard S&P 500 ETF", "NYSEARCA", "ETF"),
]

CATALOG: list[dict] = [
    {"symbol": s, "name": n, "exchange": "IDX", "currency": "IDR", "sector": sec, "is_active": True, "kind": "STOCK"}
    for s, n, sec in _IDX
] + [
    {"symbol": s, "name": n, "exchange": ex, "currency": "USD", "sector": sec, "is_active": True, "kind": "STOCK"}
    for s, n, ex, sec in _US
]

# Indeks pembanding (tidak bisa diperdagangkan). Exchange menentukan jadwal sync otomatis.
BENCHMARKS: list[dict] = [
    {"symbol": "^JKSE", "name": "IHSG (Indeks Harga Saham Gabungan)", "exchange": "IDX", "currency": "IDR",
     "sector": None, "is_active": True, "kind": "INDEX"},
    {"symbol": "^GSPC", "name": "S&P 500", "exchange": "NYSE", "currency": "USD",
     "sector": None, "is_active": True, "kind": "INDEX"},
]
