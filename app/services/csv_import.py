"""Parsing & validasi CSV impor (murni, tanpa DB) + simulasi buku besar kronologis."""
import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from app.services.metrics import ZERO, money
from app.services.tags import join_tags, parse_tags

MAX_ROWS = 5000
MIN_DATE = date(2000, 1, 1)
QTY_MAX, PRICE_MAX = Decimal("100000000"), Decimal("10000000")
FEE_MAX, AMOUNT_MAX = Decimal("1000000000000"), Decimal("10000000000000")
SYMBOL_RE = re.compile(r"^[A-Za-z0-9^][A-Za-z0-9.\-]*$")
_INT_RE, _DOT_RE, _COMMA_RE = re.compile(r"^\d+$"), re.compile(r"^\d+\.\d+$"), re.compile(r"^\d+,\d+$")

ALIASES = {
    "tanggal": "tanggal", "date": "tanggal", "tgl": "tanggal",
    "jenis": "jenis", "type": "jenis", "tipe": "jenis",
    "simbol": "simbol", "symbol": "simbol", "kode": "simbol", "ticker": "simbol",
    "jumlah": "jumlah", "qty": "jumlah", "quantity": "jumlah", "lembar": "jumlah",
    "harga": "harga", "price": "harga",
    "fee": "fee", "biaya": "fee", "komisi": "fee",
    "nominal": "nominal", "amount": "nominal",
    "catatan": "catatan", "note": "catatan", "notes": "catatan",
    "tags": "tags", "tag": "tags", "label": "tags",
}
TYPE_MAP = {
    "BUY": "BUY", "BELI": "BUY", "B": "BUY",
    "SELL": "SELL", "JUAL": "SELL", "S": "SELL",
    "DEPOSIT": "DEPOSIT", "SETOR": "DEPOSIT", "SETORAN": "DEPOSIT",
    "WITHDRAW": "WITHDRAW", "TARIK": "WITHDRAW", "PENARIKAN": "WITHDRAW",
    "DIVIDEND": "DIVIDEND", "DIVIDEN": "DIVIDEND",
}

TEMPLATE_CSV = (
    "tanggal,jenis,simbol,jumlah,harga,fee,nominal,catatan,tags\n"
    "2025-01-02,SETOR,,,,,10000000,Modal awal,\n"
    "2025-01-03,BELI,BBCA.JK,100,9000,2500,,Beli awal,value|jangka-panjang\n"
    "2025-02-10,JUAL,BBCA.JK,50,9500,1800,,Ambil untung sebagian,profit-taking\n"
    "2025-03-15,DIVIDEN,BBCA.JK,,,,150000,Dividen interim,\n"
    "2025-04-01,TARIK,,,,,500000,,\n"
)


@dataclass(frozen=True)
class ImportRow:
    line: int
    day: date
    kind: str            # BUY | SELL | DEPOSIT | WITHDRAW | DIVIDEND
    symbol: str | None
    quantity: Decimal
    price: Decimal
    fee: Decimal
    amount: Decimal
    note: str | None
    tags: str | None = None


@dataclass(frozen=True)
class RowError:
    line: int | None
    message: str


def parse_decimal(s: str) -> Decimal | None:
    """Ketat agar tidak salah tafsir: hanya 1000, 1000.5, atau 1000,5 (tanpa pemisah ribuan)."""
    s = s.strip()
    if _INT_RE.match(s) or _DOT_RE.match(s):
        return Decimal(s)
    if _COMMA_RE.match(s):
        return Decimal(s.replace(",", "."))
    return None


def _num(raw: str, label: str, max_dp: int, upper: Decimal, *, allow_zero: bool, errs: list[str]) -> Decimal | None:
    d = parse_decimal(raw)
    if d is None:
        errs.append(f"{label} '{raw}' tidak valid (angka saja; hapus pemisah ribuan; desimal pakai titik atau koma)")
        return None
    if -d.as_tuple().exponent > max_dp:  # type: ignore[operator]
        errs.append(f"{label} maksimal {max_dp} angka desimal")
        return None
    if d < 0 or (d == 0 and not allow_zero) or d > upper:
        errs.append(f"{label} harus {'≥' if allow_zero else '>'} 0 dan ≤ {upper:,}".replace(",", "."))
        return None
    return d


