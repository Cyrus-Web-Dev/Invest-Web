from datetime import date
from decimal import Decimal as D

import pytest

from app.services.price_providers.base import decode_quote, encode_quote, rows_to_bars

NAN = float("nan")


def test_rows_to_bars_drops_bad_rows_and_sorts():
    rows = [
        (date(2026, 1, 5), 10.0, 12.0, 9.0, 11.0, 500.0),
        (date(2026, 1, 2), 100.0, 105.0, 99.0, 104.5, 1000.0),
        (date(2026, 1, 3), NAN, 105.0, 99.0, 104.5, 1000.0),    # NaN -> dibuang
        (date(2026, 1, 4), 10.0, 8.0, 9.0, 9.0, 10.0),          # high < low -> dibuang
        (date(2026, 1, 6), 1.0, 1.0, 1.0, 0.0, 10.0),           # close <= 0 -> dibuang
    ]
    bars = rows_to_bars(rows)
    assert [b.trade_date for b in bars] == [date(2026, 1, 2), date(2026, 1, 5)]
    assert bars[0].close == D("104.5")
    assert bars[0].volume == 1000


def test_nan_volume_becomes_zero():
    bars = rows_to_bars([(date(2026, 1, 2), 1.0, 2.0, 1.0, 1.5, NAN)])
    assert bars[0].volume == 0


def test_duplicate_dates_merged():
    d = date(2026, 1, 2)
    bars = rows_to_bars([(d, 1.0, 2.0, 1.0, 1.5, 1.0), (d, 1.0, 3.0, 1.0, 2.5, 2.0)])
    assert len(bars) == 1 and bars[0].close == D("2.5")


def test_empty_rows():
    assert rows_to_bars([]) == []


def test_quote_codec_roundtrip():
    raw = encode_quote(D("9250.5"), date(2026, 10, 30))
    assert decode_quote(raw) == (D("9250.5"), date(2026, 10, 30))


@pytest.mark.parametrize("raw", ["bukan json", "{}", '{"p": "abc", "d": "2026-01-01"}', '{"p": "1", "d": "x"}'])
def test_corrupt_cache_raises_valueerror(raw):
    with pytest.raises(ValueError):
        decode_quote(raw)
