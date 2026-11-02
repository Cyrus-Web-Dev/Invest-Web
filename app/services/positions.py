"""Hitung posisi dengan metode harga rata-rata bergerak (moving average cost)."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

ZERO = Decimal("0")


@dataclass(frozen=True)
class Trade:
    type: str  # "BUY" / "SELL"
    quantity: Decimal
    price: Decimal
    fee: Decimal = ZERO


@dataclass
class Position:
    quantity: Decimal = ZERO
    total_cost: Decimal = ZERO
    realized_pl: Decimal = ZERO

    @property
    def avg_cost(self) -> Decimal:
        return self.total_cost / self.quantity if self.quantity > 0 else ZERO


def compute_position(trades: Iterable[Trade]) -> Position:
    """Trades HARUS berurutan secara kronologis. Raise ValueError jika jual melebihi kepemilikan."""
    pos = Position()
    for t in trades:
        if t.type == "BUY":
            pos.total_cost += t.quantity * t.price + t.fee
            pos.quantity += t.quantity
        elif t.type == "SELL":
            if t.quantity > pos.quantity:
                raise ValueError("Jual melebihi jumlah yang dimiliki")
            # Jual habis: pakai total_cost langsung agar tidak ada sisa pembulatan.
            basis = pos.total_cost if t.quantity == pos.quantity else pos.avg_cost * t.quantity
            pos.realized_pl += t.quantity * t.price - t.fee - basis
            pos.total_cost -= basis
            pos.quantity -= t.quantity
        else:
            raise ValueError(f"Tipe transaksi tidak dikenal: {t.type}")
    return pos
