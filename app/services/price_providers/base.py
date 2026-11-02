import json
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Protocol


@dataclass(frozen=True)
class PriceBar:
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class PriceProvider(Protocol):
    """Kontrak penyedia harga. Ganti sumber data cukup dengan class baru yang memenuhi ini."""

    async def fetch_history(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        """Bar harian dari start (inklusif) sampai end (eksklusif), urut tanggal naik."""
        ...

    async def fetch_latest(self, symbol: str) -> PriceBar | None:
        """Bar harian terbaru, atau None jika simbol tidak punya data."""
        ...


def _to_decimal(value) -> Decimal | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return Decimal(str(round(f, 4)))


def rows_to_bars(rows: Iterable[tuple]) -> list[PriceBar]:
    """(tanggal, open, high, low, close, volume) -> PriceBar.
    Baris rusak dibuang: NaN/kosong, close <= 0, atau high < low.
    Tanggal ganda digabung (yang terakhir menang). Hasil urut tanggal."""
    bars: dict[date, PriceBar] = {}
    for trade_date, o, h, l, c, v in rows:
        o_, h_, l_, c_ = (_to_decimal(x) for x in (o, h, l, c))
        if None in (o_, h_, l_, c_):
            continue
        if c_ <= 0 or h_ < l_:
            continue
        vol = _to_decimal(v)
        volume = int(vol) if vol is not None and vol > 0 else 0
        bars[trade_date] = PriceBar(trade_date, o_, h_, l_, c_, volume)
    return [bars[d] for d in sorted(bars)]


def encode_quote(price: Decimal, as_of: date) -> str:
    return json.dumps({"p": str(price), "d": as_of.isoformat()})


def decode_quote(raw: str) -> tuple[Decimal, date]:
    """Raise ValueError jika isi cache rusak (pemanggil lalu mengabaikan cache)."""
    try:
        obj = json.loads(raw)
        return Decimal(obj["p"]), date.fromisoformat(obj["d"])
    except (KeyError, TypeError, ValueError, ArithmeticError) as e:
        raise ValueError("Isi cache harga rusak") from e
