"""Tambah bertanggal mundur, ubah, dan hapus catatan buku besar. Setiap perubahan divalidasi ulang
terhadap SELURUH riwayat secara kronologis, dalam satu transaksi dengan baris user terkunci."""
from contextlib import asynccontextmanager
from datetime import datetime, time, timezone
from types import SimpleNamespace as NS

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CashFlow, Dividend, Stock, Transaction
from app.services.tags import join_tags, split_tags
from app.services.ledger_rules import LedgerRuleError, at_for, check_change, check_sell_fee
from app.services.trading import TradeError, _lock_user

UTC = timezone.utc


@asynccontextmanager
async def _guard(db: AsyncSession):
    try:
        yield
    except LedgerRuleError as e:
        await db.rollback()
        raise TradeError(e.message, e.status_code) from e
    except Exception:
        await db.rollback()
        raise


async def _load(db: AsyncSession, user_id: int):
    txs = (await db.scalars(select(Transaction).where(Transaction.user_id == user_id)
                            .order_by(Transaction.executed_at, Transaction.id))).all()
    cfs = (await db.scalars(select(CashFlow).where(CashFlow.user_id == user_id)
                            .order_by(CashFlow.occurred_at, CashFlow.id))).all()
    divs = (await db.scalars(select(Dividend).where(Dividend.user_id == user_id)
                             .order_by(Dividend.paid_on, Dividend.id))).all()
    return list(txs), list(cfs), list(divs)


def _tx(t, **over):
    d = dict(id=t.id, type=t.type, quantity=t.quantity, price=t.price, fee=t.fee,
             executed_at=t.executed_at, stock_id=t.stock_id)
    d.update(over)
    return NS(**d)


def _cf(c, **over):
    d = dict(id=c.id, type=c.type, amount=c.amount, occurred_at=c.occurred_at)
    d.update(over)
    return NS(**d)


def _dv(v, **over):
    d = dict(id=v.id, amount=v.amount, paid_on=v.paid_on, stock_id=v.stock_id)
    d.update(over)
    return NS(**d)


async def _require_stock(db: AsyncSession, stock_id: int) -> Stock:
    stock = await db.get(Stock, stock_id)
    if stock is None or not stock.is_active:
        raise TradeError("Saham tidak ditemukan atau tidak aktif", 404)
    if stock.kind != "STOCK":
        raise TradeError("Indeks tidak dapat diperdagangkan")
    return stock


async def symbol_of(db: AsyncSession, stock_id: int | None) -> str | None:
    if stock_id is None:
        return None
    return await db.scalar(select(Stock.symbol).where(Stock.id == stock_id))


# ---------- bentuk item untuk respons ----------
def tx_item(t: Transaction, symbol: str | None) -> dict:
    return dict(kind="TRADE", id=t.id, at=t.executed_at, day=t.executed_at.astimezone(UTC).date(),
                type=t.type, stock_id=t.stock_id, symbol=symbol, quantity=t.quantity, price=t.price,
                fee=t.fee, amount=None, note=t.note, tags=split_tags(t.tags))


def cash_item(c: CashFlow) -> dict:
    return dict(kind="CASH", id=c.id, at=c.occurred_at, day=c.occurred_at.astimezone(UTC).date(),
                type=c.type, stock_id=None, symbol=None, quantity=None, price=None, fee=None,
                amount=c.amount, note=None, tags=[])


def div_item(d: Dividend, symbol: str | None) -> dict:
    at = datetime.combine(d.paid_on, time(12, 0), tzinfo=UTC)
    return dict(kind="DIVIDEND", id=d.id, at=at, day=d.paid_on, type="DIVIDEND", stock_id=d.stock_id,
                symbol=symbol, quantity=None, price=None, fee=None, amount=d.amount, note=None, tags=[])


async def ledger_items(db: AsyncSession, user_id: int) -> list[dict]:
    txs, cfs, divs = await _load(db, user_id)
    symbols = dict((await db.execute(select(Stock.id, Stock.symbol))).all())
    items = [tx_item(t, symbols.get(t.stock_id)) for t in txs]
    items += [cash_item(c) for c in cfs]
    items += [div_item(d, symbols.get(d.stock_id)) for d in divs]
    items.sort(key=lambda x: (x["at"], x["id"]), reverse=True)
    return items


# ---------- tambah bertanggal mundur ----------
async def add_trade_dated(db: AsyncSession, user_id: int, data) -> Transaction:
    async with _guard(db):
        at = at_for(data.date, None, datetime.now(UTC))
        await _require_stock(db, data.stock_id)
        check_sell_fee(data.type, data.quantity, data.price, data.fee)
        user = await _lock_user(db, user_id)
        txs, cfs, divs = await _load(db, user_id)
        new_tx = NS(id=-1, type=data.type, quantity=data.quantity, price=data.price, fee=data.fee,
                    executed_at=at, stock_id=data.stock_id)
        balance = check_change((txs, cfs, divs), ([_tx(t) for t in txs] + [new_tx], cfs, divs),
                               user.cash_balance, ("tx", -1))
        tx = Transaction(user_id=user_id, stock_id=data.stock_id, type=data.type, quantity=data.quantity,
                         price=data.price, fee=data.fee, executed_at=at, note=data.note,
                         tags=join_tags(data.tags))
        db.add(tx)
        user.cash_balance = balance
        await db.commit()
    return tx


