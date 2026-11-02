from datetime import date, datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace as NS

from app.services.csv_import import (
    TEMPLATE_CSV, existing_sim_events, new_sim_events, parse_csv, parse_decimal, row_timestamp, simulate,
)

TODAY = date(2026, 11, 1)
HDR = "tanggal,jenis,simbol,jumlah,harga,fee,nominal,catatan\n"


def _msgs(errs):
    return " | ".join(e.message for e in errs)


def test_template_is_valid_and_consistent():
    rows, errs = parse_csv(TEMPLATE_CSV, TODAY)
    assert not errs and len(rows) == 5
    ev, e2 = new_sim_events(rows, {"BBCA.JK": 1})
    assert not e2
    sim_errs, cash = simulate(ev)
    assert not sim_errs and cash > 0


def test_decimal_is_strict():
    assert parse_decimal("1000") == D("1000") and parse_decimal("10.5") == D("10.5")
    assert parse_decimal("10,5") == D("10.5")
    for bad in ("1.000,50", "1,000.50", "1.000.000", "-5", "abc", "", "1e3"):
        assert parse_decimal(bad) is None, bad


def test_semicolon_aliases_bom_and_blank_lines():
    text = "\ufeffDate;Type;Symbol;Qty;Price;Fee;Amount;Note\n\n2025-01-02;BUY;bbca.jk;10;9000,5;0;;x\n"
    rows, errs = parse_csv(text, TODAY)
    assert not errs and rows[0].symbol == "BBCA.JK" and rows[0].price == D("9000.5") and rows[0].kind == "BUY"


def test_date_formats():
    text = HDR + "02/01/2025,SETOR,,,,,100,\n2025-01-03,SETOR,,,,,100,\n04-01-2025,SETOR,,,,,100,\n"
    rows, errs = parse_csv(text, TODAY)
    assert not errs and [r.day for r in rows] == [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 4)]


def test_row_errors_reported_with_line_numbers():
    text = HDR + (
        "2027-01-01,SETOR,,,,,100,\n"          # masa depan
        "2025-01-01,BELI,,10,100,0,,\n"        # simbol kosong
        "2025-01-01,JUAL,AAPL,0,100,0,,\n"     # jumlah 0
        "2025-01-01,XYZ,AAPL,1,1,0,,\n"        # jenis tidak dikenal
        "2025-01-01,BELI,AAPL,1.00001,1,0,,\n"  # 5 desimal
        "2025-01-01,SETOR,,,,,1.000,\n"        # pemisah ribuan
    )
    rows, errs = parse_csv(text, TODAY)
    assert not rows and len({e.line for e in errs}) == 6
    m = _msgs(errs)
    assert "masa depan" in m and "Simbol wajib" in m and "tidak dikenal" in m and "desimal" in m


def test_missing_required_columns_and_empty():
    assert parse_csv("simbol,harga\nA,1\n", TODAY)[1][0].message.startswith("Kolom wajib")
    assert parse_csv("", TODAY)[1][0].message == "File kosong"
    assert parse_csv(HDR, TODAY)[1][0].message == "Tidak ada baris data"


def test_leading_apostrophe_note_unescaped():
    rows, _ = parse_csv(HDR + "2025-01-01,SETOR,,,,,100,'=SUM(A1)\n", TODAY)
    assert rows[0].note == "=SUM(A1)"


def _events(csv_body, ids=None):
    rows, errs = parse_csv(HDR + csv_body, TODAY)
    assert not errs, errs
    return new_sim_events(rows, ids or {"AAPL": 1})


def test_simulate_ok_and_final_cash():
    ev, _ = _events(
        "2025-01-01,SETOR,,,,,1000,\n2025-01-02,BELI,AAPL,5,100,0,,\n2025-01-03,JUAL,AAPL,2,150,0,,\n"
    )
    errs, cash = simulate(ev)
    assert not errs and cash == D("800")  # 1000 - 500 + 300


def test_simulate_detects_cash_negative_and_order_matters():
    ev, _ = _events("2025-01-02,BELI,AAPL,5,100,0,,\n2025-01-01,SETOR,,,,,1000,\n")  # urutan baris tak penting
    errs, _ = simulate(ev)
    assert not errs
    ev, _ = _events("2025-01-01,BELI,AAPL,5,100,0,,\n2025-01-02,SETOR,,,,,1000,\n")  # setor terlambat
    errs, _ = simulate(ev)
    assert errs and "Saldo kas tidak cukup" in errs[0].message and errs[0].line == 2


def test_simulate_detects_oversell_by_date():
    ev, _ = _events("2025-01-01,SETOR,,,,,1000,\n2025-01-05,BELI,AAPL,5,10,0,,\n2025-01-03,JUAL,AAPL,1,10,0,,\n")
    errs, _ = simulate(ev)
    assert errs and "melebihi kepemilikan" in errs[0].message


def test_same_day_order_follows_file_order():
    ev, _ = _events("2025-01-01,SETOR,,,,,1000,\n2025-01-01,BELI,AAPL,5,10,0,,\n2025-01-01,JUAL,AAPL,5,12,0,,\n")
    errs, cash = simulate(ev)
    assert not errs and cash == D("1010")
    assert row_timestamp(date(2025, 1, 1), 0) < row_timestamp(date(2025, 1, 1), 1)


def test_import_checked_against_existing_ledger():
    t0 = datetime(2026, 5, 1, 3, 0, tzinfo=timezone.utc)
    existing = existing_sim_events(
        [NS(type="BUY", quantity=D("10"), price=D("100"), fee=D("0"), executed_at=t0, stock_id=1)],
        [NS(type="DEPOSIT", amount=D("1000"), occurred_at=datetime(2026, 4, 1, tzinfo=timezone.utc))],
        [],
    )
    assert simulate(existing)[0] == []
    # impor penarikan besar SEBELUM pembelian lama -> pembelian lama jadi tidak valid
    ev, _ = _events("2026-04-15,TARIK,,,,,900,\n")
    errs, _ = simulate(existing + ev)
    assert errs and errs[0].line is None and "sudah ada" in errs[0].message


def test_sell_fee_exceeding_value_rejected():
    rows, errs = parse_csv(HDR + "2025-01-01,JUAL,AAPL,1,10,50,,\n", TODAY)
    _, e2 = new_sim_events(rows, {"AAPL": 1})
    assert e2 and "Fee melebihi" in e2[0].message


def test_tags_parsed_normalized_and_validated():
    rows, errs = parse_csv(HDR.strip() + ",tags\n2025-01-03,BELI,AAPL,1,10,0,,alasan,Value|jangka panjang\n", TODAY)
    assert not errs and rows[0].tags == "value,jangka-panjang"
    rows, errs = parse_csv(HDR.strip() + ",tags\n2025-01-03,BELI,AAPL,1,10,0,,x,tag@salah\n", TODAY)
    assert not rows and "tidak valid" in errs[0].message
