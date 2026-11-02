from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CashFlow, Dividend, Stock, Transaction, User

CENT = Decimal("0.01")


class TradeError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


async def _lock_user(db: AsyncSession, user_id: int) -> User:
    """Kunci baris user (SELECT ... FOR UPDATE). populate_existing memaksa nilai
    segar dari DB, bukan salinan lama di memori sesi."""
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def _held_quantity(db: AsyncSession, user_id: int, stock_id: int) -> Decimal:
    signed = case((Transaction.type == "BUY", Transaction.quantity), else_=-Transaction.quantity)
    result = await db.execute(
        select(func.coalesce(func.sum(signed), 0)).where(
            Transaction.user_id == user_id, Transaction.stock_id == stock_id
        )
    )
    return Decimal(result.scalar_one())


async def apply_cash_flow(db: AsyncSession, user_id: int, flow_type: str, amount: Decimal) -> User:
    try:
        user = await _lock_user(db, user_id)
        if flow_type == "DEPOSIT":
            user.cash_balance += amount
        else:
            if user.cash_balance < amount:
                raise TradeError("Saldo kas tidak cukup untuk penarikan")
            user.cash_balance -= amount
        db.add(CashFlow(user_id=user_id, type=flow_type, amount=amount,
                        occurred_at=datetime.now(timezone.utc)))
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(user)
    return user


async def execute_trade(
    db: AsyncSession, user_id: int, stock_id: int, trade_type: str,
    quantity: Decimal, price: Decimal, fee: Decimal, note: str | None, tags: str | None = None,
) -> Transaction:
    stock = await db.get(Stock, stock_id)
    if stock is None or not stock.is_active:
        raise TradeError("Saham tidak ditemukan atau tidak aktif", 404)
    if stock.kind != "STOCK":
        raise TradeError("Indeks tidak dapat diperdagangkan")
    gross = quantity * price
    try:
        user = await _lock_user(db, user_id)
        if trade_type == "BUY":
            total = money(gross + fee)
            if user.cash_balance < total:
                raise TradeError("Saldo kas tidak cukup")
            user.cash_balance -= total
        else:
            if quantity > await _held_quantity(db, user_id, stock_id):
                raise TradeError("Jumlah jual melebihi kepemilikan")
            proceeds = money(gross - fee)
            if proceeds < 0:
                raise TradeError("Fee melebihi nilai transaksi")
            user.cash_balance += proceeds
        tx = Transaction(
            user_id=user_id, stock_id=stock_id, type=trade_type, quantity=quantity,
            price=price, fee=fee, executed_at=datetime.now(timezone.utc), note=note, tags=tags,
        )
        db.add(tx)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return tx


async def record_dividend(
    db: AsyncSession, user_id: int, stock_id: int, amount: Decimal, paid_on
) -> Dividend:
    """Catat dividen bersih (setelah pajak) yang sudah diterima; otomatis menambah kas."""
    if await db.get(Stock, stock_id) is None:
        raise TradeError("Saham tidak ditemukan", 404)
    if paid_on > datetime.now(timezone.utc).date():
        raise TradeError("Tanggal dividen tidak boleh di masa depan")
    try:
        user = await _lock_user(db, user_id)
        user.cash_balance += amount
        div = Dividend(user_id=user_id, stock_id=stock_id, amount=amount, paid_on=paid_on)
        db.add(div)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return div
