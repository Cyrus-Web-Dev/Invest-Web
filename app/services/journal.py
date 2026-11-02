"""Jurnal keputusan beli: seberapa baik tiap pembelian dibanding harga terakhir (murni)."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.services.metrics import ZERO, money

Q2 = Decimal("0.01")
UNTAGGED = "(tanpa tag)"


@dataclass(frozen=True)
class BuyRecord:
    id: int
    day: date
    stock_id: int
    symbol: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    note: str | None
    tags: list[str]


@dataclass(frozen=True)
class JournalItem:
    id: int
    day: date
    symbol: str
    quantity: Decimal
    price: Decimal
    cost: Decimal
    current_price: Decimal | None
    return_pct: Decimal | None
    pnl: Decimal | None
    still_held: bool
    note: str | None
    tags: list[str]


@dataclass(frozen=True)
class TagStat:
    tag: str
    count: int
    total_cost: Decimal
    weighted_return_pct: Decimal | None
    win_rate_pct: Decimal | None


def _ret(cur: Decimal | None, buy: Decimal) -> Decimal | None:
    if cur is None or buy <= 0:
        return None
    return ((cur / buy - 1) * 100).quantize(Q2, rounding=ROUND_HALF_UP)


def build_journal(buys: list[BuyRecord], prices: dict[int, Decimal], held: set[int]) -> tuple[list[JournalItem], list[TagStat]]:
    """Return sejak beli = harga terakhir vs harga beli (belum memperhitungkan penjualan sebagian & dividen)."""
    items: list[JournalItem] = []
    for b in sorted(buys, key=lambda x: (x.day, x.id), reverse=True):
        cur = prices.get(b.stock_id)
        items.append(JournalItem(
            id=b.id, day=b.day, symbol=b.symbol, quantity=b.quantity, price=b.price,
            cost=money(b.quantity * b.price + b.fee), current_price=cur, return_pct=_ret(cur, b.price),
            pnl=money(b.quantity * (cur - b.price) - b.fee) if cur is not None else None,
            still_held=b.stock_id in held, note=b.note, tags=b.tags,
        ))
    groups: dict[str, list[JournalItem]] = defaultdict(list)
    for it in items:
        for tag in (it.tags or [UNTAGGED]):
            groups[tag].append(it)
    stats: list[TagStat] = []
    for tag, its in groups.items():
        total_cost = sum((i.cost for i in its), ZERO)
        with_ret = [i for i in its if i.return_pct is not None]
        w_cost = sum((i.cost for i in with_ret), ZERO)
        weighted = (sum((i.return_pct * i.cost for i in with_ret), ZERO) / w_cost).quantize(Q2, rounding=ROUND_HALF_UP) if w_cost > 0 else None
        win = (Decimal(sum(1 for i in with_ret if i.return_pct > 0)) / len(with_ret) * 100).quantize(Q2, rounding=ROUND_HALF_UP) if with_ret else None
        stats.append(TagStat(tag, len(its), total_cost, weighted, win))
    stats.sort(key=lambda s: s.total_cost, reverse=True)
    return items, stats
