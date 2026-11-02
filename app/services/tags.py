"""Normalisasi tag transaksi (murni)."""
import re

TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,19}$")
MAX_TAGS = 5


def parse_tags(raw) -> list[str]:
    """Terima list atau teks dipisah koma. Huruf kecil, spasi/garis-bawah jadi '-', duplikat dibuang.
    Raise ValueError jika tidak valid (otomatis menjadi 422 di API)."""
    if raw is None:
        return []
    items = raw.split(",") if isinstance(raw, str) else list(raw)
    out: list[str] = []
    for it in items:
        t = re.sub(r"-{2,}", "-", str(it).strip().lower().replace(" ", "-").replace("_", "-"))
        if not t:
            continue
        if not TAG_RE.match(t):
            raise ValueError(f"Tag '{it}' tidak valid (huruf kecil/angka/tanda hubung, maks. 20 karakter)")
        if t not in out:
            out.append(t)
    if len(out) > MAX_TAGS:
        raise ValueError(f"Maksimal {MAX_TAGS} tag per transaksi")
    return out


def join_tags(tags: list[str] | None) -> str | None:
    return ",".join(tags) if tags else None


def split_tags(s: str | None) -> list[str]:
    return [t for t in s.split(",") if t] if s else []
