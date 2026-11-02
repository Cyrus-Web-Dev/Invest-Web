from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Stockfolio"
    database_url: str
    redis_url: str = "redis://redis:6379/0"
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Keamanan
    allow_registration: bool = True   # set false setelah akun Anda dibuat (bila di-deploy publik)
    enable_docs: bool = True          # set false di produksi (menyembunyikan /docs)
    demo_mode: bool = False           # true hanya pada stack demo (data simulasi, tanpa penyedia harga nyata)

    # Harga saham
    price_cache_ttl_seconds: int = 300
    sync_cooldown_seconds: int = 60
    history_backfill_days: int = 365
    scheduler_enabled: bool = True    # jalankan hanya di 1 proses/worker

    @field_validator("secret_key")
    @classmethod
    def _strong_secret(cls, v: str) -> str:
        if len(v) < 32 or v.lower().startswith("ganti"):
            raise ValueError(
                "SECRET_KEY terlalu lemah (minimal 32 karakter dan bukan nilai contoh). "
                'Buat dengan: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return v


settings = Settings()
