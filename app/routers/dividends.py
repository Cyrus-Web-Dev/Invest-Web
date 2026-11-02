from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import Dividend, User
from app.schemas import DividendIn, DividendOut
from app.services.trading import TradeError, record_dividend

router = APIRouter(prefix="/portfolio/dividends", tags=["dividends"])


@router.post("", response_model=DividendOut, status_code=201)
async def add_dividend(
    data: DividendIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        return await record_dividend(db, user.id, data.stock_id, data.amount, data.paid_on)
    except TradeError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("", response_model=list[DividendOut])
async def list_dividends(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (select(Dividend).where(Dividend.user_id == user.id)
            .order_by(Dividend.paid_on.desc(), Dividend.id.desc()).limit(limit).offset(offset))
    return (await db.scalars(stmt)).all()