async def add_cash_dated(db: AsyncSession, user_id: int, flow_type: str, amount, day):
    async with _guard(db):
        at = at_for(day, None, datetime.now(UTC))
        user = await _lock_user(db, user_id)
        txs, cfs, divs = await _load(db, user_id)
        new_cf = NS(id=-1, type=flow_type, amount=amount, occurred_at=at)
        balance = check_change((txs, cfs, divs), (txs, [_cf(c) for c in cfs] + [new_cf], divs),
                               user.cash_balance, ("cash", -1))
        cf = CashFlow(user_id=user_id, type=flow_type, amount=amount, occurred_at=at)
        db.add(cf)
        user.cash_balance = balance
        await db.commit()
    return user


# ---------- ubah ----------
async def update_trade(db: AsyncSession, user_id: int, trade_id: int, ch: dict) -> Transaction:
    async with _guard(db):
        user = await _lock_user(db, user_id)
        txs, cfs, divs = await _load(db, user_id)
        orig = next((t for t in txs if t.id == trade_id), None)
        if orig is None:
            raise TradeError("Transaksi tidak ditemukan", 404)
        kind = ch.get("type", orig.type)
        stock_id = ch.get("stock_id", orig.stock_id)
        qty, price, fee = ch.get("quantity", orig.quantity), ch.get("price", orig.price), ch.get("fee", orig.fee)
        note = ch["note"] if "note" in ch else orig.note
        tags = join_tags(ch["tags"]) if "tags" in ch else orig.tags
        at = at_for(ch["date"], orig.executed_at, datetime.now(UTC)) if "date" in ch else orig.executed_at
        if stock_id != orig.stock_id:
            await _require_stock(db, stock_id)
        check_sell_fee(kind, qty, price, fee)
        new_txs = [_tx(t) if t.id != trade_id else
                   _tx(t, type=kind, stock_id=stock_id, quantity=qty, price=price, fee=fee, executed_at=at)
                   for t in txs]
        balance = check_change((txs, cfs, divs), (new_txs, cfs, divs), user.cash_balance, ("tx", trade_id))
        orig.type, orig.stock_id, orig.quantity, orig.price, orig.fee = kind, stock_id, qty, price, fee
        orig.executed_at, orig.note, orig.tags = at, note, tags
        user.cash_balance = balance
        await db.commit()
    return orig


async def update_cash(db: AsyncSession, user_id: int, cash_id: int, ch: dict) -> CashFlow:
    async with _guard(db):
        user = await _lock_user(db, user_id)
        txs, cfs, divs = await _load(db, user_id)
        orig = next((c for c in cfs if c.id == cash_id), None)
        if orig is None:
            raise TradeError("Catatan kas tidak ditemukan", 404)
        kind, amount = ch.get("type", orig.type), ch.get("amount", orig.amount)
        at = at_for(ch["date"], orig.occurred_at, datetime.now(UTC)) if "date" in ch else orig.occurred_at
        new_cfs = [_cf(c) if c.id != cash_id else _cf(c, type=kind, amount=amount, occurred_at=at) for c in cfs]
        balance = check_change((txs, cfs, divs), (txs, new_cfs, divs), user.cash_balance, ("cash", cash_id))
        orig.type, orig.amount, orig.occurred_at = kind, amount, at
        user.cash_balance = balance
        await db.commit()
    return orig


async def update_dividend(db: AsyncSession, user_id: int, div_id: int, ch: dict) -> Dividend:
    async with _guard(db):
        user = await _lock_user(db, user_id)
        txs, cfs, divs = await _load(db, user_id)
        orig = next((d for d in divs if d.id == div_id), None)
        if orig is None:
            raise TradeError("Dividen tidak ditemukan", 404)
        stock_id, amount = ch.get("stock_id", orig.stock_id), ch.get("amount", orig.amount)
        paid_on = orig.paid_on
        if "paid_on" in ch:
            at_for(ch["paid_on"], None, datetime.now(UTC))  # hanya memvalidasi: tidak boleh di masa depan
            paid_on = ch["paid_on"]
        if stock_id != orig.stock_id and await db.get(Stock, stock_id) is None:
            raise TradeError("Saham tidak ditemukan", 404)
        new_divs = [_dv(d) if d.id != div_id else _dv(d, stock_id=stock_id, amount=amount, paid_on=paid_on)
                    for d in divs]
        balance = check_change((txs, cfs, divs), (txs, cfs, new_divs), user.cash_balance, ("div", div_id))
        orig.stock_id, orig.amount, orig.paid_on = stock_id, amount, paid_on
        user.cash_balance = balance
        await db.commit()
    return orig


# ---------- hapus ----------
async def delete_item(db: AsyncSession, user_id: int, kind: str, item_id: int) -> None:
    """kind: 'tx' | 'cash' | 'div'."""
    async with _guard(db):
        user = await _lock_user(db, user_id)
        txs, cfs, divs = await _load(db, user_id)
        if kind == "tx":
            target = next((t for t in txs if t.id == item_id), None)
            new = ([t for t in txs if t.id != item_id], cfs, divs)
        elif kind == "cash":
            target = next((c for c in cfs if c.id == item_id), None)
            new = (txs, [c for c in cfs if c.id != item_id], divs)
        else:
            target = next((d for d in divs if d.id == item_id), None)
            new = (txs, cfs, [d for d in divs if d.id != item_id])
        if target is None:
            raise TradeError("Data tidak ditemukan", 404)
        balance = check_change((txs, cfs, divs), new, user.cash_balance, None)
        await db.delete(target)
        user.cash_balance = balance
        await db.commit()
