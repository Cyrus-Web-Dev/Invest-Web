from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import get_db
from app.deps import get_current_user
from app.models import HistoricalPrice, Stock, User
from app.schemas import PriceBarOut, QuoteOut, SyncOut
from app.services.price_providers.base import PriceProvider
from app.services.price_providers.yahoo import get_provider
from app.services.prices import PriceUnavailable, get_quote, sync_stock_history

router = APIRouter(prefix="/stocks", tags=["prices"])


async def _stock_or_404(db: AsyncSession, stock_id: int) -> Stock:
    stock = await db.get(Stock, stock_id)
    if stock is None or not stock.is_active:
        raise HTTPException(404, "Saham tidak ditemukan")
    return stock


@router.get("/{stock_id}/prices", response_model=list[PriceBarOut])
async def price_history(
    stock_id: int,
    days: int = Query(default=365, ge=1, le=3650),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Data OHLCV harian dari database (untuk grafik lilin)."""
    stock = await _stock_or_404(db, stock_id)
    since = datetime.now(timezone.utc).date() - timedelta(days=days)
    rows = await db.scalars(
        select(HistoricalPrice)
        .where(HistoricalPrice.stock_id == stock.id, HistoricalPrice.trade_date >= since)
        .order_by(HistoricalPrice.trade_date)
    )
    return rows.all()


@router.get("/{stock_id}/quote", response_model=QuoteOut)
async def latest_quote(
    stock_id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    provider: PriceProvider = Depends(get_provider),
    _: User = Depends(get_current_user),
):
    stock = await _stock_or_404(db, stock_id)
    try:
        q = await get_quote(db, redis, provider, stock)
    except PriceUnavailable:
        raise HTTPException(503, "Harga belum tersedia untuk saham ini")
    return QuoteOut(stock_id=stock.id, symbol=q.symbol, price=q.price, as_of=q.as_of, source=q.source)


@router.post("/{stock_id}/sync", response_model=SyncOut)
async def sync_history(
    stock_id: int,
    days: int | None = Query(default=None, ge=30, le=3650, description="Backfill N hari terakhir"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    provider: PriceProvider = Depends(get_provider),
    _: User = Depends(get_current_user),
):
    """Tarik ulang data harga satu saham. Dibatasi jeda agar penyedia data tidak dibanjiri."""
    if settings.demo_mode:
        raise HTTPException(403, "Sync harga dinonaktifkan pada mode demo (data harga adalah simulasi)")
    stock = await _stock_or_404(db, stock_id)
    try:
        allowed = await redis.set(
            f"sync:cooldown:{stock.id}", "1", nx=True, ex=settings.sync_cooldown_seconds
        )
    except RedisError:
        raise HTTPException(503, "Layanan cache tidak tersedia, coba lagi nanti")
    if not allowed:
        raise HTTPException(429, "Sync baru saja dijalankan, coba lagi sebentar lagi")
    try:
        count = await sync_stock_history(db, provider, stock, days)
    except Exception:
        raise HTTPException(502, "Gagal mengambil data dari penyedia harga")
    return SyncOut(stock_id=stock.id, symbol=stock.symbol, upserted=count)
