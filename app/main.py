import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DataError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import redis_client
from app.db.session import engine, get_db
from app.routers import (
    alerts, analytics, auth, data_io, dividends, ledger, notifications, portfolio, prices, stocks,
    reports, targets, watchlist,
)
from app.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.scheduler_enabled and not settings.demo_mode:
        scheduler = build_scheduler()
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
    redoc_url=None,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(DataError)
async def data_error_handler(request: Request, exc: DataError):
    # Jaring pengaman: nilai di luar kapasitas kolom database -> 400, bukan 500.
    return JSONResponse(status_code=400, content={"detail": "Nilai di luar batas yang diizinkan"})


app.include_router(auth.router, prefix="/api/v1")
app.include_router(stocks.router, prefix="/api/v1")
app.include_router(prices.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(dividends.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(data_io.router, prefix="/api/v1")
app.include_router(ledger.router, prefix="/api/v1")
app.include_router(targets.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "app": settings.app_name}
