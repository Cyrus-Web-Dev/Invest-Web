from decimal import Decimal

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, PositionTarget, PriceAlert, Stock
from app.services.alerts import alert_message, is_triggered
from app.services.targets import stop_message, target_message
from app.services.trading import _held_quantity


async def evaluate_alerts(db: AsyncSession, stock: Stock, price: Decimal) -> int:
    """Picu alert aktif untuk satu saham. Tiap alert hanya terpicu SEKALI: UPDATE bersyarat
    (is_active masih true) memastikan tidak ada notifikasi ganda walau job berjalan bersamaan."""
    fired = 0
    try:
        alerts = (await db.scalars(
            select(PriceAlert).where(PriceAlert.stock_id == stock.id, PriceAlert.is_active.is_(True))
        )).all()
        for a in alerts:
            if not is_triggered(a.direction, a.target_price, price):
                continue
            res = await db.execute(
                update(PriceAlert)
                .where(PriceAlert.id == a.id, PriceAlert.is_active.is_(True))
                .values(is_active=False, triggered_at=func.now(), triggered_price=price)
            )
            if res.rowcount:
                title, message = alert_message(stock.symbol, a.direction, a.target_price, price)
                db.add(Notification(user_id=a.user_id, kind="ALERT", title=title, message=message))
                fired += 1
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return fired


async def evaluate_targets(db: AsyncSession, stock: Stock, price: Decimal) -> int:
    """Picu target harga / stop loss (masing-masing sekali) HANYA untuk user yang masih memegang saham itu."""
    fired = 0
    try:
        pending = (await db.scalars(
            select(PositionTarget).where(
                PositionTarget.stock_id == stock.id,
                or_(
                    and_(PositionTarget.target_price.is_not(None), PositionTarget.target_hit_at.is_(None)),
                    and_(PositionTarget.stop_price.is_not(None), PositionTarget.stop_hit_at.is_(None)),
                ),
            )
        )).all()
        for t in pending:
            if await _held_quantity(db, t.user_id, stock.id) <= 0:
                continue
            if t.target_price is not None and t.target_hit_at is None and price >= t.target_price:
                res = await db.execute(
                    update(PositionTarget)
                    .where(PositionTarget.id == t.id, PositionTarget.target_hit_at.is_(None))
                    .values(target_hit_at=func.now())
                )
                if res.rowcount:
                    title, message = target_message(stock.symbol, t.target_price, price)
                    db.add(Notification(user_id=t.user_id, kind="TARGET", title=title, message=message))
                    fired += 1
            elif t.stop_price is not None and t.stop_hit_at is None and price <= t.stop_price:
                res = await db.execute(
                    update(PositionTarget)
                    .where(PositionTarget.id == t.id, PositionTarget.stop_hit_at.is_(None))
                    .values(stop_hit_at=func.now())
                )
                if res.rowcount:
                    title, message = stop_message(stock.symbol, t.stop_price, price)
                    db.add(Notification(user_id=t.user_id, kind="STOP", title=title, message=message))
                    fired += 1
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return fired
