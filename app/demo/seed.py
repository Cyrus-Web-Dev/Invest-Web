"""Penulis data demo ke database. Hanya untuk stack demo (DEMO_MODE=true)."""
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.demo.generator import UNIVERSE, WATCH_ONLY, generate_plan, round_tick
from app.models import (
    CashFlow, Dividend, HistoricalPrice, Notification, PositionTarget, PriceAlert, Stock, Transaction,
    User, Watchlist,
)
from app.seed.catalog import ensure_benchmarks, ensure_catalog
from app.services.alerts import alert_message
from app.services.metrics import money
from app.services.tags import join_tags
from app.services.targets import target_message

UTC = timezone.utc
DEMO_EMAIL = "demo@stockfolio.app"


def _at(day, seq: int) -> datetime:
    """Tengah hari UTC + detik urutan: urutan antar-kejadian pada hari yang sama terjaga."""
    return datetime.combine(day, time(12, 0), tzinfo=UTC) + timedelta(seconds=seq)


async def seed_demo(db: AsyncSession, email: str, password: str, *, reset: bool = False,
                    seed: int = 2026, today=None) -> dict:
    today = today or datetime.now(UTC).date()
    email = email.strip().lower()

    await ensure_catalog(db)
    await ensure_benchmarks(db)

    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        if not existing.is_demo:
            raise RuntimeError(f"{email} adalah akun biasa (bukan akun demo). Demi keamanan, tidak akan dihapus atau ditimpa.")
        if not reset:
            raise RuntimeError(f"Akun demo {email} sudah ada. Tambahkan --reset untuk membuat ulang.")
        await db.delete(existing)
        await db.flush()

    plan = generate_plan(today, seed)
    stock_ids = {sym: sid for sid, sym in (await db.execute(
        select(Stock.id, Stock.symbol).where(Stock.symbol.in_(set(plan.prices))))).all()}
    missing = set(plan.prices) - set(stock_ids)
    if missing:
        raise RuntimeError(f"Simbol tidak ada di katalog: {sorted(missing)}")

    # --- harga simulasi (upsert) ---
    rows = [dict(stock_id=stock_ids[sym], trade_date=b.trade_date, open=b.open, high=b.high, low=b.low,
                 close=b.close, volume=b.volume) for sym, bars in plan.prices.items() for b in bars]
    for i in range(0, len(rows), 500):
        stmt = pg_insert(HistoricalPrice).values(rows[i:i + 500])
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "trade_date"],
            set_={c: stmt.excluded[c] for c in ("open", "high", "low", "close", "volume")},
        )
        await db.execute(stmt)

    # --- akun & buku besar ---
    user = User(email=email, hashed_password=hash_password(password), full_name="Demo Investor",
                is_demo=True, cash_balance=money(plan.final_cash))
    db.add(user)
    await db.flush()
    uid = user.id
    for t in plan.trades:
        db.add(Transaction(user_id=uid, stock_id=stock_ids[t.symbol], type=t.type, quantity=Decimal(t.qty),
                           price=t.price, fee=t.fee, executed_at=_at(t.day, t.seq), note=t.note,
                           tags=join_tags(list(t.tags))))
    for c in plan.cashflows:
        db.add(CashFlow(user_id=uid, type=c.type, amount=c.amount, occurred_at=_at(c.day, c.seq)))
    for d in plan.dividends:
        db.add(Dividend(user_id=uid, stock_id=stock_ids[d.symbol], amount=d.amount, paid_on=d.day))

    # --- pantauan, alert, target, notifikasi ---
    last = {sym: bars[-1].close for sym, bars in plan.prices.items()}
    now = datetime.now(UTC)
    for sym in list(WATCH_ONLY) + ["ICBP.JK", "KLBF.JK"]:
        db.add(Watchlist(user_id=uid, stock_id=stock_ids[sym]))
    notes: list[Notification] = []

    bbca = round_tick(float(last["BBCA.JK"]) * 0.95)
    antm = round_tick(float(last["ANTM.JK"]) * 1.10)
    db.add(PriceAlert(user_id=uid, stock_id=stock_ids["BBCA.JK"], direction="BELOW", target_price=bbca, created_at=now - timedelta(days=9)))
    db.add(PriceAlert(user_id=uid, stock_id=stock_ids["ANTM.JK"], direction="ABOVE", target_price=antm, created_at=now - timedelta(days=9)))
    tl_target = round_tick(float(last["TLKM.JK"]) * 1.02)
    db.add(PriceAlert(user_id=uid, stock_id=stock_ids["TLKM.JK"], direction="ABOVE", target_price=tl_target, is_active=False,
                      created_at=now - timedelta(days=30), triggered_at=now - timedelta(days=12), triggered_price=tl_target))
    title, msg = alert_message("TLKM.JK", "ABOVE", tl_target, tl_target)
    notes.append(Notification(user_id=uid, kind="ALERT", title=title, message=msg, created_at=now - timedelta(days=12), read_at=now - timedelta(days=11)))

    held = sorted(plan.holdings, key=lambda s: float(last[s] / plan.holdings[s][1]), reverse=True)
    for rank, sym in enumerate(held[:3]):
        avg = plan.holdings[sym][1]
        if rank == 0:       # contoh target yang sudah tercapai
            target = round_tick(float(avg) * 1.06)
            db.add(PositionTarget(user_id=uid, stock_id=stock_ids[sym], target_price=target,
                                  stop_price=round_tick(float(avg) * 0.90), note="Target awal: +6% dari harga rata-rata",
                                  target_hit_at=now - timedelta(days=5)))
            t_title, t_msg = target_message(sym, target, last[sym])
            notes.append(Notification(user_id=uid, kind="TARGET", title=t_title, message=t_msg, created_at=now - timedelta(days=5)))
        else:
            db.add(PositionTarget(user_id=uid, stock_id=stock_ids[sym], target_price=round_tick(float(avg) * 1.25),
                                  stop_price=round_tick(float(avg) * 0.90), note="Target +25%, stop loss -10% dari harga rata-rata"))
    notes.append(Notification(user_id=uid, kind="INFO", title="Selamat datang di Stockfolio (DEMO)",
                              message="Ini akun demo dengan data simulasi untuk peragaan aplikasi.", created_at=now - timedelta(days=1)))
    for n in notes:
        db.add(n)

    await db.commit()
    deposits = sum((c.amount for c in plan.cashflows if c.type == "DEPOSIT"), Decimal(0))
    return dict(email=email, trades=len(plan.trades), cashflows=len(plan.cashflows), dividends=len(plan.dividends),
                price_rows=len(rows), deposits=deposits, final_cash=money(plan.final_cash), holdings=len(plan.holdings),
                start=plan.days[0], end=plan.days[-1])
