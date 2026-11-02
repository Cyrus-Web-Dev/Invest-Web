"""Metrik target harga / stop loss (murni, tanpa DB)."""
from decimal import ROUND_HALF_UP, Decimal

from app.services.alerts import fmt_price

Q2 = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(Q2, rounding=ROUND_HALF_UP)


def _pct_change(to: Decimal | None, base: Decimal | None) -> Decimal | None:
    if to is None or base is None or base <= 0:
        return None
    return _q((to / base - 1) * 100)


def target_metrics(avg_cost: Decimal | None, price: Decimal | None,
                   target: Decimal | None, stop: Decimal | None) -> dict:
    """Semua persen dalam skala 100. progress: 0 = harga rata-rata, 100 = target (negatif jika di bawah modal)."""
    out: dict = dict(target_from_cost_pct=None, stop_from_cost_pct=None, to_target_pct=None,
                     to_stop_pct=None, progress_pct=None, risk_reward=None)
    if avg_cost is not None and avg_cost > 0:
        out["target_from_cost_pct"] = _pct_change(target, avg_cost)
        out["stop_from_cost_pct"] = _pct_change(stop, avg_cost)
        if target is not None and target > avg_cost and price is not None:
            out["progress_pct"] = _q((price - avg_cost) / (target - avg_cost) * 100)
        if target is not None and stop is not None and target > avg_cost > stop:
            out["risk_reward"] = _q((target - avg_cost) / (avg_cost - stop))
    out["to_target_pct"] = _pct_change(target, price)
    out["to_stop_pct"] = _pct_change(stop, price)
    return out


def target_message(symbol: str, target: Decimal, price: Decimal) -> tuple[str, str]:
    return (f"Target harga {symbol} tercapai",
            f"{symbol} mencapai {fmt_price(price)} (target {fmt_price(target)}). Pertimbangkan mengambil untung sesuai rencana Anda.")


def stop_message(symbol: str, stop: Decimal, price: Decimal) -> tuple[str, str]:
    return (f"Stop loss {symbol} tersentuh",
            f"{symbol} turun ke {fmt_price(price)} (stop loss {fmt_price(stop)}). Tinjau kembali posisi Anda sesuai rencana.")
