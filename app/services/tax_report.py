"""Laporan tahunan: laba/rugi terealisasi per penjualan, dividen, dan posisi akhir tahun (murni, tanpa DB).
Harga perolehan memakai metode rata-rata bergerak (termasuk fee beli), sama dengan perhitungan di seluruh aplikasi."""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.services.metrics import ZERO, money
from app.services.positions import Position, Trade, compute_position

NOTES = [
    "Laporan ini disusun otomatis dari catatan Anda di Stockfolio sebagai bantuan administrasi. Ini bukan nasihat pajak "
    "dan bukan dokumen resmi.",
    "Perlakuan pajak atas penjualan saham dan dividen bergantung pada ketentuan yang berlaku dan kondisi masing-masing wajib pajak. "
    "Cocokkan angka dengan konfirmasi dan laporan resmi dari broker/KSEI, dan konsultasikan dengan konsultan pajak atau KPP.",
    "Harga perolehan memakai metode rata-rata bergerak dan sudah termasuk fee pembelian. Fee penjualan sebagaimana Anda catat "
    "(umumnya sudah mencakup komisi dan pajak transaksi dari broker).",
    "Tanggal mengikuti zona waktu UTC. Nilai posisi akhir tahun memakai harga penutupan terakhir di database pada atau sebelum "
    "tanggal acuan dan bisa berbeda dari nilai resmi.",
]


@dataclass(frozen=True)
class DatedTrade:
    day: date
    symbol: str
    type: str       # BUY | SELL
    quantity: Decimal
    price: Decimal
    fee: Decimal


@dataclass(frozen=True)
class SaleLine:
    day: date
    symbol: str
    quantity: Decimal
    gross: Decimal
    fee: Decimal
    net: Decimal
    cost_basis: Decimal
    realized: Decimal


@dataclass(frozen=True)
class DividendLine:
    day: date
    symbol: str
    amount: Decimal


@dataclass(frozen=True)
class AnnualTotals:
    sales_count: int
    gross_sales: Decimal
    sell_fees: Decimal
    net_proceeds: Decimal
    cost_basis: Decimal
    realized_pl: Decimal
    dividends: Decimal


@dataclass(frozen=True)
class StockYear:
    symbol: str
    gross: Decimal
    cost_basis: Decimal
    realized: Decimal
    dividends: Decimal


@dataclass(frozen=True)
class PositionYE:
    symbol: str
    quantity: Decimal
    total_cost: Decimal
    avg_cost: Decimal
    price: Decimal | None
    price_date: date | None
    market_value: Decimal | None


@dataclass
class AnnualReport:
    year: int
    as_of: date
    generated_on: date
    totals: AnnualTotals
    by_stock: list[StockYear]
    sales: list[SaleLine]
    dividends: list[DividendLine]
    positions: list[PositionYE]
    notes: list[str] = field(default_factory=lambda: list(NOTES))


def sale_lines(trades: list[DatedTrade]) -> list[SaleLine]:
    """Satu baris per penjualan, seluruh riwayat. `trades` HARUS urut kronologis (per saham cukup).
    Nilai tiap baris dibulatkan ke sen agar total laporan konsisten dengan barisnya."""
    by: dict[str, list[DatedTrade]] = defaultdict(list)
    for t in trades:
        by[t.symbol].append(t)
    lines: list[SaleLine] = []
    for sym, ts in by.items():
        qty, cost = ZERO, ZERO
        for t in ts:
            if t.type == "BUY":
                cost += t.quantity * t.price + t.fee
                qty += t.quantity
            elif t.type == "SELL":
                if t.quantity > qty:
                    raise ValueError(f"Penjualan {sym} melebihi kepemilikan pada {t.day}")
                basis = cost if t.quantity == qty else (cost / qty) * t.quantity
                gross, fee = money(t.quantity * t.price), money(t.fee)
                net, basis_r = gross - fee, money(basis)
                lines.append(SaleLine(t.day, sym, t.quantity, gross, fee, net, basis_r, net - basis_r))
                cost -= basis
                qty -= t.quantity
            else:
                raise ValueError(f"Tipe transaksi tidak dikenal: {t.type}")
    lines.sort(key=lambda s: (s.day, s.symbol))
    return lines


def positions_at(trades: list[DatedTrade], end: date) -> dict[str, Position]:
    by: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        if t.day <= end:
            by[t.symbol].append(Trade(t.type, t.quantity, t.price, t.fee))
    return {s: compute_position(ts) for s, ts in by.items()}


def available_years(trades: list[DatedTrade], dividends: list[tuple[date, str, Decimal]], today: date) -> list[int]:
    years = {t.day.year for t in trades} | {d.year for d, _, _ in dividends} | {today.year}
    return sorted(years, reverse=True)


def build_annual_report(
    trades: list[DatedTrade], dividends: list[tuple[date, str, Decimal]],
    prices: dict[str, tuple[Decimal, date]], year: int, today: date,
) -> AnnualReport:
    as_of = min(date(year, 12, 31), today)
    sales = [s for s in sale_lines(trades) if s.day.year == year]
    divs = sorted((DividendLine(d, sym, amt) for d, sym, amt in dividends if d.year == year), key=lambda x: (x.day, x.symbol))

    stock_rows: dict[str, list] = defaultdict(lambda: [ZERO, ZERO, ZERO, ZERO])   # gross, basis, realized, dividends
    for s in sales:
        r = stock_rows[s.symbol]
        r[0] += s.gross; r[1] += s.cost_basis; r[2] += s.realized
    for d in divs:
        stock_rows[d.symbol][3] += d.amount
    by_stock = sorted((StockYear(sym, *vals) for sym, vals in stock_rows.items()), key=lambda x: x.symbol)

    totals = AnnualTotals(
        sales_count=len(sales),
        gross_sales=sum((s.gross for s in sales), ZERO), sell_fees=sum((s.fee for s in sales), ZERO),
        net_proceeds=sum((s.net for s in sales), ZERO), cost_basis=sum((s.cost_basis for s in sales), ZERO),
        realized_pl=sum((s.realized for s in sales), ZERO), dividends=sum((d.amount for d in divs), ZERO),
    )

    positions: list[PositionYE] = []
    for sym, pos in sorted(positions_at(trades, as_of).items()):
        if pos.quantity <= 0:
            continue
        price, price_date = prices.get(sym, (None, None))
        positions.append(PositionYE(
            symbol=sym, quantity=pos.quantity, total_cost=money(pos.total_cost), avg_cost=pos.avg_cost.quantize(Decimal("0.0001")),
            price=price, price_date=price_date, market_value=money(pos.quantity * price) if price is not None else None,
        ))
    return AnnualReport(year, as_of, today, totals, by_stock, sales, divs, positions)
