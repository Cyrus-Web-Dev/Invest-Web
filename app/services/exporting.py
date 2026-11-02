import io
from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CashFlow, Dividend, Stock, Transaction
from app.services.analytics import PortfolioView
from app.services.tags import split_tags
from app.services.export_format import (
    HOLDING_HEADERS, LEDGER_HEADERS, fmt_num, ledger_row, sanitize_cell,
)


async def load_ledger(db: AsyncSession, user_id: int) -> list[list[str]]:
    """Seluruh buku besar (transaksi, kas, dividen) berurutan kronologis, format = format impor."""
    items: list[tuple[datetime, int, list[str]]] = []
    seq = 0
    txs = (await db.execute(
        select(Transaction, Stock.symbol).join(Stock, Stock.id == Transaction.stock_id)
        .where(Transaction.user_id == user_id)
    )).all()
    for t, sym in txs:
        at = t.executed_at.astimezone(timezone.utc)
        items.append((at, seq, ledger_row(t.type, at.date(), sym, t.quantity, t.price, t.fee, None, t.note, split_tags(t.tags))))
        seq += 1
    for c in (await db.scalars(select(CashFlow).where(CashFlow.user_id == user_id))).all():
        at = c.occurred_at.astimezone(timezone.utc)
        items.append((at, seq, ledger_row(c.type, at.date(), None, None, None, None, c.amount, None)))
        seq += 1
    divs = (await db.execute(
        select(Dividend, Stock.symbol).join(Stock, Stock.id == Dividend.stock_id)
        .where(Dividend.user_id == user_id)
    )).all()
    for d, sym in divs:
        at = datetime.combine(d.paid_on, time(12, 0), tzinfo=timezone.utc)
        items.append((at, seq, ledger_row("DIVIDEND", d.paid_on, sym, None, None, None, d.amount, None)))
        seq += 1
    items.sort(key=lambda x: (x[0], x[1]))
    return [r for _, _, r in items]


def holdings_rows(view: PortfolioView) -> list[list[str]]:
    return [
        [
            sanitize_cell(h.symbol), sanitize_cell(h.sector or ""), fmt_num(h.quantity), fmt_num(h.avg_cost),
            fmt_num(h.total_cost), fmt_num(h.price), fmt_num(h.market_value), fmt_num(h.floating_pl),
            fmt_num(h.floating_pl_pct), fmt_num(h.realized_pl), h.price_source,
        ]
        for h in view.holdings
    ]


def _num(v: str):
    """Teks angka -> float untuk sel Excel; selain itu tetap teks."""
    try:
        return float(v) if v != "" else None
    except ValueError:
        return v


def build_xlsx(view: PortfolioView, ledger: list[list[str]], today) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="4F46E5")

    def write_table(ws, headers, rows, numeric_from=0):
        ws.append(headers)
        for c in ws[1]:
            c.font, c.fill, c.alignment = head_font, head_fill, Alignment(horizontal="center")
        for r in rows:
            ws.append([_num(v) if i >= numeric_from else sanitize_cell(v) for i, v in enumerate(r)])
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 44)
        ws.freeze_panes = "A2"

    t = view.totals
    ws = wb.active
    ws.title = "Ringkasan"
    ws.append(["Laporan Stockfolio", str(today)])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([])
    summary = [
        ("Net Worth", t.net_worth), ("Kas", t.cash), ("Nilai saham", t.holdings_value),
        ("Modal bersih disetor", t.net_deposits), ("Total untung/rugi", t.total_pl),
        ("ROI (%)", t.roi_pct), ("Floating P/L", t.floating_pl), ("Realized P/L", t.realized_pl),
        ("Total dividen", t.dividends_total), ("Dividend yield 12 bln (%)", t.dividend_yield_pct),
        ("Yield on cost (%)", t.yield_on_cost_pct), ("XIRR (%)", view.xirr_pct),
    ]
    for label, val in summary:
        ws.append([label, float(val) if val is not None else "—"])
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 22
    for row in ws.iter_rows(min_row=3, max_col=1):
        row[0].font = Font(bold=True)

    write_table(wb.create_sheet("Posisi"), HOLDING_HEADERS, holdings_rows(view), numeric_from=2)
    write_table(wb.create_sheet("Transaksi"), LEDGER_HEADERS, ledger, numeric_from=3)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