def _parse_date(s: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _cell(raw: list[str], idx: dict[str, int], name: str) -> str:
    i = idx.get(name)
    return raw[i].strip() if i is not None and i < len(raw) else ""


def _parse_row(raw: list[str], idx: dict[str, int], line: int, today: date) -> tuple[ImportRow | None, list[str]]:
    errs: list[str] = []
    kind = TYPE_MAP.get(_cell(raw, idx, "jenis").upper())
    if kind is None:
        errs.append(f"Jenis '{_cell(raw, idx, 'jenis')}' tidak dikenal (gunakan BELI, JUAL, SETOR, TARIK, atau DIVIDEN)")
    day = _parse_date(_cell(raw, idx, "tanggal"))
    if day is None:
        errs.append(f"Tanggal '{_cell(raw, idx, 'tanggal')}' tidak valid (gunakan YYYY-MM-DD atau DD/MM/YYYY)")
    elif day > today:
        errs.append("Tanggal tidak boleh di masa depan")
    elif day < MIN_DATE:
        errs.append("Tanggal terlalu lama (minimal 2000-01-01)")

    symbol = _cell(raw, idx, "simbol").upper() or None
    if kind in ("BUY", "SELL", "DIVIDEND"):
        if symbol is None:
            errs.append("Simbol wajib diisi")
        elif not SYMBOL_RE.match(symbol) or len(symbol) > 20:
            errs.append(f"Simbol '{symbol}' tidak valid")

    qty = price = fee = amount = ZERO
    if kind in ("BUY", "SELL"):
        q = _num(_cell(raw, idx, "jumlah"), "Jumlah", 4, QTY_MAX, allow_zero=False, errs=errs)
        p = _num(_cell(raw, idx, "harga"), "Harga", 4, PRICE_MAX, allow_zero=False, errs=errs)
        fee_raw = _cell(raw, idx, "fee") or "0"
        f = _num(fee_raw, "Fee", 4, FEE_MAX, allow_zero=True, errs=errs)
        if q is not None and p is not None and f is not None:
            qty, price, fee = q, p, f
    elif kind in ("DEPOSIT", "WITHDRAW", "DIVIDEND"):
        n = _num(_cell(raw, idx, "nominal"), "Nominal", 2, AMOUNT_MAX, allow_zero=False, errs=errs)
        if n is not None:
            amount = n

    note = _cell(raw, idx, "catatan") or None
    if note and len(note) > 1 and note[0] == "'" and note[1] in "=+-@":
        note = note[1:]  # kebalikan dari perlindungan formula saat ekspor
    if note and len(note) > 255:
        errs.append("Catatan maksimal 255 karakter")
    tags_str = None
    raw_tags = _cell(raw, idx, "tags")
    if raw_tags and kind in ("BUY", "SELL"):
        try:
            tags_str = join_tags(parse_tags(raw_tags.split("|")))
        except ValueError as e:
            errs.append(str(e))

    if errs or kind is None or day is None:
        return None, errs
    return ImportRow(line, day, kind, symbol, qty, price, fee, amount, note, tags_str), []


def parse_csv(text: str, today: date) -> tuple[list[ImportRow], list[RowError]]:
    text = text.lstrip("\ufeff")
    first = next((ln for ln in text.splitlines() if ln.strip()), None)
    if first is None:
        return [], [RowError(None, "File kosong")]
    delim = max((",", ";", "\t"), key=first.count)
    if first.count(delim) == 0:
        delim = ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)

    idx: dict[str, int] = {}
    header_seen = False
    rows: list[ImportRow] = []
    errors: list[RowError] = []
    n_data = 0
    for raw in reader:
        if not any(c.strip() for c in raw):
            continue
        if not header_seen:
            header_seen = True
            for i, h in enumerate(raw):
                key = ALIASES.get(h.strip().lower())
                if key and key not in idx:
                    idx[key] = i
            missing = [k for k in ("tanggal", "jenis") if k not in idx]
            if missing:
                return [], [RowError(None, f"Kolom wajib tidak ditemukan: {', '.join(missing)}. Gunakan templat yang disediakan.")]
            continue
        n_data += 1
        if n_data > MAX_ROWS:
            errors.append(RowError(None, f"Maksimal {MAX_ROWS} baris per file"))
            break
        row, errs = _parse_row(raw, idx, reader.line_num, today)
        errors.extend(RowError(reader.line_num, m) for m in errs)
        if row is not None:
            rows.append(row)
    if not rows and not errors:
        errors.append(RowError(None, "Tidak ada baris data"))
    return rows, errors


# ---------------- simulasi buku besar ----------------
@dataclass(frozen=True)
class SimEvent:
    at: datetime
    cash_delta: Decimal
    stock_id: int | None
    qty_delta: Decimal
    line: int | None  # nomor baris CSV; None = transaksi yang sudah ada


def row_timestamp(day: date, index: int) -> datetime:
    """Awal hari (UTC) + indeks baris dalam milidetik: urutan antar-baris pada hari yang sama terjaga."""
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(milliseconds=index)


