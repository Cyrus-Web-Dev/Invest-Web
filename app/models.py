"""Skema database. Semua nilai uang memakai Numeric (BUKAN float) agar presisi."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric,
    String, UniqueConstraint, false, func, true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("cash_balance >= 0", name="ck_users_cash_nonneg"),)


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # mis. BBCA.JK, AAPL
    name: Mapped[str] = mapped_column(String(160))
    exchange: Mapped[str] = mapped_column(String(20))  # IDX, NASDAQ, ...
    currency: Mapped[str] = mapped_column(String(3), default="IDR")
    sector: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(default=True)
    kind: Mapped[str] = mapped_column(String(10), default="STOCK", server_default="STOCK")  # STOCK | INDEX

    __table_args__ = (CheckConstraint("kind IN ('STOCK','INDEX')", name="ck_stock_kind"),)


class Transaction(Base):
    """Buku besar transaksi. Posisi (holding) selalu dihitung dari tabel ini."""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    type: Mapped[str] = mapped_column(String(4))  # BUY / SELL
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[str | None] = mapped_column(String(120))  # tag dipisah koma, mis. 'value,dividend'

    stock: Mapped[Stock] = relationship()

    __table_args__ = (
        CheckConstraint("type IN ('BUY','SELL')", name="ck_tx_type"),
        CheckConstraint("quantity > 0", name="ck_tx_qty_pos"),
        CheckConstraint("price >= 0 AND fee >= 0", name="ck_tx_price_fee"),
        Index("ix_tx_user_time", "user_id", "executed_at"),
    )


class CashFlow(Base):
    """Setoran/penarikan modal. Dibutuhkan untuk grafik Net Worth vs Modal Disetor."""
    __tablename__ = "cash_flows"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(10))  # DEPOSIT / WITHDRAW
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("type IN ('DEPOSIT','WITHDRAW')", name="ck_cf_type"),
        CheckConstraint("amount > 0", name="ck_cf_amount_pos"),
    )


class Dividend(Base):
    __tablename__ = "dividends"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    paid_on: Mapped[date] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_div_amount_pos"),
        Index("ix_div_user_date", "user_id", "paid_on"),
    )


class HistoricalPrice(Base):
    """Harga harian OHLCV. PK komposit (stock_id, trade_date) mencegah duplikat saat fetch ulang."""
    __tablename__ = "historical_prices"

    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    volume: Mapped[int] = mapped_column(BigInteger, default=0)


class PortfolioSnapshot(Base):
    """Foto harian kekayaan bersih per user, agar line chart tidak dihitung ulang dari nol."""
    __tablename__ = "portfolio_snapshots"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    snap_date: Mapped[date] = mapped_column(Date, primary_key=True)
    net_worth: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    invested_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 2))


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))

    __table_args__ = (UniqueConstraint("user_id", "stock_id", name="uq_watchlist_user_stock"),)


class PriceAlert(Base):
    """Alert harga: aktif sampai terpicu satu kali, lalu dinonaktifkan."""
    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    direction: Mapped[str] = mapped_column(String(5))  # ABOVE (naik >=) / BELOW (turun <=)
    target_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    triggered_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))

    __table_args__ = (
        CheckConstraint("direction IN ('ABOVE','BELOW')", name="ck_alert_direction"),
        CheckConstraint("target_price > 0", name="ck_alert_target_pos"),
        Index("ix_alert_active_stock", "is_active", "stock_id"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_notif_user_created", "user_id", "created_at"),)


class ImportBatch(Base):
    """Jejak impor CSV. Hash file yang sama tidak boleh diimpor dua kali per user."""
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    file_sha256: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str | None] = mapped_column(String(255))
    row_count: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "file_sha256", name="uq_import_user_hash"),)


class PositionTarget(Base):
    """Target harga & stop loss per saham untuk satu user. Masing-masing memicu notifikasi sekali."""
    __tablename__ = "position_targets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    note: Mapped[str | None] = mapped_column(String(255))
    target_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "stock_id", name="uq_target_user_stock"),
        CheckConstraint("target_price IS NULL OR target_price > 0", name="ck_target_pos"),
        CheckConstraint("stop_price IS NULL OR stop_price > 0", name="ck_stop_pos"),
        CheckConstraint("target_price IS NULL OR stop_price IS NULL OR stop_price < target_price", name="ck_stop_below_target"),
        CheckConstraint("target_price IS NOT NULL OR stop_price IS NOT NULL", name="ck_target_or_stop"),
    )
