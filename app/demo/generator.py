"""Generator data demo: deterministik, murni, offline. SEMUA DATA DI SINI ADALAH SIMULASI.
Harga dibangkitkan dengan jalan acak berbenih (tanpa data pasar nyata); transaksi mengikuti aturan sederhana
dan divalidasi agar kas tidak pernah negatif dan penjualan tidak melebihi kepemilikan."""
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.services.price_providers.base import PriceBar

LOT = 100
BUY_FEE, SELL_FEE, DIV_NET = Decimal("0.0015"), Decimal("0.0025"), Decimal("0.9")
INDEX_SYMBOL = "^JKSE"


@dataclass(frozen=True)
class Stk:
    p0: float        # harga awal (simulasi)
    mu: float        # drift harian
    vol: float       # volatilitas harian
    beta: float      # sensitivitas terhadap indeks
    divs: tuple = () # ((bulan, yield), ...) per pembayaran


UNIVERSE: dict[str, Stk] = {
    "BBCA.JK": Stk(9300, 0.00045, 0.011, 0.9, ((4, 0.010), (12, 0.005))),
    "BBRI.JK": Stk(4300, 0.00030, 0.015, 1.1, ((3, 0.035), (12, 0.018))),
    "BMRI.JK": Stk(5600, 0.00040, 0.014, 1.1, ((3, 0.035), (9, 0.012))),
    "TLKM.JK": Stk(3100, 0.00005, 0.014, 0.8, ((7, 0.040), (11, 0.020))),
    "ASII.JK": Stk(5000, 0.00015, 0.015, 1.0, ((6, 0.040), (10, 0.017))),
    "UNVR.JK": Stk(2400, -0.00060, 0.014, 0.7, ((6, 0.035), (12, 0.025))),
    "ICBP.JK": Stk(10800, 0.00030, 0.012, 0.6, ((7, 0.020),)),
    "KLBF.JK": Stk(1500, 0.00005, 0.013, 0.7, ((6, 0.020),)),
    "ANTM.JK": Stk(1650, 0.00035, 0.025, 1.3, ((6, 0.015),)),
    "PTBA.JK": Stk(2700, 0.00020, 0.020, 1.0, ((5, 0.060), (10, 0.030))),
    "AMRT.JK": Stk(2300, 0.00030, 0.016, 0.8, ((5, 0.003),)),
}
WATCH_ONLY: dict[str, Stk] = {          # hanya dipantau (punya harga, tidak dibeli)
    "GOTO.JK": Stk(75, 0.0002, 0.030, 1.4),
    "MDKA.JK": Stk(2300, 0.0002, 0.024, 1.2),
    "ISAT.JK": Stk(2400, 0.0003, 0.016, 0.9),
}
CORE = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK"]
ROTATION = ["UNVR.JK", "ICBP.JK", "KLBF.JK", "PTBA.JK", "ANTM.JK", "AMRT.JK", "BBCA.JK", "BMRI.JK", "TLKM.JK"]

TAGS = {
    "BBCA.JK": ("value", "jangka-panjang"), "BBRI.JK": ("value", "jangka-panjang"),
    "BMRI.JK": ("value", "jangka-panjang"), "TLKM.JK": ("dividend", "defensif"),
    "ASII.JK": ("value", "dividend"), "UNVR.JK": ("dividend", "defensif"),
    "ICBP.JK": ("dividend", "defensif"), "KLBF.JK": ("dividend", "defensif"),
    "AMRT.JK": ("dividend", "defensif"), "PTBA.JK": ("dividend", "siklikal"),
    "ANTM.JK": ("trading", "siklikal"),
}
NOTES = {
    "BBCA.JK": ["Fundamental kuat dan dana murah tinggi; akumulasi bertahap saat koreksi", "Tambah posisi: valuasi wajar dibanding rata-rata historis", "Rutin akumulasi bulanan untuk jangka panjang"],
    "BBRI.JK": ["Penetrasi segmen mikro luas; pembagian dividen konsisten", "Tambah saat harga turun mendekati area dukungan", "Averaging bertahap sesuai rencana"],
    "BMRI.JK": ["Kualitas aset membaik, pertumbuhan kredit sehat", "Tambah posisi setelah laporan kuartal solid", "Akumulasi rutin"],
    "TLKM.JK": ["Arus kas stabil dan dividen menarik untuk portofolio defensif", "Tambah untuk memperkuat porsi dividen", "Akumulasi bertahap"],
    "ASII.JK": ["Diversifikasi bisnis (otomotif, alat berat, keuangan) dan dividen rutin", "Tambah saat valuasi di bawah rata-rata", "Akumulasi bertahap"],
    "UNVR.JK": ["Merek kuat dan arus kas stabil; berharap penjualan pulih", "Tambah kecil untuk rata-rata turun, pantau kinerja berikutnya", "Posisi kecil, dievaluasi tiap kuartal"],
    "ICBP.JK": ["Bisnis makanan defensif dengan margin stabil", "Tambah saat harga terkoreksi", "Akumulasi bertahap"],
    "KLBF.JK": ["Sektor kesehatan defensif; neraca bersih dan dividen konsisten", "Tambah posisi kecil", "Akumulasi bertahap"],
    "ANTM.JK": ["Trading jangka menengah mengikuti siklus komoditas, disiplin target dan stop loss", "Masuk di area dukungan dengan stop loss ketat", "Posisi taktis, tidak untuk ditahan lama"],
    "PTBA.JK": ["Dividen besar dari siklus komoditas; pantau harga batu bara", "Tambah menjelang musim dividen", "Akumulasi bertahap"],
    "AMRT.JK": ["Ritel dengan pertumbuhan gerai stabil", "Tambah kecil saat koreksi", "Akumulasi bertahap"],
}


