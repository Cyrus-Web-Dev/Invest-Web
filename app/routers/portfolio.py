from datetime import datetime, timezone
from itertools import groupby

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import Stock, Transaction, User
from app.schemas import CashFlowIn, HoldingOut, TradeIn, TransactionOut, UserOut
from app.services.positions import Trade, compute_position
from app.services.ledger import add_cash_dated, add_trade_dated
from app.services.tags import join_tags
from app.services.trading import TradeError, apply_cash_flow, execute_trade

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/cash", response_model=UserOut)
async def cash_flow(
    data: CashFlowIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        if data.date is not None and data.date != datetime.now(timezone.utc).date():
            return await add_cash_dated(db, user.id, data.type, data.amount, data.date)
        return await apply_cash_flow(db, user.id, data.type, data.amount)
    except TradeError as e:
        raise HTTPException(e.status_code, e.message)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
async def create_transaction(
    data: TradeIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        if data.date is not None and data.date != datetime.now(timezone.utc).date():
            return await add_trade_dated(db, user.id, data)
        return await execute_trade(
            db, user.id, data.stock_id, data.type, data.quantity, data.price, data.fee, data.note,
            tags=join_tags(data.tags),
        )
    except TradeError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/transactions", response_model=list[TransactionOut])
async def list_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (select(Transaction).where(Transaction.user_id == user.id)
            .order_by(Transaction.executed_at.desc(), Transaction.id.desc()).limit(limit).offset(offset))
    return (await db.scalars(stmt)).all()


@router.get("/holdings", response_model=list[HoldingOut])
async def holdings(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.scalars(
        select(Transaction).where(Transaction.user_id == user.id)
        .order_by(Transaction.stock_id, Transaction.executed_at, Transaction.id)
    )).all()
    symbols = dict((await db.execute(select(Stock.id, Stock.symbol))).all())
    result = []
    for stock_id, group in groupby(rows, key=lambda t: t.stock_id):
        pos = compute_position(Trade(t.type, t.quantity, t.price, t.fee) for t in group)
        if pos.quantity > 0:
            result.append(HoldingOut(
                stock_id=stock_id, symbol=symbols.get(stock_id, "?"), quantity=pos.quantity,
                avg_cost=pos.avg_cost, total_cost=pos.total_cost, realized_pl=pos.realized_pl,
            ))
    return result
