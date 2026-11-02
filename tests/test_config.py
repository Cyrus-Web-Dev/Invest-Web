import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_weak_secret_rejected():
    for bad in ("pendek", "ganti_dengan_string_acak_panjang_sekali_32+"):
        with pytest.raises(ValidationError):
            Settings(database_url="postgresql+asyncpg://u:p@h/d", secret_key=bad, _env_file=None)


def test_strong_secret_accepted():
    s = Settings(database_url="postgresql+asyncpg://u:p@h/d", secret_key="x" * 40, _env_file=None)
    assert s.secret_key == "x" * 40
