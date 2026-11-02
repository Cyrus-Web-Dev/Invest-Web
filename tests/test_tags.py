import pytest

from app.services.tags import join_tags, parse_tags, split_tags


def test_parse_normalizes():
    assert parse_tags(["Value", "jangka panjang", "dividend_yield", "value"]) == ["value", "jangka-panjang", "dividend-yield"]
    assert parse_tags("Value, Growth ,, ") == ["value", "growth"]
    assert parse_tags(None) == [] and parse_tags([]) == []


def test_parse_rejects_invalid():
    for bad in (["tag@salah"], ["-awal"], ["x" * 21], ["a", "b", "c", "d", "e", "f"]):
        with pytest.raises(ValueError):
            parse_tags(bad)


def test_join_split_roundtrip():
    assert join_tags(["a", "b"]) == "a,b" and join_tags([]) is None and join_tags(None) is None
    assert split_tags("a,b") == ["a", "b"] and split_tags(None) == [] and split_tags("") == []
