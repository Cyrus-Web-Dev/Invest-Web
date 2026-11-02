"""Penyedia harga via yfinance (scraper tidak resmi: bisa berubah/rusak sewaktu-waktu)."""
import asyncio
from datetime import date

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.price_providers.base import PriceBar, PriceProvider, rows_to_bars

FETCH_TIMEOUT = 25  # detik per percobaan


def _fetch_rows(symbol: str, **kwargs) -> list[tuple]:
    """Sinkron & memblokir -> HARUS dipanggil lewat thread. yfinance diimpor di sini
    agar aplikasi (dan tes) tetap bisa dimuat tanpa yfinance."""
    import yfinance as yf

    df = yf.Ticker(symbol).history(auto_adjust=False, actions=False, **kwargs)
    if df is None or df.empty:
        return []
    return [
        (idx.date(), row["Open"], row["High"], row["Low"], row["Close"], row["Volume"])
        for idx, row in df.iterrows()
    ]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
async def _download(symbol: str, **kwargs) -> list[tuple]:
    return await asyncio.wait_for(
        asyncio.to_thread(_fetch_rows, symbol, **kwargs), timeout=FETCH_TIMEOUT
    )


class YahooProvider:
    async def fetch_history(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        rows = await _download(symbol, start=start.isoformat(), end=end.isoformat())
        return rows_to_bars(rows)

    async def fetch_latest(self, symbol: str) -> PriceBar | None:
        bars = rows_to_bars(await _download(symbol, period="5d"))
        return bars[-1] if bars else None


_provider = YahooProvider()


class OfflineProvider:
    """Mode demo: tidak pernah menghubungi internet; harga berasal dari data simulasi di database."""

    async def fetch_history(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        return []

    async def fetch_latest(self, symbol: str) -> PriceBar | None:
        return None


_offline = OfflineProvider()


def get_provider() -> PriceProvider:
    return _offline if settings.demo_mode else _provider
