"""Perhitungan metrik portofolio. Semua uang memakai Decimal. Tanpa DB/Pandas agar mudah diuji."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from app.services.positions import Position

ZERO = Decimal("0")
CENT = Decimal("0.01")
FOUR = Decimal("0.0001")
HUNDRED = Decimal("100")


def money(v: Decimal) -> Decimal:
    # Harus identik dengan pembulatan di services/trading.py agar saldo kas cocok.
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def pct(numer: Decimal, denom: Decimal) -> Decimal | None:
    if denom <= 0:
        return None
    return (numer / denom * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)


def to_day(dt) -> date:
    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt.date()
    return dt


@dataclass(frozen=True)
class HoldingValue:
    stock_id: int
    symbol: str
    sector: str | None
    quantity: Decimal
    avg_cost: Decimal
    total_cost: Decimal
    price: Decimal
    price_date: date | None
    price_source: str  # "market" | "cost" (belum ada harga pasar -> pakai harga rata-rata)
    market_value: Decimal
    floating_pl: Decimal
    floating_pl_pct: Decimal | None
    realized_pl: Decimal


def value_holding(
    stock_id: int, symbol: str, sector: str | None, pos: Position,
    price: Decimal | None, price_date: date | None,
) -> HoldingValue:
    cost = money(pos.total_cost)
    if price is None:
        used, source, mv, pl = pos.avg_cost, "cost", cost, ZERO
    else:
        used, source = price, "market"
        mv = money(pos.quantity * price)
        pl = mv - cost
    return HoldingValue(
        stock_id=stock_id, symbol=symbol, sector=sector, quantity=pos.quantity,
        avg_cost=pos.avg_cost.quantize(FOUR, rounding=ROUND_HALF_UP), total_cost=cost,
        price=used, price_date=price_date if source == "market" else None,
        price_source=source, market_value=mv, floating_pl=pl,
        floating_pl_pct=pct(pl, cost), realized_pl=money(pos.realized_pl),
    )


@dataclass(frozen=True)
class Totals:
    cash: Decimal
    holdings_value: Decimal
    net_worth: Decimal
    net_deposits: Decimal
    total_pl: Decimal           # net_worth - net_deposits (sudah termasuk dividen)
    roi_pct: Decimal | None
    floating_pl: Decimal
    realized_pl: Decimal
    dividends_total: Decimal
    dividend_yield_pct: Decimal | None   # dividen 12 bulan / nilai pasar saat ini
    yield_on_cost_pct: Decimal | None    # dividen 12 bulan / total modal di saham


def build_totals(
    cash: Decimal, holdings: list[HoldingValue], deposits: Decimal, withdrawals: Decimal,
    dividends_total: Decimal, dividends_12m: Decimal, realized_total: Decimal,
) -> Totals:
    hv = sum((h.market_value for h in holdings), ZERO)
    cost_basis = sum((h.total_cost for h in holdings), ZERO)
    net_worth = cash + hv
    net_dep = deposits - withdrawals
    total_pl = net_worth - net_dep
    return Totals(
        cash=cash, holdings_value=hv, net_worth=net_worth, net_deposits=net_dep,
        total_pl=total_pl, roi_pct=pct(total_pl, net_dep),
        floating_pl=sum((h.floating_pl for h in holdings), ZERO),
        realized_pl=money(realized_total), dividends_total=dividends_total,
        dividend_yield_pct=pct(dividends_12m, hv),
        yield_on_cost_pct=pct(dividends_12m, cost_basis),
    )


@dataclass(frozen=True)
class AllocationRow:
    label: str
    value: Decimal
    pct: Decimal


def allocation(items: dict[str, Decimal]) -> list[AllocationRow]:
    """Nilai non-positif dibuang; hasil urut terbesar dulu."""
    positive = {k: v for k, v in items.items() if v > 0}
    total = sum(positive.values(), ZERO)
    if total <= 0:
        return []
    rows = [AllocationRow(k, v, pct(v, total)) for k, v in positive.items()]
    return sorted(rows, key=lambda r: r.value, reverse=True)


def xirr(flows: list[tuple[date, Decimal]]) -> float | None:
    """Imbal hasil tahunan berbobot uang (money-weighted). Setoran = negatif, penarikan dan
    nilai akhir = positif. None jika data belum cukup (butuh arus masuk & keluar, rentang >= 30 hari)."""
    if len(flows) < 2:
        return None
    flows = sorted(flows, key=lambda x: x[0])
    if not (any(a < 0 for _, a in flows) and any(a > 0 for _, a in flows)):
        return None
    d0 = flows[0][0]
    if (flows[-1][0] - d0).days < 30:
        return None
    data = [((d - d0).days / 365.0, float(a)) for d, a in flows]

    def f(r: float) -> float:
        return sum(a / ((1.0 + r) ** t) for t, a in data)

    lo, hi = -0.9999, 10.0
    flo, fhi = f(lo), f(hi)
    while flo * fhi > 0 and hi < 1e4:
        hi *= 10
        fhi = f(hi)
    if flo * fhi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = f(mid)
        if flo * fm <= 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


@dataclass(frozen=True)
class LedgerEvent:
    day: date
    cash_delta: Decimal
    capital_delta: Decimal
    stock_id: int | None = None
    qty_delta: Decimal = ZERO
    price: Decimal | None = None


def make_events(transactions, cash_flows, dividends) -> list[LedgerEvent]:
    """Ubah baris DB (atau objek bertipe sama) menjadi peristiwa buku besar."""
    events: list[LedgerEvent] = []
    for t in transactions:
        gross = t.quantity * t.price
        if t.type == "BUY":
            cash, qty = -money(gross + t.fee), t.quantity
        else:
            cash, qty = money(gross - t.fee), -t.quantity
        events.append(LedgerEvent(to_day(t.executed_at), cash, ZERO, t.stock_id, qty, t.price))
    for c in cash_flows:
        signed = c.amount if c.type == "DEPOSIT" else -c.amount
        events.append(LedgerEvent(to_day(c.occurred_at), signed, signed))
    for d in dividends:
        events.append(LedgerEvent(to_day(d.paid_on), d.amount, ZERO))
    return events
