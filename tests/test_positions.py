from decimal import Decimal as D

import pytest

from app.services.positions import Trade, compute_position


def test_buy_includes_fee_in_cost():
    pos = compute_position([Trade("BUY", D("10"), D("100"), D("5"))])
    assert pos.quantity == D("10")
    assert pos.total_cost == D("1005")
    assert pos.avg_cost == D("100.5")


def test_average_down_and_partial_sell():
    pos = compute_position([
        Trade("BUY", D("100"), D("1000")),
        Trade("BUY", D("100"), D("2000")),
        Trade("SELL", D("50"), D("1800"), D("100")),
    ])
    assert pos.quantity == D("150")
    assert pos.total_cost == D("225000")
    assert pos.realized_pl == D("14900")  # 89.900 - 75.000


def test_sell_all_leaves_zero_cost():
    pos = compute_position([
        Trade("BUY", D("3"), D("100")),
        Trade("SELL", D("3"), D("90")),
    ])
    assert pos.quantity == 0
    assert pos.total_cost == 0
    assert pos.realized_pl == D("-30")


def test_oversell_raises():
    with pytest.raises(ValueError):
        compute_position([Trade("BUY", D("1"), D("10")), Trade("SELL", D("2"), D("10"))])


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        compute_position([Trade("HOLD", D("1"), D("10"))])
