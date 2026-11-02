from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ratelimit import add_hit, is_blocked
from app.core.redis import get_redis
from app.db.session import get_db
from app.deps import get_current_user
from app.models import Stock, User
from app.seed.catalog import ensure_catalog
from app.schemas import StockIn, StockOut
from app.services.price_providers.base import PriceProvider
from app.services.price_providers.yahoo import get_provider

router = APIRouter(prefix="/stocks", tags=["stocks"])
USER_ADDS_PER_DAY = 10


@router.get("", response_model=list[StockOut])
async def list_stocks(
    q: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Stock).where(Stock.is_active.is_(True), Stock.kind == "STOCK").order_by(Stock.symbol)
    if q:
        stmt = stmt.where(Stock.symbol.ilike(f"%{q}%") | Stock.name.ilike(f"%{q}%"))
    rows = (await db.scalars(stmt.limit(limit).offset(offset))).all()
    if not rows and not q and offset == 0 and await ensure_catalog(db) > 0:
        # Tabel masih kosong (pemakaian pertama): isi katalog awal lalu ambil ulang.
        rows = (await db.scalars(stmt.limit(limit).offset(offset))).all()
    return rows


@router.post("", response_model=StockOut, status_code=201)
async def create_stock(
    data: StockIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
    provider: PriceProvider = Depends(get_provider),
):
    """Admin: bebas. User biasa: hanya saham (bukan indeks), simbol divalidasi ke penyedia harga,
    dengan pembatasan jumlah penambahan per hari."""
    if data.kind != "STOCK" and not user.is_admin:
        raise HTTPException(403, "Hanya admin yang boleh menambah indeks pembanding")
    symbol = data.symbol.upper()
    if await db.scalar(select(Stock.id).where(Stock.symbol == symbol)):
        raise HTTPException(409, "Simbol saham sudah ada")
    if not user.is_admin:
        if settings.demo_mode:
            raise HTTPException(403, "Penambahan saham dinonaktifkan pada mode demo")
        key = f"addstock:{user.id}"
        if await is_blocked(redis, key, USER_ADDS_PER_DAY):
            raise HTTPException(429, f"Batas {USER_ADDS_PER_DAY} penambahan saham per hari tercapai. Coba lagi besok.")
        await add_hit(redis, key, 86400)   # setiap percobaan dihitung, termasuk yang gagal validasi
        try:
            bar = await provider.fetch_latest(symbol)
        except Exception:
            raise HTTPException(502, "Gagal menghubungi penyedia harga untuk memvalidasi simbol. Coba lagi nanti.")
        if bar is None:
            raise HTTPException(422, "Simbol tidak ditemukan di penyedia harga. Periksa penulisan (saham IDX berakhiran .JK, mis. BBCA.JK).")
    stock = Stock(symbol=symbol, name=data.name.strip(), exchange=data.exchange.upper(),
                  currency=data.currency.upper(), sector=data.sector, kind=data.kind)
    db.add(stock)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Simbol saham sudah ada")
    await db.refresh(stock)
    return stock


@router.get("/{stock_id}", response_model=StockOut)
async def get_stock(
    stock_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
):
    stock = await db.get(Stock, stock_id)
    if stock is None:
        raise HTTPException(404, "Saham tidak ditemukan")
    return stock
