"""Metrik risiko, benchmark, dan konsentrasi (murni: tanpa DB/Pandas)."""
import math
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date

TRADING_DAYS = 252
MIN_VOL_OBS = 20
MIN_BETA_OBS = 30


@dataclass(frozen=True)
class Point:
    day: date
    value: float      # net worth akhir hari
    invested: float   # modal bersih kumulatif (setoran - penarikan)


def weekday_points(points: list[Point]) -> list[Point]:
    """Hanya Senin-Jumat: akhir pekan datar akan menekan volatilitas secara semu."""
    return [p for p in points if p.day.weekday() < 5]


def twr_returns(points: list[Point]) -> list[tuple[date, float]]:
    """Return harian time-weighted: setoran/penarikan dinetralkan (r = (V_t - F_t)/V_{t-1} - 1)."""
    out: list[tuple[date, float]] = []
    for prev, cur in zip(points, points[1:]):
        if prev.value <= 0:
            continue
        ratio = (cur.value - (cur.invested - prev.invested)) / prev.value
        if ratio < 0:
            continue
        out.append((cur.day, ratio - 1.0))
    return out


def total_return(rets: list[tuple[date, float]]) -> float | None:
    if not rets:
        return None
    g = 1.0
    for _, r in rets:
        g *= 1.0 + r
    return g - 1.0


def volatility(rets: list[tuple[date, float]]) -> float | None:
    """Simpangan baku return harian dikali akar 252 (tahunan, dalam pecahan)."""
    n = len(rets)
    if n < MIN_VOL_OBS:
        return None
    vals = [r for _, r in rets]
    m = sum(vals) / n
    var = sum((v - m) ** 2 for v in vals) / (n - 1)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def max_drawdown(rets: list[tuple[date, float]], base_day: date) -> tuple[float, date, date] | None:
    """(drawdown negatif terdalam, tanggal puncak, tanggal lembah) dari kurva ekuitas TWR."""
    if not rets:
        return None
    eq, peak, peak_day = 1.0, 1.0, base_day
    worst, w_peak, w_trough = 0.0, base_day, base_day
    for d, r in rets:
        eq *= 1.0 + r
        if eq > peak:
            peak, peak_day = eq, d
        dd = eq / peak - 1.0
        if dd < worst:
            worst, w_peak, w_trough = dd, peak_day, d
    return worst, w_peak, w_trough


def ffill_fn(closes: dict[date, float]):
    keys = sorted(closes)

    def price(d: date) -> float | None:
        i = bisect_right(keys, d) - 1
        return closes[keys[i]] if i >= 0 else None

    return price


def bench_returns(days: list[date], closes: dict[date, float]) -> dict[date, float]:
    price = ffill_fn(closes)
    out: dict[date, float] = {}
    for d0, d1 in zip(days, days[1:]):
        p0, p1 = price(d0), price(d1)
        if p0 and p1:
            out[d1] = p1 / p0 - 1.0
    return out


def beta(port_rets: list[tuple[date, float]], bench: dict[date, float]) -> float | None:
    pairs = [(r, bench[d]) for d, r in port_rets if d in bench]
    n = len(pairs)
    if n < MIN_BETA_OBS:
        return None
    mp = sum(p for p, _ in pairs) / n
    mb = sum(b for _, b in pairs) / n
    cov = sum((p - mp) * (b - mb) for p, b in pairs) / (n - 1)
    var = sum((b - mb) ** 2 for _, b in pairs) / (n - 1)
    return cov / var if var > 0 else None


def shadow_benchmark(flows: dict[date, float], closes: dict[date, float], days: list[date]) -> list[float]:
    """Nilai 'portofolio bayangan': modal yang sama (setoran/penarikan di tanggal yang sama)
    seluruhnya ditaruh di indeks. Sebelum data indeks ada, memakai harga indeks pertama."""
    if not closes:
        return []
    price = ffill_fn(closes)
    first = closes[min(closes)]
    units = 0.0
    out: list[float] = []
    for d in days:
        p = price(d)
        if p is None:
            p = first
        f = flows.get(d, 0.0)
        if f:
            units += f / p
        out.append(units * p)
    return out


@dataclass(frozen=True)
class Concentration:
    holdings: int
    sectors: int
    top1_pct: float
    top3_pct: float
    top_sector: str | None
    top_sector_pct: float
    hhi: float
    effective_n: float
    score: int  # 0-100, makin tinggi makin terdiversifikasi


def concentration(values: dict[str, float], sectors: dict[str, float]) -> Concentration | None:
    """Konsentrasi di antara saham (kas tidak dihitung). Skor = (1 - HHI) x 100:
    1 saham = 0, 2 saham sama besar = 50, 4 = 75, 10 = 90."""
    pos = {k: v for k, v in values.items() if v > 0}
    total = sum(pos.values())
    if total <= 0:
        return None
    w = sorted((v / total for v in pos.values()), reverse=True)
    hhi = sum(x * x for x in w)
    sec_pos = {k: v for k, v in sectors.items() if v > 0}
    sec_total = sum(sec_pos.values()) or 1.0
    top_sector = max(sec_pos, key=sec_pos.get) if sec_pos else None
    return Concentration(
        holdings=len(w), sectors=len(sec_pos), top1_pct=w[0] * 100, top3_pct=sum(w[:3]) * 100,
        top_sector=top_sector, top_sector_pct=(sec_pos[top_sector] / sec_total * 100) if top_sector else 0.0,
        hhi=hhi, effective_n=1.0 / hhi, score=round((1.0 - hhi) * 100),
    )


def monthly_returns(rets: list[tuple[date, float]]) -> dict[tuple[int, int], float]:
    """Return bulanan time-weighted = hasil majemuk return harian dalam bulan itu (pecahan)."""
    g: dict[tuple[int, int], float] = {}
    for d, r in rets:
        k = (d.year, d.month)
        g[k] = g.get(k, 1.0) * (1.0 + r)
    return {k: v - 1.0 for k, v in g.items()}


def yearly_from_monthly(m: dict[tuple[int, int], float]) -> dict[int, float]:
    out: dict[int, float] = {}
    for (y, _mo), r in sorted(m.items()):
        out[y] = out.get(y, 1.0) * (1.0 + r)
    return {y: v - 1.0 for y, v in out.items()}
