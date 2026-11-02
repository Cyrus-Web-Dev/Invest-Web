from datetime import date
from decimal import Decimal as D

from app.services.journal import UNTAGGED, BuyRecord, build_journal


def B(i, sid, sym, qty, price, tags, note=None, day=date(2026, 1, 5)):
    return BuyRecord(i, day, sid, sym, D(qty), D(price), D("0"), note, tags)


def test_returns_pnl_and_held():
    items, _ = build_journal([B(1, 1, "AAA", "100", "100", ["value"])], {1: D("120")}, {1})
    it = items[0]
    assert it.return_pct == D("20.00") and it.pnl == D("2000.00") and it.still_held and it.cost == D("10000.00")


def test_missing_price_gives_none():
    items, stats = build_journal([B(1, 1, "AAA", "10", "100", [])], {}, set())
    assert items[0].return_pct is None and items[0].pnl is None and not items[0].still_held
    assert stats[0].tag == UNTAGGED and stats[0].weighted_return_pct is None and stats[0].win_rate_pct is None


def test_tag_stats_weighted_and_win_rate():
    buys = [B(1, 1, "AAA", "100", "100", ["value"]),      # +20% biaya 10.000
            B(2, 2, "BBB", "50", "200", ["value", "growth"]),  # -10% biaya 10.000
            B(3, 3, "CCC", "10", "100", ["growth"])]      # +50% biaya 1.000
    _, stats = build_journal(buys, {1: D("120"), 2: D("180"), 3: D("150")}, {1, 2, 3})
    s = {x.tag: x for x in stats}
    assert s["value"].count == 2 and s["value"].total_cost == D("20000.00")
    assert s["value"].weighted_return_pct == D("5.00") and s["value"].win_rate_pct == D("50.00")
    assert s["growth"].count == 2 and s["growth"].win_rate_pct == D("50.00")
    assert [x.tag for x in stats][0] == "value"         # urut biaya terbesar


def test_items_sorted_newest_first():
    items, _ = build_journal([B(1, 1, "A", "1", "1", [], day=date(2026, 1, 1)), B(2, 1, "A", "1", "1", [], day=date(2026, 3, 1))], {}, set())
    assert [i.id for i in items] == [2, 1]
