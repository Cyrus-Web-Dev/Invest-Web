"""Atribusi kinerja: kontribusi tiap saham terhadap total untung/rugi (murni, tanpa DB).
Identitas akuntansi: total untung/rugi = jumlah (terealisasi + belum terealisasi + dividen) seluruh saham,
karena kas tidak menghasilkan untung/rugi dan fee sudah menjadi bagian dari harga perolehan."""
from dataclasses import dataclass
from decimal import Decimal

from app.services.metrics import ZERO, pct


@dataclass(frozen=True)
class AttrInput:
    symbol: str
    sector: str | None
    invested: Decimal      # total modal pembelian (termasuk fee beli) sepanjang riwayat
    realized: Decimal
    floating: Decimal
    dividends: Decimal
    held: bool


@dataclass(frozen=True)
class StockContribution:
    symbol: str
    sector: str | None
    invested: Decimal
    realized: Decimal
    floating: Decimal
    dividends: Decimal
    total: Decimal
    share_of_pl_pct: Decimal | None            # porsi terhadap total untung/rugi (hanya jika total positif)
    contribution_to_return_pct: Decimal | None  # total / modal bersih disetor
    return_on_cost_pct: Decimal | None          # total / modal pembelian saham itu
    held: bool


def build_attribution(
    items: list[AttrInput], total_pl: Decimal, net_deposits: Decimal
) -> tuple[list[StockContribution], Decimal]:
    """Return (baris urut kontribusi terbesar, selisih pembulatan = total_pl - jumlah kontribusi)."""
    rows: list[StockContribution] = []
    for it in items:
        total = it.realized + it.floating + it.dividends
        rows.append(StockContribution(
            symbol=it.symbol, sector=it.sector, invested=it.invested, realized=it.realized, floating=it.floating,
            dividends=it.dividends, total=total,
            share_of_pl_pct=pct(total, total_pl) if total_pl > 0 else None,
            contribution_to_return_pct=pct(total, net_deposits),
            return_on_cost_pct=pct(total, it.invested), held=it.held,
        ))
    rows.sort(key=lambda r: r.total, reverse=True)
    residual = total_pl - sum((r.total for r in rows), ZERO)
    return rows, residual
