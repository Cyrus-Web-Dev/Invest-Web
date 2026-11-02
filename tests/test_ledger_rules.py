from datetime import date, datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace as NS

import pytest

from app.services.csv_import import existing_sim_events, simulate
from app.services.ledger_rules import LedgerRuleError, at_for, check_change, check_sell_fee

UTC = timezone.utc


def T(y, m, d, h=12):
    return datetime(y, m, d, h, tzinfo=UTC)


def tx(i, kind, q, p, at, sid=1, fee="0"):
    return NS(id=i, type=kind, quantity=D(q), price=D(p), fee=D(fee), executed_at=at, stock_id=sid)


def cf(i, kind, amount, at):
    return NS(id=i, type=kind, amount=D(amount), occurred_at=at)


def base():
    txs = [tx(1, "BUY", "10", "100", T(2026, 2, 1)), tx(2, "SELL", "4", "120", T(2026, 3, 1))]
    cfs = [cf(1, "DEPOSIT", "2000", T(2026, 1, 1))]
    # saldo: 2000 - 1000 + 480 = 1480
    return txs, cfs, []


def test_consistent_base_and_balance():
    errs, cash = simulate(existing_sim_events(*base()))
    assert not errs and cash == D("1480")


def test_delete_unrelated_sell_changes_balance_by_delta():
    txs, cfs, divs = base()
    new = ([txs[0]], cfs, divs)
    bal = check_change((txs, cfs, divs), new, D("1480"), None)
    assert bal == D("1000")          # tanpa penjualan 480


def test_delete_deposit_invalidates_later_buy():
    txs, cfs, divs = base()
    with pytest.raises(LedgerRuleError) as e:
        check_change((txs, cfs, divs), (txs, [], divs), D("1480"), None)
    assert "sudah ada" in e.value.message and "2026-02-01" in e.value.message


def test_delete_buy_invalidates_later_sell():
    txs, cfs, divs = base()
    with pytest.raises(LedgerRuleError) as e:
        check_change((txs, cfs, divs), ([txs[1]], cfs, divs), D("1480"), None)
    assert "jual melebihi kepemilikan" in e.value.message


def test_edit_sell_date_before_buy_rejected_and_marked():
    txs, cfs, divs = base()
    moved = [txs[0], tx(2, "SELL", "4", "120", T(2026, 1, 15))]
    with pytest.raises(LedgerRuleError) as e:
        check_change((txs, cfs, divs), (moved, cfs, divs), D("1480"), ("tx", 2))
    assert "Jumlah jual melebihi kepemilikan pada 2026-01-15" in e.value.message   # item yang diubah ditandai


def test_edit_price_ok_and_balance_delta():
    txs, cfs, divs = base()
    new = [txs[0], tx(2, "SELL", "4", "150", T(2026, 3, 1))]   # +120 proceeds
    assert check_change((txs, cfs, divs), (new, cfs, divs), D("1480"), ("tx", 2)) == D("1600")


def test_inconsistent_balance_aborts_with_409():
    txs, cfs, divs = base()
    with pytest.raises(LedgerRuleError) as e:
        check_change((txs, cfs, divs), (txs, cfs, divs), D("1479"), None)
    assert e.value.status_code == 409


def test_same_instant_deposit_buy_sell_ordering():
    at = T(2026, 5, 1)
    txs = [tx(5, "BUY", "5", "10", at), tx(6, "SELL", "5", "12", at)]
    cfs = [cf(9, "DEPOSIT", "50", at)]
    errs, cash = simulate(existing_sim_events(txs, cfs, []))
    assert not errs and cash == D("60")       # setoran -> beli -> jual, walau waktunya identik


def test_new_item_marker_message():
    txs, cfs, divs = base()
    new_tx = tx(-1, "BUY", "100", "100", T(2026, 1, 10))
    with pytest.raises(LedgerRuleError) as e:
        check_change((txs, cfs, divs), (txs + [new_tx], cfs, divs), D("1480"), ("tx", -1))
    assert "Saldo kas tidak cukup pada 2026-01-10" in e.value.message


def test_at_for_rules():
    now = datetime(2026, 11, 1, 3, 0, tzinfo=UTC)
    assert at_for(date(2026, 11, 1), None, now) == now
    assert at_for(date(2026, 3, 1), None, now) == T(2026, 3, 1)
    orig = T(2026, 3, 1, 5)
    assert at_for(date(2026, 3, 1), orig, now) == orig     # tanggal sama: waktu asli dipertahankan
    with pytest.raises(LedgerRuleError):
        at_for(date(2026, 11, 2), None, now)


def test_sell_fee_check():
    check_sell_fee("BUY", D("1"), D("1"), D("999"))
    check_sell_fee("SELL", D("1"), D("100"), D("10"))
    with pytest.raises(LedgerRuleError):
        check_sell_fee("SELL", D("1"), D("1"), D("50"))