def row_cash_delta(r: ImportRow) -> Decimal:
    if r.kind == "BUY":
        return -money(r.quantity * r.price + r.fee)
    if r.kind == "SELL":
        return money(r.quantity * r.price - r.fee)
    if r.kind == "WITHDRAW":
        return -r.amount
    return r.amount  # DEPOSIT, DIVIDEND


def new_sim_events(rows: list[ImportRow], stock_ids: dict[str, int]) -> tuple[list[SimEvent], list[RowError]]:
    events: list[SimEvent] = []
    errors: list[RowError] = []
    for i, r in enumerate(rows):
        delta = row_cash_delta(r)
        if r.kind == "SELL" and delta < 0:
            errors.append(RowError(r.line, "Fee melebihi nilai penjualan"))
            continue
        sid = stock_ids.get(r.symbol) if r.symbol else None
        qty = r.quantity if r.kind == "BUY" else -r.quantity if r.kind == "SELL" else ZERO
        events.append(SimEvent(row_timestamp(r.day, i), delta, sid, qty, r.line))
    return events, errors


def existing_sim_events(transactions, cash_flows, dividends, mark=None) -> list[SimEvent]:
    """Dari baris DB (atau objek bertipe sama) ke peristiwa simulasi, berurutan deterministik.
    Pada waktu yang persis sama: setoran/dividen dulu, lalu transaksi saham (urut id), lalu penarikan.
    mark=("tx"|"cash"|"div", id) menandai peristiwa yang sedang diubah/ditambah (line=1)."""
    items: list[tuple[datetime, int, int, SimEvent]] = []
    for t in transactions:
        tid = getattr(t, "id", 0)
        line = 1 if mark == ("tx", tid) else None
        gross = t.quantity * t.price
        if t.type == "BUY":
            ev = SimEvent(t.executed_at, -money(gross + t.fee), t.stock_id, t.quantity, line)
        else:
            ev = SimEvent(t.executed_at, money(gross - t.fee), t.stock_id, -t.quantity, line)
        items.append((t.executed_at, 1, tid, ev))
    for c in cash_flows:
        cid = getattr(c, "id", 0)
        line = 1 if mark == ("cash", cid) else None
        if c.type == "DEPOSIT":
            items.append((c.occurred_at, 0, cid, SimEvent(c.occurred_at, c.amount, None, ZERO, line)))
        else:
            items.append((c.occurred_at, 2, cid, SimEvent(c.occurred_at, -c.amount, None, ZERO, line)))
    for dv in dividends:
        did = getattr(dv, "id", 0)
        line = 1 if mark == ("div", did) else None
        at = datetime.combine(dv.paid_on, time(12, 0), tzinfo=timezone.utc)
        items.append((at, 0, did, SimEvent(at, dv.amount, None, ZERO, line)))
    items.sort(key=lambda x: (x[0], x[1], x[2]))
    return [x[3] for x in items]


def simulate(events: list[SimEvent], max_errors: int = 30) -> tuple[list[RowError], Decimal]:
    """Putar ulang seluruh buku besar secara kronologis. Kembalikan pelanggaran (kas negatif /
    jual melebihi kepemilikan) dan saldo kas akhir. Pelanggaran dilaporkan saat BARU terjadi."""
    ordered = sorted(enumerate(events), key=lambda t: (t[1].at, t[0]))
    cash = ZERO
    held: dict[int, Decimal] = {}
    errors: list[RowError] = []
    cash_bad = False
    stock_bad: set[int] = set()
    for _, e in ordered:
        cash += e.cash_delta
        if cash < 0 and not cash_bad:
            cash_bad = True
            msg = (f"Saldo kas tidak cukup pada {e.at.date()}. Tambahkan setoran modal sebelum tanggal ini."
                   if e.line else f"Transaksi yang sudah ada pada {e.at.date()} menjadi tidak valid (saldo kas negatif)")
            errors.append(RowError(e.line, msg))
        elif cash >= 0:
            cash_bad = False
        if e.stock_id is not None and e.qty_delta != 0:
            q = held.get(e.stock_id, ZERO) + e.qty_delta
            held[e.stock_id] = q
            if q < 0 and e.stock_id not in stock_bad:
                stock_bad.add(e.stock_id)
                errors.append(RowError(e.line, f"Jumlah jual melebihi kepemilikan pada {e.at.date()}"
                                       if e.line else f"Transaksi yang sudah ada pada {e.at.date()} menjadi tidak valid (jual melebihi kepemilikan)"))
            elif q >= 0:
                stock_bad.discard(e.stock_id)
        if len(errors) >= max_errors:
            break
    return errors, cash
