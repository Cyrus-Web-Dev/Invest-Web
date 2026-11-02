from datetime import date
from decimal import Decimal as D

from app.services.dividends import (
    DivRecord, last_n_months, monthly_totals, per_stock, projected_calendar, sum_between,
    trailing_12m, yearly_totals,
)

END = date(2026, 11, 1)


def R(sym, y, m, d, amt, sid=1):
    return DivRecord(sid, sym, date(y, m, d), D(str(amt)))


RECS = [
    R("BBCA.JK", 2025, 3, 15, 100), R("BBCA.JK", 2026, 3, 14, 120),
    R("BBCA.JK", 2025, 9, 20, 50), R("BBCA.JK", 2026, 9, 18, 70),
    R("TLKM.JK", 2026, 6, 10, 200, 2), R("UNVR.JK", 2024, 5, 5, 999, 3),
]


def test_last_n_months_wraps_year():
    ks = last_n_months(date(2026, 2, 10), 4)
    assert ks == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert len(last_n_months(END, 24)) == 24 and last_n_months(END, 24)[-1] == "2026-11"


def test_monthly_totals_fills_zero_months():
    m = dict(monthly_totals(RECS, END, 24))
    assert m["2026-03"] == D("120") and m["2026-09"] == D("70") and m["2026-04"] == D("0")
    assert "2024-05" not in m                      # di luar 24 bulan terakhir


def test_trailing_and_ytd_and_yearly():
    assert trailing_12m(RECS, END) == D("120") + D("70") + D("200")     # 2025-11-01 < tgl <= 2026-11-01
    assert sum_between(RECS, date(2026, 1, 1), END) == D("390")
    assert yearly_totals(RECS) == [(2024, D("999")), (2025, D("150")), (2026, D("390"))]


def test_projected_calendar_uses_held_only_and_averages_years():
    cal = projected_calendar(RECS, {"BBCA.JK", "TLKM.JK"}, END)
    by = {c.month: c for c in cal}
    assert by[3].amount == D("110.00") and by[3].symbols == ["BBCA.JK"]      # rata-rata 100 & 120
    assert by[9].amount == D("60.00") and by[6].amount == D("200.00")
    assert by[5].amount == D("0") and by[5].symbols == []                    # UNVR tidak dimiliki / terlalu lama
    assert len(cal) == 12


def test_per_stock_yields():
    held = {"BBCA.JK": (D("100"), D("10000"), D("12500"))}
    rows = {r.symbol: r for r in per_stock(RECS, held, END)}
    b = rows["BBCA.JK"]
    assert b.total == D("340") and b.last_12m == D("190") and b.payments == 4 and b.held
    assert b.yield_on_cost_pct == D("1.90") and b.current_yield_pct == D("1.52")
    assert not rows["UNVR.JK"].held and rows["UNVR.JK"].yield_on_cost_pct is None
    assert list(rows)[0] == "UNVR.JK"      # urut total terbesar
