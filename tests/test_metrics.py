from datetime import date, datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace as NS

from app.services.metrics import (
    allocation, build_totals, make_events, value_holding, xirr,
)
from app.services.positions import Position


def _pos(q, cost, realized="0"):
    return Position(D(q), D(cost), D(realized))


def test_value_holding_market():
    h = value_holding(1, "BBCA.JK", "Bank", _pos("10", "1000"), D("120"), date(2026, 10, 30))
    assert h.market_value == D("1200.00") and h.floating_pl == D("200.00")
    assert h.floating_pl_pct == D("20.00") and h.price_source == "market"


def test_value_holding_without_price_uses_cost_and_zero_pl():
    h = value_holding(1, "X", None, _pos("3", "100"), None, None)
    assert h.price_source == "cost" and h.floating_pl == 0 and h.market_value == D("100.00")


def test_build_totals():
    h = value_holding(1, "A", None, _pos("10", "1000"), D("120"), date(2026, 10, 30))
    t = build_totals(D("500"), [h], D("2000"), D("500"), D("50"), D("24"), D("30"))
    assert t.net_worth == D("1700.00") and t.net_deposits == D("1500")
    assert t.total_pl == D("200.00") and t.roi_pct == D("13.33")
    assert t.dividend_yield_pct == D("2.00") and t.yield_on_cost_pct == D("2.40")


def test_roi_none_without_deposits():
    t = build_totals(D("0"), [], D("0"), D("0"), D("0"), D("0"), D("0"))
    assert t.roi_pct is None and t.net_worth == 0


def test_allocation():
    rows = allocation({"BBCA": D("300"), "Kas": D("100"), "Nol": D("0")})
    assert [r.label for r in rows] == ["BBCA", "Kas"]
    assert rows[0].pct == D("75.00") and rows[1].pct == D("25.00")
    assert allocation({}) == []


def test_xirr_simple_ten_percent():
    r = xirr([(date(2025, 1, 1), D("-1000")), (date(2026, 1, 1), D("1100"))])
    assert abs(r - 0.10) < 1e-6


def test_xirr_none_cases():
    assert xirr([(date(2026, 1, 1), D("-1000")), (date(2026, 1, 10), D("1100"))]) is None  # < 30 hari
    assert xirr([(date(2025, 1, 1), D("-1000")), (date(2026, 1, 1), D("-5"))]) is None      # satu arah
    assert xirr([]) is None


def test_make_events():
    t0 = datetime(2026, 1, 2, 3, 0, tzinfo=timezone.utc)
    txs = [
        NS(type="BUY", quantity=D("10"), price=D("50"), fee=D("5"), executed_at=t0, stock_id=1),
        NS(type="SELL", quantity=D("4"), price=D("60"), fee=D("2"), executed_at=t0, stock_id=1),
    ]
    cfs = [NS(type="DEPOSIT", amount=D("1000"), occurred_at=t0),
           NS(type="WITHDRAW", amount=D("100"), occurred_at=t0)]
    divs = [NS(amount=D("7"), paid_on=date(2026, 1, 2))]
    ev = make_events(txs, cfs, divs)
    assert ev[0].cash_delta == D("-505.00") and ev[0].qty_delta == D("10")
    assert ev[1].cash_delta == D("238.00") and ev[1].qty_delta == D("-4")
    assert ev[2].capital_delta == D("1000") and ev[3].capital_delta == D("-100")
    assert ev[4].cash_delta == D("7") and ev[4].capital_delta == 0
