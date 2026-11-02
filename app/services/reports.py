from datetime import date, timezone
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Dividend, HistoricalPrice, Stock, Transaction
from app.services.tax_report import DatedTrade


async def load_report_inputs(db: AsyncSession, user_id: int):
    rows = (await db.execute(
        select(Transaction, Stock.symbol).join(Stock, Stock.id == Transaction.stock_id)
        .where(Transaction.user_id == user_id).order_by(Transaction.executed_at, Transaction.id)
    )).all()
    trades = [DatedTrade(t.executed_at.astimezone(timezone.utc).date(), sym, t.type, t.quantity, t.price, t.fee)
              for t, sym in rows]
    divs = [(d, sym, a) for d, sym, a in (await db.execute(
        select(Dividend.paid_on, Stock.symbol, Dividend.amount).join(Stock, Stock.id == Dividend.stock_id)
        .where(Dividend.user_id == user_id).order_by(Dividend.paid_on)
    )).all()]
    return trades, divs


async def closing_prices(db: AsyncSession, symbols: list[str], on_or_before: date) -> dict[str, tuple[Decimal, date]]:
    """Penutupan terakhir pada/sebelum tanggal acuan, per simbol."""
    if not symbols:
        return {}
    latest = (
        select(HistoricalPrice.stock_id.label("sid"), func.max(HistoricalPrice.trade_date).label("d"))
        .join(Stock, Stock.id == HistoricalPrice.stock_id)
        .where(Stock.symbol.in_(symbols), HistoricalPrice.trade_date <= on_or_before)
        .group_by(HistoricalPrice.stock_id).subquery()
    )
    rows = await db.execute(
        select(Stock.symbol, HistoricalPrice.close, HistoricalPrice.trade_date)
        .join(HistoricalPrice, HistoricalPrice.stock_id == Stock.id)
        .join(latest, and_(latest.c.sid == HistoricalPrice.stock_id, latest.c.d == HistoricalPrice.trade_date))
    )
    return {sym: (close, d) for sym, close, d in rows.all()}
