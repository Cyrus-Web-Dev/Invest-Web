import asyncio
import logging

from sqlalchemy import and_, or_, select

from app.core.redis import redis_client
from app.db.session import SessionLocal
from app.models import PositionTarget, PriceAlert, Stock
from app.services.alert_engine import evaluate_alerts, evaluate_targets
from app.services.price_providers.yahoo import get_provider
from app.services.prices import PriceUnavailable, get_quote, sync_stock_history

log = logging.getLogger("stockfolio.jobs")


async def sync_prices_job(idx_only: bool) -> None:
    """Sync semua saham aktif satu per satu. Satu saham gagal tidak menghentikan yang lain."""
    provider = get_provider()
    cond = Stock.exchange == "IDX" if idx_only else Stock.exchange != "IDX"
    async with SessionLocal() as db:
        stocks = (
            await db.scalars(select(Stock).where(Stock.is_active.is_(True), cond))
        ).all()
    ok = failed = 0
    for stock in stocks:
        try:
            async with SessionLocal() as db:
                await sync_stock_history(db, provider, stock)
            ok += 1
        except Exception:
            failed += 1
            log.exception("Sync harga gagal untuk %s", stock.symbol)
        await asyncio.sleep(1)  # sopan terhadap penyedia data
    log.info("Sync harga selesai (idx_only=%s): %d berhasil, %d gagal", idx_only, ok, failed)


async def check_alerts_job() -> None:
    """Periksa alert harga aktif. Hanya saham yang punya alert aktif yang diambil harganya
    (memakai cache Redis, jadi tidak membebani penyedia data)."""
    provider = get_provider()
    async with SessionLocal() as db:
        alert_ids = select(PriceAlert.stock_id).where(PriceAlert.is_active.is_(True))
        target_ids = select(PositionTarget.stock_id).where(or_(
            and_(PositionTarget.target_price.is_not(None), PositionTarget.target_hit_at.is_(None)),
            and_(PositionTarget.stop_price.is_not(None), PositionTarget.stop_hit_at.is_(None)),
        ))
        stocks = (await db.scalars(
            select(Stock).where(or_(Stock.id.in_(alert_ids), Stock.id.in_(target_ids)))
        )).all()
    fired = 0
    for stock in stocks:
        try:
            async with SessionLocal() as db:
                quote = await get_quote(db, redis_client, provider, stock)
                fired += await evaluate_alerts(db, stock, quote.price)
                fired += await evaluate_targets(db, stock, quote.price)
        except PriceUnavailable:
            continue
        except Exception:
            log.exception("Pemeriksaan alert gagal untuk %s", stock.symbol)
        await asyncio.sleep(1)
    if stocks:
        log.info("Pemeriksaan alert selesai: %d saham diperiksa, %d alert terpicu", len(stocks), fired)
