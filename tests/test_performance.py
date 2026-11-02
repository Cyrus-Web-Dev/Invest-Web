from datetime import date
from decimal import Decimal as D

import pytest

pytest.importorskip("pandas")

from app.services.metrics import LedgerEvent  # noqa: E402
from app.services.performance import build_performance_series  # noqa: E402


def test_series_networth_follows_prices_and_cash():
    d1, d2, d3 = date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)
    events = [
        LedgerEvent(d1, D("1000"), D("1000")),                       # setor 1000
        LedgerEvent(d1, D("-500"), D("0"), 1, D("10"), D("50")),     # beli 10 @ 50
    ]
    closes = {1: [(d2, D("60")), (d3, D("70"))]}
    out = build_performance_series(events, closes, d3, 10)
    assert [p["date"] for p in out] == [d1, d2, d3]
    assert [p["net_worth"] for p in out] == [1000.0, 1100.0, 1200.0]
    assert all(p["invested_capital"] == 1000.0 for p in out)
    assert out[2]["cash"] == 500.0 and out[2]["holdings_value"] == 700.0


def test_series_after_full_sell_has_no_holdings():
    d1, d2 = date(2026, 1, 1), date(2026, 1, 2)
    events = [
        LedgerEvent(d1, D("1000"), D("1000")),
        LedgerEvent(d1, D("-500"), D("0"), 1, D("10"), D("50")),
        LedgerEvent(d2, D("600"), D("0"), 1, D("-10"), D("60")),
    ]
    out = build_performance_series(events, {}, d2, 10)
    assert out[-1]["holdings_value"] == 0.0 and out[-1]["net_worth"] == 1100.0


def test_empty_events():
    assert build_performance_series([], {}, date(2026, 1, 3), 10) == []
