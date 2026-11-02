import re

from app.seed.data import CATALOG

SYMBOL_RE = re.compile(r"^[A-Za-z0-9^][A-Za-z0-9.\-]*$")  # sama dengan validasi StockIn


def test_symbols_unique_and_valid():
    symbols = [c["symbol"] for c in CATALOG]
    assert len(symbols) == len(set(symbols))
    assert all(SYMBOL_RE.match(s) and len(s) <= 20 for s in symbols)


def test_fields_consistent():
    for c in CATALOG:
        assert c["name"] and len(c["name"]) <= 160
        assert len(c["currency"]) == 3 and c["currency"].isupper()
        assert c["exchange"].isupper() and len(c["exchange"]) <= 20
        assert c["is_active"] is True
        if c["exchange"] == "IDX":
            assert c["symbol"].endswith(".JK") and c["currency"] == "IDR"
        else:
            assert not c["symbol"].endswith(".JK") and c["currency"] == "USD"


def test_catalog_size():
    assert sum(c["exchange"] == "IDX" for c in CATALOG) == 30
    assert len(CATALOG) == 40
