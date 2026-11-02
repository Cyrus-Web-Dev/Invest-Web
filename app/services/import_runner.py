from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CashFlow, Dividend, ImportBatch, Stock, Transaction, User
from app.services.csv_import import (
    ImportRow, RowError, existing_sim_events, new_sim_events, row_timestamp, simulate,
)
from app.services.metrics import ZERO, money
from app.services.trading import _lock_user


@dataclass
class ImportReport:
    ok: bool = False
    committed: bool = False
    duplicate: bool = False
    total_rows: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    date_from: date | None = None
    date_to: date | None = None
    cash_effect: Decimal = ZERO
    resulting_cash: Decimal | None = None
    errors: list[RowError] = field(default_factory=list)


async def run_import(
    db: AsyncSession, user_id: int, rows: list[ImportRow], file_hash: str,
    filename: str | None, dry_run: bool, force: bool = False,
) -> ImportReport:
    rep = ImportReport(
        total_rows=len(rows), counts=dict(Counter(r.kind for r in rows)),
        date_from=min(r.day for r in rows), date_to=max(r.day for r in rows),
    )

    # 1) simbol harus ada di katalog
    symbols = {r.symbol for r in rows if r.symbol}
    stock_ids: dict[str, int] = {}
    if symbols:
        res = await db.execute(
            select(Stock.id, Stock.symbol).where(Stock.symbol.in_(symbols), Stock.is_active.is_(True), Stock.kind == "STOCK")
        )
        stock_ids = {sym: sid for sid, sym in res.all()}
    for r in rows:
        if r.symbol and r.symbol not in stock_ids:
            rep.errors.append(RowError(r.line, f"Simbol {r.symbol} tidak ada di katalog saham (minta admin menambahkannya)"))
    if rep.errors:
        return rep

    try:
        # 2) kunci user saat impor sungguhan (membaca & menulis buku besar secara konsisten)
        user = await db.get(User, user_id) if dry_run else await _lock_user(db, user_id)
        if user is None:
            rep.errors.append(RowError(None, "Akun tidak ditemukan"))
            return rep
        rep.duplicate = bool(await db.scalar(
            select(ImportBatch.id).where(ImportBatch.user_id == user_id, ImportBatch.file_sha256 == file_hash)
        ))
        if rep.duplicate and not force:
            rep.errors.append(RowError(None, "File yang sama persis sudah pernah diimpor. Mengimpor ulang akan menggandakan data jika data lamanya masih ada."))
            return rep

        # 3) simulasi buku besar gabungan (data lama + data impor) secara kronologis
        new_events, row_errors = new_sim_events(rows, stock_ids)
        rep.errors.extend(row_errors)
        txs = (await db.scalars(select(Transaction).where(Transaction.user_id == user_id))).all()
        cfs = (await db.scalars(select(CashFlow).where(CashFlow.user_id == user_id))).all()
        divs = (await db.scalars(select(Dividend).where(Dividend.user_id == user_id))).all()
        sim_errors, final_cash = simulate(existing_sim_events(txs, cfs, divs) + new_events)
        rep.errors.extend(sim_errors)

        net = sum((e.cash_delta for e in new_events), ZERO)
        rep.cash_effect = net
        rep.resulting_cash = user.cash_balance + net
        if not rep.errors and money(final_cash) != money(rep.resulting_cash):
            rep.errors.append(RowError(None, "Buku besar akun tidak cocok dengan saldo kas saat ini; impor dibatalkan demi keamanan data"))
        if rep.errors or dry_run:
            rep.ok = not rep.errors
            return rep

        # 4) tulis semuanya (atomik)
        for i, r in enumerate(rows):
            at = row_timestamp(r.day, i)
            if r.kind in ("BUY", "SELL"):
                db.add(Transaction(
                    user_id=user_id, stock_id=stock_ids[r.symbol], type=r.kind, quantity=r.quantity,
                    price=r.price, fee=r.fee, executed_at=at, note=r.note, tags=r.tags,
                ))
            elif r.kind in ("DEPOSIT", "WITHDRAW"):
                db.add(CashFlow(user_id=user_id, type=r.kind, amount=r.amount, occurred_at=at))
            else:
                db.add(Dividend(user_id=user_id, stock_id=stock_ids[r.symbol], amount=r.amount, paid_on=r.day))
        user.cash_balance = user.cash_balance + net
        if rep.duplicate:  # impor ulang yang disengaja: ganti jejak lama
            await db.execute(delete(ImportBatch).where(
                ImportBatch.user_id == user_id, ImportBatch.file_sha256 == file_hash))
        db.add(ImportBatch(user_id=user_id, file_sha256=file_hash, filename=(filename or "")[:255] or None,
                           row_count=len(rows)))
        await db.commit()
        rep.ok = rep.committed = True
        return rep
    except IntegrityError:  # dua impor file sama bersamaan
        await db.rollback()
        rep.duplicate = True
        rep.errors.append(RowError(None, "File yang sama sedang/sudah diimpor"))
        return rep
    except Exception:
        await db.rollback()
        raise
    finally:
        if dry_run:
            await db.rollback()  # lepas transaksi baca