def tick(price: float) -> int:
    """Fraksi harga Bursa Efek Indonesia."""
    if price < 200:
        return 1
    if price < 500:
        return 2
    if price < 2000:
        return 5
    if price < 5000:
        return 10
    return 25


def round_tick(price: float) -> Decimal:
    t = tick(price)
    return Decimal(max(t, int(round(price / t)) * t))


def business_days(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def gen_prices(days: list[date], seed: int) -> dict[str, list[PriceBar]]:
    idx_mu, idx_vol = 0.0003, 0.008
    mrng = random.Random(f"{seed}-market")
    market = [mrng.gauss(idx_mu, idx_vol) for _ in days]
    out: dict[str, list[PriceBar]] = {}

    # indeks
    rng = random.Random(f"{seed}-{INDEX_SYMBOL}")
    level, bars = 7000.0, []
    for d, m in zip(days, market):
        prev = level
        level *= 1 + m
        o = prev * (1 + rng.gauss(0, 0.002))
        hi, lo = max(o, level) * (1 + abs(rng.gauss(0, 0.002))), min(o, level) * (1 - abs(rng.gauss(0, 0.002)))
        q = lambda x: Decimal(str(round(x, 2)))  # noqa: E731
        bars.append(PriceBar(d, q(o), q(max(hi, o, level)), q(min(lo, o, level)), q(level), 0))
    out[INDEX_SYMBOL] = bars

    for sym, s in {**UNIVERSE, **WATCH_ONLY}.items():
        rng = random.Random(f"{seed}-{sym}")
        idio = s.vol * 0.8
        raw, prev_c, bars = s.p0, round_tick(s.p0), []
        base_vol = 5e11 / s.p0
        for d, m in zip(days, market):
            raw = max(raw * (1 + s.mu + s.beta * (m - idx_mu) + rng.gauss(0, idio)), 20.0)
            c = round_tick(raw)
            o = round_tick(float(prev_c) * (1 + rng.gauss(0, 0.003)))
            hi = round_tick(max(float(o), float(c)) * (1 + abs(rng.gauss(0, 0.004))))
            lo = round_tick(min(float(o), float(c)) * (1 - abs(rng.gauss(0, 0.004))))
            hi, lo = max(hi, o, c), min(lo, o, c)
            volume = int(rng.lognormvariate(math.log(base_vol), 0.4))
            bars.append(PriceBar(d, o, hi, lo, c, volume))
            prev_c = c
        out[sym] = bars
    return out


@dataclass(frozen=True)
class DemoTrade:
    seq: int
    day: date
    symbol: str
    type: str          # BUY | SELL
    qty: int
    price: Decimal
    fee: Decimal
    note: str
    tags: tuple


@dataclass(frozen=True)
class DemoCash:
    seq: int
    day: date
    type: str          # DEPOSIT | WITHDRAW
    amount: Decimal
    note: str | None


@dataclass(frozen=True)
class DemoDividend:
    seq: int
    day: date
    symbol: str
    amount: Decimal


@dataclass
class DemoPlan:
    days: list[date]
    prices: dict[str, list[PriceBar]]
    trades: list[DemoTrade]
    cashflows: list[DemoCash]
    dividends: list[DemoDividend]
    final_cash: Decimal
    holdings: dict[str, tuple[int, Decimal]]   # simbol -> (lembar, harga rata-rata)


def _fee(gross: Decimal, rate: Decimal) -> Decimal:
    return (gross * rate).to_integral_value(ROUND_HALF_UP)


def generate_plan(today: date, seed: int = 2026, months: int = 18) -> DemoPlan:
    start = today - timedelta(days=int(months * 30.4))
    days = business_days(start, today)
    prices = gen_prices(days, seed)
    close = {s: {b.trade_date: b.close for b in bars} for s, bars in prices.items()}

    cash = Decimal(0)
    qty: dict[str, int] = defaultdict(int)
    cost: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    buys_count: dict[str, int] = defaultdict(int)
    trades: list[DemoTrade] = []
    flows: list[DemoCash] = []
    divs: list[DemoDividend] = []
    seq = 0

    month_idx = [i for i, d in enumerate(days) if i == 0 or d.month != days[i - 1].month]
    deposit_at = {0: Decimal(50_000_000)}
    buys_at: dict[int, list[tuple[str, Decimal]]] = defaultdict(list)
    for k, sym in enumerate(CORE):
        buys_at[1 + k].append((sym, Decimal(9_000_000)))
    for n, i in enumerate(month_idx[1:], start=1):
        deposit_at[i] = Decimal(5_000_000)
        buys_at[i + 1].append((ROTATION[(n - 1) % len(ROTATION)], Decimal(5_000_000)))
    withdraw_at = 300 if len(days) > 320 else -1
    sell_days = set(range(120, len(days), 60))
    div_done: set[tuple[str, int, int]] = set()

    for i, d in enumerate(days):
        if i in deposit_at:
            cash += deposit_at[i]
            flows.append(DemoCash(seq, d, "DEPOSIT", deposit_at[i], "Modal awal" if i == 0 else "Setoran rutin bulanan"))
            seq += 1
        if i == withdraw_at and cash >= Decimal(10_000_000):
            cash -= Decimal(5_000_000)
            flows.append(DemoCash(seq, d, "WITHDRAW", Decimal(5_000_000), "Penarikan untuk kebutuhan pribadi"))
            seq += 1
        for sym, s in UNIVERSE.items():
            if qty[sym] <= 0:
                continue
            for month, y in s.divs:
                key = (sym, d.year, month)
                if d.month == month and d.day >= 15 and key not in div_done:
                    div_done.add(key)
                    dps = (close[sym][d] * Decimal(str(y))).to_integral_value(ROUND_HALF_UP)
                    amount = (Decimal(qty[sym]) * dps * DIV_NET).to_integral_value(ROUND_HALF_UP)
                    if amount > 0:
                        cash += amount
                        divs.append(DemoDividend(seq, d, sym, amount))
                        seq += 1
        for sym, budget in buys_at.get(i, []):
            price = close[sym][d]
            budget = min(budget, cash * Decimal("0.98"))
            lots = int(budget // (price * LOT * (1 + BUY_FEE)))
            while lots >= 1 and price * lots * LOT + _fee(price * lots * LOT, BUY_FEE) > cash:
                lots -= 1
            if lots < 1:
                continue
            shares = lots * LOT
            gross = price * shares
            fee = _fee(gross, BUY_FEE)
            notes = NOTES[sym]
            cash -= gross + fee
            qty[sym] += shares
            cost[sym] += gross + fee
            trades.append(DemoTrade(seq, d, sym, "BUY", shares, price, fee, notes[buys_count[sym] % len(notes)], TAGS[sym]))
            buys_count[sym] += 1
            seq += 1
        if i in sell_days:
            cands = [(close[sym][d] / (cost[sym] / qty[sym]) - 1, sym) for sym in UNIVERSE if qty[sym] >= 2 * LOT]
            if cands:
                best, worst = max(cands), min(cands)
                pick = None
                if best[0] > Decimal("0.08"):
                    pick = (best[1], Decimal("0.4"), "Ambil untung sebagian: kenaikan sudah melewati target awal", ("profit-taking",))
                elif worst[0] < Decimal("-0.10"):
                    pick = (worst[1], Decimal("0.5"), "Cut loss: tesis awal tidak lagi sesuai, kurangi risiko", ("cut-loss",))
                if pick:
                    sym, frac, note, tags = pick
                    lots = max(1, int(Decimal(qty[sym] // LOT) * frac))
                    shares = lots * LOT
                    price = close[sym][d]
                    gross = price * shares
                    fee = _fee(gross, SELL_FEE)
                    avg = cost[sym] / qty[sym]
                    cash += gross - fee
                    cost[sym] -= avg * shares
                    qty[sym] -= shares
                    trades.append(DemoTrade(seq, d, sym, "SELL", shares, price, fee, note, tags))
                    seq += 1

    holdings = {s: (q, (cost[s] / q).quantize(Decimal("0.0001"))) for s, q in qty.items() if q > 0}
    return DemoPlan(days, prices, trades, flows, divs, cash, holdings)
