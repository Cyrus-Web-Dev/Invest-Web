import jwt
import pytest

from app.core.security import (
    create_access_token, decode_access_token, hash_password, verify_password,
)


def test_password_roundtrip():
    h = hash_password("rahasia123")
    assert h != "rahasia123"
    assert verify_password("rahasia123", h)
    assert not verify_password("salah", h)
    assert not verify_password("apa-saja", "bukan-hash-valid")


def test_token_roundtrip():
    token = create_access_token(42)
    assert decode_access_token(token)["sub"] == "42"


def test_tampered_token_rejected():
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(create_access_token(1) + "x")
