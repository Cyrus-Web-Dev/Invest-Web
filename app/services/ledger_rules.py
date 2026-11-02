"""Aturan penyuntingan buku besar (murni, tanpa DB)."""
from datetime import date, datetime, time, timezone
from decimal import Decimal

from app.services.csv_import import existing_sim_events, simulate
from app.services.metrics import money


class LedgerRuleError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def at_for(day: date, original: datetime | None, now: datetime) -> datetime:
    """Waktu transaksi untuk sebuah tanggal. Tanggal tak berubah -> waktu asli dipertahankan;
    hari ini -> sekarang; lainnya -> tengah hari UTC (aman dari pergeseran zona waktu)."""
    today = now.astimezone(timezone.utc).date()
    if day > today:
        raise LedgerRuleError("Tanggal tidak boleh di masa depan")
    if original is not None and original.astimezone(timezone.utc).date() == day:
        return original
    if day == today:
        return now
    return datetime.combine(day, time(12, 0), tzinfo=timezone.utc)


def check_sell_fee(kind: str, quantity: Decimal, price: Decimal, fee: Decimal) -> None:
    if kind == "SELL" and money(quantity * price - fee) < 0:
        raise LedgerRuleError("Fee melebihi nilai penjualan")


def check_change(old: tuple, new: tuple, balance: Decimal, mark) -> Decimal:
    """old/new = (transaksi, arus kas, dividen). Putar ulang seluruh buku besar secara kronologis;
    tolak bila kas negatif / jual melebihi kepemilikan di titik waktu mana pun.
    Return saldo kas baru = saldo sekarang + selisih efek ke kas."""
    old_errs, old_cash = simulate(existing_sim_events(*old))
    if old_errs or money(old_cash) != money(balance):
        raise LedgerRuleError(
            "Buku besar akun tidak cocok dengan saldo kas saat ini; perubahan dibatalkan demi keamanan data", 409
        )
    errs, new_cash = simulate(existing_sim_events(*new, mark=mark))
    if errs:
        raise LedgerRuleError(f"Perubahan ditolak: {errs[0].message}")
    return balance + (new_cash - old_cash)
