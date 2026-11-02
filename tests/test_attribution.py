import math
from datetime import date
from decimal import Decimal as D

from app.demo.generator import generate_plan
from app.services.attribution import AttrInput, build_attribution
from app.services.metrics import ZERO, build_totals, money, value_holding
from app.services.positions import Trade, compute_position
from app.services.risk import monthly_returns, yearly_from_monthly


def test_rows_sorted_and_percentages():
    items = [
        AttrInput("A", "X", D("1000"), D("100"), D("50"), D("10"), True),     # total 160
        AttrInput("B", None, D("2000"), D("-50"), D("20"), D("0"), False),    # total -30
        AttrInput("C", "Y", D("500"), D("0"), D("40"), D("0"), True),         # total 40
    ]
    rows, residual = build_attribution(items, D("170"), D("1000"))
    assert [r.symbol for r in rows] == ["A", "C", "B"] and residual == D("0")
    a = rows[0]
    assert a.share_of_pl_pct == D("94.12") and a.contribution_to_return_pct == D("16.00") and a.return_on_cost_pct == D("16.00")
    assert rows[2].total == D("-30") and rows[2].share_of_pl_pct == D("-17.65")


def test_share_is_none_when_total_not_positive():
    rows, _ = build_attribution([AttrInput("A", None, D("100"), D("-10"), D("0"), D("0"), False)], D("-10"), D("100"))
    assert rows[0].share_of_pl_pct is None and rows[0].contribution_to_return_pct == D("-10.00")


def test_residual_reports_rounding_gap():
    _, residual = build_attribution([AttrInput("A", None, D("100"), D("10"), D("0"), D("0"), False)], D("10.03"), D("100"))
    assert residual == D("0.03")


def _identity(trades_by_symbol, deposits, withdrawals, dividends_by_symbol, prices):
    """Hitung kas dengan rumus buku besar, lalu bandingkan jumlah atribusi dengan total untung/rugi."""
    cash = deposits - withdrawals + sum(dividends_by_symbol.values(), ZERO)
    items, holdings, realized = [], [], ZERO
    for sym, ts in trades_by_symbol.items():
        invested = ZERO
        for t in ts:
            gross = t.quantity * t.price
            if t.type == "BUY":
                cash -= money(gross + t.fee)
                invested += gross + t.fee
            else:
                cash += money(gross - t.fee)
        pos = compute_position(ts)
        realized += pos.realized_pl
        floating = ZERO
        if pos.quantity > 0:
            h = value_holding(1, sym, None, pos, prices.get(sym), None)
            holdings.append(h)
            floating = h.floating_pl
        items.append(AttrInput(sym, None, money(invested), money(pos.realized_pl), floating, dividends_by_symbol.get(sym, ZERO), pos.quantity > 0))
    totals = build_totals(cash, holdings, deposits, withdrawals, sum(dividends_by_symbol.values(), ZERO),
                          sum(dividends_by_symbol.values(), ZERO), realized)
    rows, residual = build_attribution(items, totals.total_pl, totals.net_deposits)
    return totals, rows, residual


def test_identity_manual_scenario():
    trades = {
        "AAA": [Trade("BUY", D("100"), D("100"), D("10")), Trade("BUY", D("100"), D("200"), D("20")), Trade("SELL", D("50"), D("300"), D("15"))],
        "BBB": [Trade("BUY", D("10"), D("1000")), Trade("SELL", D("10"), D("900"), D("5"))],       # rugi, ditutup
    }
    totals, rows, residual = _identity(trades, D("100000"), D("5000"), {"AAA": D("300")}, {"AAA": D("250")})
    assert abs(residual) < D("0.05"), residual
    assert abs(sum(r.total for r in rows) - totals.total_pl) < D("0.05")
    assert {r.symbol: r.held for r in rows} == {"AAA": True, "BBB": False}


def test_identity_on_demo_plan():
    plan = generate_plan(date(2026, 11, 2))
    by: dict[str, list[Trade]] = {}
    for t in sorted(plan.trades, key=lambda x: x.seq):
        by.setdefault(t.symbol, []).append(Trade(t.type, D(t.qty), t.price, t.fee))
    divs: dict[str, D] = {}
    for d in plan.dividends:
        divs[d.symbol] = divs.get(d.symbol, ZERO) + d.amount
    deposits = sum((c.amount for c in plan.cashflows if c.type == "DEPOSIT"), ZERO)
    withdrawals = sum((c.amount for c in plan.cashflows if c.type == "WITHDRAW"), ZERO)
    prices = {s: plan.prices[s][-1].close for s in by}
    totals, rows, residual = _identity(by, deposits, withdrawals, divs, prices)
    assert abs(residual) < D("1"), residual
    assert totals.net_worth - plan.final_cash == sum((h.market_value for h in [value_holding(1, s, None, compute_position(t), prices[s], None) for s, t in by.items() if compute_position(t).quantity > 0]), ZERO)
    assert rows[0].total >= rows[-1].total


def test_monthly_returns_compound_within_month():
    rets = [(date(2026, 1, 5), 0.01), (date(2026, 1, 6), 0.01), (date(2026, 2, 2), -0.02), (date(2027, 1, 4), 0.05)]
    m = monthly_returns(rets)
    assert math.isclose(m[(2026, 1)], 1.01 * 1.01 - 1) and math.isclose(m[(2026, 2)], -0.02) and math.isclose(m[(2027, 1)], 0.05)
    y = yearly_from_monthly(m)
    assert math.isclose(y[2026], (1.01 * 1.01) * 0.98 - 1) and math.isclose(y[2027], 0.05)
    assert monthly_returns([]) == {}
