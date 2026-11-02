from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Stock
from app.seed.data import BENCHMARKS, CATALOG


async def ensure_catalog(db: AsyncSession) -> int:
    """Isi katalog awal. Idempoten: simbol yang sudah ada dilewati (tidak ditimpa).
    Return jumlah saham yang benar-benar ditambahkan."""
    try:
        res = await db.execute(
            pg_insert(Stock).values(CATALOG).on_conflict_do_nothing(index_elements=["symbol"])
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return res.rowcount or 0


async def ensure_benchmarks(db: AsyncSession) -> int:
    """Pastikan indeks pembanding (IHSG, S&P 500) ada. Idempoten."""
    try:
        res = await db.execute(
            pg_insert(Stock).values(BENCHMARKS).on_conflict_do_nothing(index_elements=["symbol"])
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return res.rowcount or 0
