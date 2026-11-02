from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import (
    CashUpdate, DividendUpdate, LedgerItemOut, LedgerPageOut, OkOut, TradeUpdate,
)
from app.services import ledger as svc
from app.services.trading import TradeError

router = APIRouter(prefix="/portfolio", tags=["ledger"])


def _changes(data, nullable: tuple[str, ...] = ("note",)) -> dict:
    """Hanya field yang dikirim klien. Nilai null untuk field wajib dianggap 'tidak diubah'."""
    return {k: getattr(data, k) for k in data.model_fields_set
            if getattr(data, k) is not None or k in nullable}


def _http(e: TradeError) -> HTTPException:
    return HTTPException(e.status_code, e.message)


@router.get("/ledger", response_model=LedgerPageOut)
async def list_ledger(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    type: str | None = Query(default=None, pattern="^(BUY|SELL|DEPOSIT|WITHDRAW|DIVIDEND)$"),
    q: str | None = Query(default=None, max_length=30),
    tag: str | None = Query(default=None, max_length=20),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = await svc.ledger_items(db, user.id)
    if type:
        items = [i for i in items if i["type"] == type]
    if q:
        needle = q.strip().upper()
        items = [i for i in items if i["symbol"] and needle in i["symbol"].upper()]
    if tag:
        items = [i for i in items if tag.strip().lower() in i["tags"]]
    return LedgerPageOut(total=len(items), items=[LedgerItemOut(**i) for i in items[offset:offset + limit]])


@router.patch("/transactions/{trade_id}", response_model=LedgerItemOut)
async def patch_trade(
    trade_id: int, data: TradeUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        t = await svc.update_trade(db, user.id, trade_id, _changes(data))
    except TradeError as e:
        raise _http(e)
    return LedgerItemOut(**svc.tx_item(t, await svc.symbol_of(db, t.stock_id)))


@router.delete("/transactions/{trade_id}", response_model=OkOut)
async def remove_trade(trade_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        await svc.delete_item(db, user.id, "tx", trade_id)
    except TradeError as e:
        raise _http(e)
    return OkOut()


@router.patch("/cash/{cash_id}", response_model=LedgerItemOut)
async def patch_cash(
    cash_id: int, data: CashUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        c = await svc.update_cash(db, user.id, cash_id, _changes(data, ()))
    except TradeError as e:
        raise _http(e)
    return LedgerItemOut(**svc.cash_item(c))


@router.delete("/cash/{cash_id}", response_model=OkOut)
async def remove_cash(cash_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        await svc.delete_item(db, user.id, "cash", cash_id)
    except TradeError as e:
        raise _http(e)
    return OkOut()


@router.patch("/dividends/{div_id}", response_model=LedgerItemOut)
async def patch_dividend(
    div_id: int, data: DividendUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        d = await svc.update_dividend(db, user.id, div_id, _changes(data, ()))
    except TradeError as e:
        raise _http(e)
    return LedgerItemOut(**svc.div_item(d, await svc.symbol_of(db, d.stock_id)))


@router.delete("/dividends/{div_id}", response_model=OkOut)
async def remove_dividend(div_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        await svc.delete_item(db, user.id, "div", div_id)
    except TradeError as e:
        raise _http(e)
    return OkOut()
