from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import PositionTarget, Stock, User
from app.schemas import OkOut, TargetIn, TargetOut
from app.services.analytics import _latest_prices, _positions
from app.services.targets import target_metrics

router = APIRouter(prefix="/targets", tags=["targets"])
MAX_TARGETS = 100


@router.get("", response_model=list[TargetOut])
async def list_targets(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(PositionTarget, Stock.symbol, Stock.name, Stock.currency)
        .join(Stock, Stock.id == PositionTarget.stock_id)
        .where(PositionTarget.user_id == user.id).order_by(Stock.symbol)
    )).all()
    ids = [t.stock_id for t, *_ in rows]
    positions = await _positions(db, user.id)
    prices = await _latest_prices(db, ids)
    out = []
    for t, sym, name, cur in rows:
        pos = positions.get(t.stock_id)
        qty = pos.quantity if pos else Decimal("0")
        avg = pos.avg_cost if pos is not None and pos.quantity > 0 else None
        price, price_date = prices.get(t.stock_id, (None, None))
        out.append(TargetOut(
            stock_id=t.stock_id, symbol=sym, name=name, currency=cur, quantity=qty,
            avg_cost=avg.quantize(Decimal("0.0001")) if avg is not None else None,
            price=price, price_date=price_date, target_price=t.target_price, stop_price=t.stop_price,
            note=t.note, target_hit_at=t.target_hit_at, stop_hit_at=t.stop_hit_at,
            **target_metrics(avg, price, t.target_price, t.stop_price),
        ))
    return out


@router.put("/{stock_id}", response_model=OkOut)
async def set_target(
    stock_id: int, data: TargetIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    stock = await db.get(Stock, stock_id)
    if stock is None or not stock.is_active or stock.kind != "STOCK":
        raise HTTPException(404, "Saham tidak ditemukan")
    try:
        existing = await db.scalar(select(PositionTarget).where(
            PositionTarget.user_id == user.id, PositionTarget.stock_id == stock_id))
        if existing is None:
            count = await db.scalar(
                select(func.count()).select_from(PositionTarget).where(PositionTarget.user_id == user.id))
            if (count or 0) >= MAX_TARGETS:
                raise HTTPException(400, f"Maksimal {MAX_TARGETS} target")
            db.add(PositionTarget(user_id=user.id, stock_id=stock_id, target_price=data.target_price,
                                  stop_price=data.stop_price, note=data.note))
        else:
            if data.target_price != existing.target_price:
                existing.target_hit_at = None   # target baru -> boleh memicu lagi
            if data.stop_price != existing.stop_price:
                existing.stop_hit_at = None
            existing.target_price, existing.stop_price, existing.note = data.target_price, data.stop_price, data.note
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise
    return OkOut()


@router.delete("/{stock_id}", response_model=OkOut)
async def delete_target(stock_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        await db.execute(delete(PositionTarget).where(
            PositionTarget.user_id == user.id, PositionTarget.stock_id == stock_id))
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return OkOut()
