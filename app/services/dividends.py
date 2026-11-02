"""Analitik pendapatan dividen dari catatan pengguna (murni, tanpa DB)."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.services.metrics import ZERO, pct

Q2 = Decimal("0.01")


@dataclass(frozen=True)
class DivRecord:
    stock_id: int
    symbol: str
    paid_on: date
    amount: Decimal


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def last_n_months(end: date, n: int) -> list[str]:
    """n bulan terakhir (urut lama -> baru), berakhir di bulan `end`."""
    keys: list[str] = []
    y, m = end.year, end.month
    for _ in range(n):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return keys[::-1]


def monthly_totals(records: list[DivRecord], end: date, n: int = 24) -> list[tuple[str, Decimal]]:
    sums: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for r in records:
        sums[month_key(r.paid_on)] += r.amount
    return [(k, sums.get(k, ZERO)) for k in last_n_months(end, n)]


def yearly_totals(records: list[DivRecord]) -> list[tuple[int, Decimal]]:
    sums: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for r in records:
        sums[r.paid_on.year] += r.amount
    return sorted(sums.items())


def trailing_12m(records: list[DivRecord], end: date) -> Decimal:
    start = end - timedelta(days=365)
    return sum((r.amount for r in records if start < r.paid_on <= end), ZERO)


def sum_between(records: list[DivRecord], start: date, end: date) -> Decimal:
    return sum((r.amount for r in records if start <= r.paid_on <= end), ZERO)


@dataclass(frozen=True)
class CalendarMonth:
    month: int
    amount: Decimal
    symbols: list[str]


def projected_calendar(records: list[DivRecord], held_symbols: set[str], end: date) -> list[CalendarMonth]:
    """Perkiraan bulan & nominal dividen berdasarkan 24 bulan terakhir catatan Anda untuk saham yang masih dimiliki.
    Nominal tiap saham per bulan = rata-rata total bulan itu di tahun-tahun yang tercatat."""
    start = end - timedelta(days=730)
    per: dict[tuple[str, int, int], Decimal] = defaultdict(lambda: ZERO)   # (simbol, tahun, bulan) -> jumlah
    for r in records:
        if r.symbol in held_symbols and start < r.paid_on <= end:
            per[(r.symbol, r.paid_on.year, r.paid_on.month)] += r.amount
    by_sym_month: dict[tuple[str, int], list[Decimal]] = defaultdict(list)
    for (sym, _y, m), amt in per.items():
        by_sym_month[(sym, m)].append(amt)
    months: dict[int, tuple[Decimal, list[str]]] = {m: (ZERO, []) for m in range(1, 13)}
    for (sym, m), amts in by_sym_month.items():
        avg = (sum(amts, ZERO) / len(amts)).quantize(Q2, rounding=ROUND_HALF_UP)
        total, syms = months[m]
        months[m] = (total + avg, syms + [sym])
    return [CalendarMonth(m, months[m][0], sorted(months[m][1])) for m in range(1, 13)]


@dataclass(frozen=True)
class StockDividend:
    symbol: str
    total: Decimal
    last_12m: Decimal
    last_paid: date
    payments: int
    held: bool
    quantity: Decimal | None
    yield_on_cost_pct: Decimal | None
    current_yield_pct: Decimal | None


def per_stock(records: list[DivRecord], held: dict[str, tuple[Decimal, Decimal, Decimal]], end: date) -> list[StockDividend]:
    """held: simbol -> (jumlah lembar, total biaya, nilai pasar)."""
    groups: dict[str, list[DivRecord]] = defaultdict(list)
    for r in records:
        groups[r.symbol].append(r)
    out: list[StockDividend] = []
    for sym, rs in groups.items():
        l12 = trailing_12m(rs, end)
        h = held.get(sym)
        out.append(StockDividend(
            symbol=sym, total=sum((r.amount for r in rs), ZERO), last_12m=l12,
            last_paid=max(r.paid_on for r in rs), payments=len(rs), held=h is not None,
            quantity=h[0] if h else None,
            yield_on_cost_pct=pct(l12, h[1]) if h else None,
            current_yield_pct=pct(l12, h[2]) if h else None,
        ))
    return sorted(out, key=lambda s: s.total, reverse=True)
