from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal as D
from types import SimpleNamespace as NS

from app.demo.generator import (
    INDEX_SYMBOL, LOT, UNIVERSE, business_days, generate_plan, round_tick, tick,
)
from app.services.csv_import import existing_sim_events, simulate

TODAY = date(2026, 11, 2)
UTC = timezone.utc


def _at(day, seq):
    return datetime.combine(day, time(12, 0), tzinfo=UTC) + timedelta(seconds=seq)


def test_tick_sizes_and_rounding():
    assert [tick(p) for p in (150, 300, 1000, 3000, 9000)] == [1, 2, 5, 10, 25]
    assert round_tick(9310) == D("9300") and round_tick(9312.7) == D("9325") and round_tick(2403) == D("2400") and round_tick(12) == D("12")


def test_business_days_exclude_weekends():
    days = business_days(date(2026, 11, 2), date(2026, 11, 9))
    assert all(d.weekday() < 5 for d in days) and len(days) == 6


def test_deterministic_and_seed_sensitive():
    a, b, c = generate_plan(TODAY, 2026), generate_plan(TODAY, 2026), generate_plan(TODAY, 7)
    assert [(t.day, t.symbol, t.qty) for t in a.trades] == [(t.day, t.symbol, t.qty) for t in b.trades]
    assert a.final_cash == b.final_cash and a.prices["BBCA.JK"][-1].close == b.prices["BBCA.JK"][-1].close
    assert a.prices["BBCA.JK"][-1].close != c.prices["BBCA.JK"][-1].close


def test_price_bars_are_valid():
    plan = generate_plan(TODAY)
    assert set(plan.prices) >= set(UNIVERSE) | {INDEX_SYMBOL}
    for sym, bars in plan.prices.items():
        assert len(bars) == len(plan.days)
        for bar in bars:
            assert bar.low <= min(bar.open, bar.close) and bar.high >= max(bar.open, bar.close) and bar.low > 0
        if sym != INDEX_SYMBOL:
            assert all(b.close == b.close.to_integral_value() for b in bars)      # harga rupiah bulat sesuai fraksi


def test_plan_ledger_is_valid_and_cash_matches():
    plan = generate_plan(TODAY)
    trades = [NS(id=i, type=t.type, quantity=D(t.qty), price=t.price, fee=t.fee,
                 executed_at=_at(t.day, t.seq), stock_id=hash(t.symbol) % 10_000) for i, t in enumerate(plan.trades, 1)]
    cfs = [NS(id=i, type=c.type, amount=c.amount, occurred_at=_at(c.day, c.seq)) for i, c in enumerate(plan.cashflows, 1)]
    divs = [NS(id=i, amount=d.amount, paid_on=d.day, stock_id=1) for i, d in enumerate(plan.dividends, 1)]
    errs, cash = simulate(existing_sim_events(trades, cfs, divs))
    assert not errs, errs[:3]
    assert cash == plan.final_cash and cash >= 0


def test_plan_has_realistic_variety():
    plan = generate_plan(TODAY)
    kinds = {t.type for t in plan.trades}
    assert kinds == {"BUY", "SELL"} and len(plan.trades) >= 25 and len(plan.dividends) >= 5
    assert all(t.qty % LOT == 0 and t.qty > 0 for t in plan.trades)
    assert all(t.tags and t.note for t in plan.trades)
    assert {c.type for c in plan.cashflows} == {"DEPOSIT", "WITHDRAW"}
    assert len(plan.holdings) >= 4
    assert max(t.day for t in plan.trades) <= TODAY and min(c.day for c in plan.cashflows) == plan.days[0]
