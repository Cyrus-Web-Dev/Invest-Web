from datetime import date
from decimal import Decimal as D

import pytest

from app.services.positions import Trade, compute_position
from app.services.tax_report import (
    DatedTrade, available_years, build_annual_report, positions_at, sale_lines,
)

TODAY = date(2026, 11, 2)


def T(day, sym, kind, q, p, fee="0"):
    return DatedTrade(day, sym, kind, D(q), D(p), D(fee))


TRADES = [
    T(date(2025, 1, 10), "AAA", "BUY", "100", "100", "10"),       # biaya 10.010
    T(date(2025, 2, 10), "AAA", "BUY", "100", "200", "20"),       # biaya 20.020 -> total 30.030, rata-rata 150,15
    T(date(2025, 3, 10), "AAA", "SELL", "50", "300", "15"),       # bruto 15.000, bersih 14.985, basis 7.507,50
    T(date(2025, 6, 1), "BBB", "BUY", "10", "1000"),
    T(date(2026, 2, 1), "AAA", "SELL", "150", "120", "10"),       # jual habis
    T(date(2026, 5, 1), "BBB", "SELL", "4", "1500", "6"),
]
DIVS = [(date(2025, 4, 1), "AAA", D("300")), (date(2026, 4, 1), "AAA", D("100")), (date(2026, 8, 1), "BBB", D("50"))]


def test_sale_lines_match_position_realized():
    lines = sale_lines(TRADES)
    assert len(lines) == 3
    for sym in ("AAA", "BBB"):
        pos = compute_position(Trade(t.type, t.quantity, t.price, t.fee) for t in TRADES if t.symbol == sym)
        assert abs(sum(l.realized for l in lines if l.symbol == sym) - pos.realized_pl) < D("0.05")


def test_first_sale_numbers():
    l = sale_lines(TRADES)[0]
    assert (l.gross, l.fee, l.net) == (D("15000.00"), D("15.00"), D("14985.00"))
    assert l.cost_basis == D("7507.50") and l.realized == D("7477.50")


def test_full_sale_uses_exact_remaining_cost():
    last = [l for l in sale_lines(TRADES) if l.symbol == "AAA" and l.day.year == 2026][0]
    assert last.cost_basis == D("22522.50")            # 30.030 - 7.507,50
    assert last.realized == last.net - last.cost_basis


def test_annual_report_2025_vs_2026():
    r25 = build_annual_report(TRADES, DIVS, {}, 2025, TODAY)
    assert r25.totals.sales_count == 1 and r25.totals.dividends == D("300") and r25.totals.gross_sales == D("15000.00")
    assert [s.symbol for s in r25.by_stock] == ["AAA"] and r25.as_of == date(2025, 12, 31)
    syms = {p.symbol: p for p in r25.positions}
    assert syms["AAA"].quantity == D("150") and syms["BBB"].quantity == D("10")
    r26 = build_annual_report(TRADES, DIVS, {"BBB": (D("1600"), date(2026, 10, 30))}, 2026, TODAY)
    assert r26.as_of == TODAY and r26.totals.sales_count == 2 and r26.totals.dividends == D("150")
    assert [p.symbol for p in r26.positions] == ["BBB"]                      # AAA sudah habis
    assert r26.positions[0].market_value == D("9600.00") and r26.positions[0].quantity == D("6")
    assert r26.totals.realized_pl == sum(l.realized for l in r26.sales)


def test_year_end_position_uses_only_trades_up_to_date():
    pos = positions_at(TRADES, date(2025, 12, 31))
    assert pos["AAA"].quantity == D("150") and "BBB" in pos


def test_position_without_price_has_none_value():
    r = build_annual_report(TRADES, DIVS, {}, 2025, TODAY)
    assert all(p.price is None and p.market_value is None for p in r.positions)


def test_available_years_sorted_desc_includes_current():
    assert available_years(TRADES, DIVS, TODAY) == [2026, 2025]
    assert available_years([], [], TODAY) == [2026]


def test_oversell_raises():
    with pytest.raises(ValueError):
        sale_lines([T(date(2025, 1, 1), "A", "BUY", "1", "1"), T(date(2025, 1, 2), "A", "SELL", "2", "1")])
