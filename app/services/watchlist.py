from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HistoricalPrice


async def last_two_closes(db: AsyncSession, stock_ids: list[int]) -> dict[int, list[tuple[date, Decimal]]]:
    """Dua penutupan terakhir per saham, terbaru dulu: {stock_id: [(tgl, close), (tgl, close)]}."""
    if not stock_ids:
        return {}
    rn = func.row_number().over(
        partition_by=HistoricalPrice.stock_id, order_by=HistoricalPrice.trade_date.desc()
    ).label("rn")
    sub = (
        select(HistoricalPrice.stock_id, HistoricalPrice.trade_date, HistoricalPrice.close, rn)
        .where(HistoricalPrice.stock_id.in_(stock_ids))
        .subquery()
    )
    rows = await db.execute(
        select(sub.c.stock_id, sub.c.trade_date, sub.c.close)
        .where(sub.c.rn <= 2)
        .order_by(sub.c.stock_id, sub.c.rn)
    )
    out: dict[int, list[tuple[date, Decimal]]] = {}
    for sid, d, c in rows.all():
        out.setdefault(sid, []).append((d, c))
    return out
