import math
from datetime import date, timedelta

from app.services.risk import (
    Point, bench_returns, beta, concentration, max_drawdown, shadow_benchmark, total_return,
    twr_returns, volatility, weekday_points,
)

D0 = date(2026, 1, 5)  # Senin


def _day(n):
    return D0 + timedelta(days=n)


def test_twr_neutralizes_deposits():
    pts = [Point(_day(0), 1000, 1000), Point(_day(1), 1100, 1000), Point(_day(2), 2100, 2000)]
    rets = twr_returns(pts)
    assert math.isclose(rets[0][1], 0.10) and math.isclose(rets[1][1], 0.0, abs_tol=1e-12)
    assert math.isclose(total_return(rets), 0.10)


def test_twr_skips_zero_base_and_handles_withdrawal():
    assert twr_returns([Point(_day(0), 0, 0), Point(_day(1), 1000, 1000)]) == []
    rets = twr_returns([Point(_day(0), 2000, 2000), Point(_day(1), 1100, 1000)])  # tarik 1000, sisa +10%
    assert math.isclose(rets[0][1], 0.05)


def test_weekday_points_filters_weekend():
    pts = [Point(_day(i), 1, 1) for i in range(7)]
    assert [p.day.weekday() for p in weekday_points(pts)] == [0, 1, 2, 3, 4]


def test_volatility_needs_enough_data_and_matches_formula():
    rets = [(_day(i), 0.01 if i % 2 == 0 else -0.01) for i in range(10)]
    assert volatility(rets) is None
    rets = [(_day(i), 0.01 if i % 2 == 0 else -0.01) for i in range(40)]
    expected = 0.01 * math.sqrt(40 / 39) * math.sqrt(252)
    assert math.isclose(volatility(rets), expected, rel_tol=1e-9)


def test_max_drawdown():
    rets = [(_day(1), 0.10), (_day(2), -0.20), (_day(3), 0.05)]
    dd, peak, trough = max_drawdown(rets, _day(0))
    assert math.isclose(dd, -0.20) and peak == _day(1) and trough == _day(2)
    assert max_drawdown([], _day(0)) is None
    assert max_drawdown([(_day(1), 0.1), (_day(2), 0.1)], _day(0))[0] == 0.0


def test_beta_scales_with_leverage_and_needs_obs():
    days = [_day(i) for i in range(41)]
    bench = {d: 0.01 * math.sin(i) for i, d in enumerate(days[1:], 1)}
    port = [(d, 2 * r) for d, r in bench.items()]
    assert math.isclose(beta(port, bench), 2.0, rel_tol=1e-9)
    assert beta(port[:10], bench) is None


def test_bench_returns_forward_fill():
    closes = {_day(0): 100.0, _day(2): 110.0}
    r = bench_returns([_day(0), _day(1), _day(2)], closes)
    assert r[_day(1)] == 0.0 and math.isclose(r[_day(2)], 0.10)


def test_shadow_benchmark_same_capital_into_index():
    closes = {_day(0): 100.0, _day(1): 110.0, _day(2): 120.0}
    out = shadow_benchmark({_day(0): 1000.0, _day(2): 1000.0}, closes, [_day(0), _day(1), _day(2)])
    assert [round(x, 2) for x in out] == [1000.0, 1100.0, 2200.0]


def test_shadow_benchmark_before_index_data_is_flat():
    closes = {_day(1): 100.0, _day(2): 120.0}
    out = shadow_benchmark({_day(0): 500.0}, closes, [_day(0), _day(1), _day(2)])
    assert [round(x, 2) for x in out] == [500.0, 500.0, 600.0]
    assert shadow_benchmark({}, {}, [_day(0)]) == []


def test_concentration_scores():
    two = concentration({"A": 50, "B": 50}, {"X": 50, "Y": 50})
    assert two.score == 50 and math.isclose(two.effective_n, 2.0) and two.holdings == 2
    one = concentration({"A": 100}, {"X": 100})
    assert one.score == 0 and one.top1_pct == 100 and one.top_sector == "X"
    ten = concentration({str(i): 10 for i in range(10)}, {"X": 100})
    assert ten.score == 90 and math.isclose(ten.top3_pct, 30.0)
    assert concentration({}, {}) is None and concentration({"A": 0}, {}) is None
