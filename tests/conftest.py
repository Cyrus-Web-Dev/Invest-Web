import os

# Harus di-set SEBELUM modul app diimpor (Settings dibaca saat import).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/test")
os.environ.setdefault("SECRET_KEY", "kunci-khusus-untuk-test-minimal-32-karakter-ok")
