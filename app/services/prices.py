import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import HistoricalPrice, Stock
from app.services.price_providers.base import PriceProvider, decode_quote, encode_quote

log = logging.getLogger("stockfolio.prices")

CHUNK = 500         # 500 baris x 7 kolom, jauh di bawah batas parameter asyncpg
OVERLAP_DAYS = 3    # ambil ulang beberapa hari terakhir (data hari terakhir bisa direvisi)


class PriceUnavailable(Exception):
    pass


@dataclass
class Quote:
    symbol: str
    price: Decimal
    as_of: date
    source: str  # "cache" | "live" | "db_fallback"


async def sync_stock_history(
    db: AsyncSession, provider: PriceProvider, stock: Stock, days: int | None = None
) -> int:
    """Tarik harga harian lalu upsert (idempoten: aman dijalankan berulang). Return jumlah baris."""
    last = await db.scalar(
        select(func.max(HistoricalPrice.trade_date)).where(HistoricalPrice.stock_id == stock.id)
    )
    today = datetime.now(timezone.utc).date()
    if days:  # backfill eksplisit (idempoten: upsert menimpa data yang sama)
        start = today - timedelta(days=days)
    elif last:
        start = last - timedelta(days=OVERLAP_DAYS)
    else:
        start = today - timedelta(days=settings.history_backfill_days)
    bars = await provider.fetch_history(stock.symbol, start, today + timedelta(days=1))
    if not bars:
        return 0
    rows = [
        {
            "stock_id": stock.id, "trade_date": b.trade_date, "open": b.open,
            "high": b.high, "low": b.low, "close": b.close, "volume": b.volume,
        }
        for b in bars
    ]
    try:
        for i in range(0, len(rows), CHUNK):
            stmt = pg_insert(HistoricalPrice).values(rows[i : i + CHUNK])
            stmt = stmt.on_conflict_do_update(
                index_elements=["stock_id", "trade_date"],
                set_={c: stmt.excluded[c] for c in ("open", "high", "low", "close", "volume")},
            )
            await db.execute(stmt)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return len(rows)


async def get_quote(db: AsyncSession, redis: Redis, provider: PriceProvider, stock: Stock) -> Quote:
    """Urutan: cache Redis -> penyedia (live) -> harga penutupan terakhir di DB."""
    key = f"quote:{stock.symbol}"
    try:
        cached = await redis.get(key)
    except RedisError:
        log.warning("Redis tidak tersedia saat membaca cache %s", key)
        cached = None
    if cached:
        try:
            price, as_of = decode_quote(cached)
            return Quote(stock.symbol, price, as_of, "cache")
        except ValueError:
            log.warning("Cache %s rusak, diabaikan", key)

    bar = None
    try:
        bar = await provider.fetch_latest(stock.symbol)
    except Exception:
        log.warning("Gagal mengambil harga live %s", stock.symbol, exc_info=True)
    if bar is not None:
        try:
            await redis.set(
                key, encode_quote(bar.close, bar.trade_date), ex=settings.price_cache_ttl_seconds
            )
        except RedisError:
            log.warning("Redis tidak tersedia saat menulis cache %s", key)
        return Quote(stock.symbol, bar.close, bar.trade_date, "live")

    row = (
        await db.scalars(
            select(HistoricalPrice)
            .where(HistoricalPrice.stock_id == stock.id)
            .order_by(HistoricalPrice.trade_date.desc())
            .limit(1)
        )
    ).first()
    if row is not None:
        return Quote(stock.symbol, row.close, row.trade_date, "db_fallback")
    raise PriceUnavailable(stock.symbol)
