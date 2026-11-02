"""Deret harian net worth vs modal disetor, dihitung ulang dari buku besar (akurat, tanpa snapshot)."""
from datetime import date
from decimal import Decimal

import pandas as pd

from app.services.metrics import LedgerEvent


def _daily_sum(pairs: list[tuple[date, float]], idx: pd.DatetimeIndex) -> pd.Series:
    if not pairs:
        return pd.Series(0.0, index=idx)
    s = pd.Series([v for _, v in pairs], index=pd.DatetimeIndex([pd.Timestamp(d) for d, _ in pairs]))
    return s.groupby(level=0).sum().reindex(idx, fill_value=0.0)


def build_performance_series(
    events: list[LedgerEvent],
    closes: dict[int, list[tuple[date, Decimal]]],
    end: date,
    days: int,
) -> list[dict]:
    """Return [{date, net_worth, invested_capital, cash, holdings_value}, ...] per hari (float, 2 desimal)."""
    if not events:
        return []
    start = min(e.day for e in events)
    if start > end:
        return []
    idx = pd.date_range(start, end, freq="D")

    cash = _daily_sum([(e.day, float(e.cash_delta)) for e in events], idx).cumsum()
    capital = _daily_sum([(e.day, float(e.capital_delta)) for e in events], idx).cumsum()

    holdings = pd.Series(0.0, index=idx)
    for sid in {e.stock_id for e in events if e.stock_id is not None}:
        mine = [e for e in events if e.stock_id == sid]
        qty = _daily_sum([(e.day, float(e.qty_delta)) for e in mine], idx).cumsum()

        # Harga: penutupan dari DB; di hari transaksi tanpa data, pakai harga transaksi.
        obs = {d: float(p) for d, p in closes.get(sid, [])}
        for e in mine:
            if e.price is not None and e.day not in obs:
                obs[e.day] = float(e.price)
        px = pd.Series(obs)
        px.index = pd.DatetimeIndex([pd.Timestamp(d) for d in px.index])
        px = px.sort_index()
        px = px.reindex(idx.union(px.index)).ffill().reindex(idx)
        holdings = holdings + (qty * px).fillna(0.0)

    df = pd.DataFrame({
        "net_worth": cash + holdings,
        "invested_capital": capital,
        "cash": cash,
        "holdings_value": holdings,
    })
    df = df[df.index >= pd.Timestamp(end) - pd.Timedelta(days=days)]
    return [
        {"date": ts.date(), **{c: round(float(row[c]), 2) for c in df.columns}}
        for ts, row in df.iterrows()
    ]
