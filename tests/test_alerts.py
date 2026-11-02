from decimal import Decimal as D

from app.services.alerts import alert_message, change_pct, fmt_price, is_triggered


def test_is_triggered_boundaries():
    assert is_triggered("ABOVE", D("100"), D("100"))
    assert is_triggered("ABOVE", D("100"), D("101"))
    assert not is_triggered("ABOVE", D("100"), D("99.99"))
    assert is_triggered("BELOW", D("100"), D("100"))
    assert is_triggered("BELOW", D("100"), D("99"))
    assert not is_triggered("BELOW", D("100"), D("100.01"))
    assert not is_triggered("SIDEWAYS", D("100"), D("100"))


def test_fmt_price_indonesian_style():
    assert fmt_price(D("9250")) == "9.250,00"
    assert fmt_price(D("1234567.891")) == "1.234.567,89"
    assert fmt_price(D("0.5")) == "0,50"


def test_change_pct():
    assert change_pct(D("110"), D("100")) == D("10.00")
    assert change_pct(D("90"), D("100")) == D("-10.00")
    assert change_pct(D("100"), D("0")) is None


def test_alert_message():
    title, msg = alert_message("BBCA.JK", "BELOW", D("9000"), D("8950"))
    assert title == "Alert harga BBCA.JK"
    assert "turun hingga 9.000,00" in msg and "8.950,00" in msg
    _, msg2 = alert_message("AAPL", "ABOVE", D("200"), D("201.5"))
    assert "naik mencapai 200,00" in msg2
