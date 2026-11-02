"""Logika murni untuk alert harga & pantauan (tanpa DB)."""
from decimal import ROUND_HALF_UP, Decimal


def is_triggered(direction: str, target: Decimal, price: Decimal) -> bool:
    if direction == "ABOVE":
        return price >= target
    if direction == "BELOW":
        return price <= target
    return False


def fmt_price(d: Decimal) -> str:
    """12345.5 -> '12.345,50' (format Indonesia)."""
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{q:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")


def change_pct(last: Decimal, prev: Decimal) -> Decimal | None:
    if prev <= 0:
        return None
    return ((last - prev) / prev * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def alert_message(symbol: str, direction: str, target: Decimal, price: Decimal) -> tuple[str, str]:
    verb = "naik mencapai" if direction == "ABOVE" else "turun hingga"
    return (
        f"Alert harga {symbol}",
        f"{symbol} {verb} {fmt_price(target)}. Harga terakhir: {fmt_price(price)}.",
    )
