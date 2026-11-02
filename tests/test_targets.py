from decimal import Decimal as D

from app.services.targets import stop_message, target_message, target_metrics


def test_metrics_full():
    m = target_metrics(D("100"), D("120"), D("150"), D("90"))
    assert m["target_from_cost_pct"] == D("50.00") and m["stop_from_cost_pct"] == D("-10.00")
    assert m["to_target_pct"] == D("25.00") and m["to_stop_pct"] == D("-25.00")
    assert m["progress_pct"] == D("40.00") and m["risk_reward"] == D("5.00")


def test_metrics_negative_progress_when_below_cost():
    m = target_metrics(D("100"), D("90"), D("150"), None)
    assert m["progress_pct"] == D("-20.00") and m["risk_reward"] is None and m["to_stop_pct"] is None


def test_metrics_without_holding_or_price():
    m = target_metrics(None, D("200"), D("250"), D("180"))
    assert m["progress_pct"] is None and m["risk_reward"] is None and m["target_from_cost_pct"] is None
    assert m["to_target_pct"] == D("25.00") and m["to_stop_pct"] == D("-10.00")
    m2 = target_metrics(D("100"), None, D("150"), D("90"))
    assert m2["to_target_pct"] is None and m2["progress_pct"] is None and m2["risk_reward"] == D("5.00")


def test_metrics_target_below_cost_has_no_progress_or_rr():
    m = target_metrics(D("100"), D("95"), D("80"), D("70"))
    assert m["progress_pct"] is None and m["risk_reward"] is None


def test_messages():
    t, msg = target_message("BBCA.JK", D("10000"), D("10050"))
    assert t == "Target harga BBCA.JK tercapai" and "10.000,00" in msg and "10.050,00" in msg
    t, msg = stop_message("AAPL", D("150"), D("149.5"))
    assert t == "Stop loss AAPL tersentuh" and "149,50" in msg
