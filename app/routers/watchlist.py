from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import Stock, User, Watchlist
from app.schemas import OkOut, WatchAdd, WatchItemOut
from app.services.alerts import change_pct
from app.services.watchlist import last_two_closes

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
MAX_WATCH = 100


@router.get("", response_model=list[WatchItemOut])
async def list_watch(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    stocks = (await db.scalars(
        select(Stock).join(Watchlist, Watchlist.stock_id == Stock.id)
        .where(Watchlist.user_id == user.id).order_by(Stock.symbol)
    )).all()
    closes = await last_two_closes(db, [s.id for s in stocks])
    out = []
    for s in stocks:
        pts = closes.get(s.id, [])
        last = pts[0] if pts else None
        prev = pts[1] if len(pts) > 1 else None
        out.append(WatchItemOut(
            stock_id=s.id, symbol=s.symbol, name=s.name, exchange=s.exchange, currency=s.currency,
            sector=s.sector, price=last[1] if last else None, price_date=last[0] if last else None,
            change_pct=change_pct(last[1], prev[1]) if last and prev else None,
        ))
    return out


@router.post("", response_model=OkOut, status_code=201)
async def add_watch(
    data: WatchAdd, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    stock = await db.get(Stock, data.stock_id)
    if stock is None or not stock.is_active:
        raise HTTPException(404, "Saham tidak ditemukan")
    count = await db.scalar(
        select(func.count()).select_from(Watchlist).where(Watchlist.user_id == user.id)
    )
    if (count or 0) >= MAX_WATCH:
        raise HTTPException(400, f"Maksimal {MAX_WATCH} saham dalam daftar pantauan")
    try:  # idempoten: menambah saham yang sudah ada tidak error
        await db.execute(
            pg_insert(Watchlist).values(user_id=user.id, stock_id=stock.id)
            .on_conflict_do_nothing(index_elements=["user_id", "stock_id"])
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return OkOut()


@router.delete("/{stock_id}", response_model=OkOut)
async def remove_watch(
    stock_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        await db.execute(
            delete(Watchlist).where(Watchlist.user_id == user.id, Watchlist.stock_id == stock_id)
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return OkOut()
