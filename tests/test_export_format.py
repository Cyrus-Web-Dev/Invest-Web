from datetime import date
from decimal import Decimal as D

from app.services.csv_import import parse_csv
from app.services.export_format import LEDGER_HEADERS, fmt_num, ledger_row, sanitize_cell, to_csv


def test_sanitize_cell():
    assert sanitize_cell("=SUM(A1)") == "'=SUM(A1)"
    assert sanitize_cell("+1") == "'+1" and sanitize_cell("@x") == "'@x" and sanitize_cell("-x") == "'-x"
    assert sanitize_cell("aman") == "aman" and sanitize_cell("") == ""


def test_fmt_num():
    assert fmt_num(D("100.0000")) == "100" and fmt_num(D("0.5000")) == "0.5"
    assert fmt_num(D("1E+2")) == "100" and fmt_num(None) == ""


def test_to_csv_bom_and_separator():
    out = to_csv(["a", "b"], [["1", "x,y"]], ";")
    assert out.startswith("\ufeffa;b\r\n") and '1;x,y' in out


def test_export_then_import_roundtrip():
    rows = [
        ledger_row("DEPOSIT", date(2025, 1, 2), None, None, None, None, D("1000000"), "modal"),
        ledger_row("BUY", date(2025, 1, 3), "BBCA.JK", D("100"), D("9000.5000"), D("2500"), None, "=cmd"),
        ledger_row("SELL", date(2025, 2, 3), "BBCA.JK", D("40"), D("9500"), D("0"), None, None),
        ledger_row("DIVIDEND", date(2025, 3, 1), "BBCA.JK", None, None, None, D("12000"), None),
    ]
    for sep in (",", ";"):
        parsed, errs = parse_csv(to_csv(LEDGER_HEADERS, rows, sep), date(2026, 11, 1))
        assert not errs and [r.kind for r in parsed] == ["DEPOSIT", "BUY", "SELL", "DIVIDEND"]
        assert parsed[1].price == D("9000.5") and parsed[1].fee == D("2500") and parsed[1].note == "=cmd"
        assert parsed[3].amount == D("12000") and parsed[3].symbol == "BBCA.JK"


def test_tags_roundtrip_through_export():
    rows = [ledger_row("BUY", date(2025, 1, 3), "BBCA.JK", D("100"), D("9000"), D("0"), None, "x", ["value", "dividend"])]
    parsed, errs = parse_csv(to_csv(LEDGER_HEADERS, rows, ";"), date(2026, 11, 1))
    assert not errs and parsed[0].tags == "value,dividend"
