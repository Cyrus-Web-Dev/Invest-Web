from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import PriceAlert, Stock, User
from app.schemas import AlertIn, AlertOut, OkOut

router = APIRouter(prefix="/alerts", tags=["alerts"])
MAX_ACTIVE_ALERTS = 50


def _out(a: PriceAlert, symbol: str) -> AlertOut:
    return AlertOut(
        id=a.id, stock_id=a.stock_id, symbol=symbol, direction=a.direction,
        target_price=a.target_price, is_active=a.is_active, created_at=a.created_at,
        triggered_at=a.triggered_at, triggered_price=a.triggered_price,
    )


@router.get("", response_model=list[AlertOut])
async def list_alerts(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(PriceAlert, Stock.symbol).join(Stock, Stock.id == PriceAlert.stock_id)
        .where(PriceAlert.user_id == user.id)
        .order_by(PriceAlert.is_active.desc(), PriceAlert.created_at.desc()).limit(200)
    )).all()
    return [_out(a, sym) for a, sym in rows]


@router.post("", response_model=AlertOut, status_code=201)
async def create_alert(
    data: AlertIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    stock = await db.get(Stock, data.stock_id)
    if stock is None or not stock.is_active:
        raise HTTPException(404, "Saham tidak ditemukan")
    active = await db.scalar(
        select(func.count()).select_from(PriceAlert)
        .where(PriceAlert.user_id == user.id, PriceAlert.is_active.is_(True))
    )
    if (active or 0) >= MAX_ACTIVE_ALERTS:
        raise HTTPException(400, f"Maksimal {MAX_ACTIVE_ALERTS} alert aktif")
    alert = PriceAlert(
        user_id=user.id, stock_id=stock.id, direction=data.direction, target_price=data.target_price
    )
    db.add(alert)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(alert)  # created_at diisi database
    return _out(alert, stock.symbol)


@router.delete("/{alert_id}", response_model=OkOut)
async def delete_alert(
    alert_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        res = await db.execute(
            delete(PriceAlert).where(PriceAlert.id == alert_id, PriceAlert.user_id == user.id)
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    if not res.rowcount:
        raise HTTPException(404, "Alert tidak ditemukan")
    return OkOut()
