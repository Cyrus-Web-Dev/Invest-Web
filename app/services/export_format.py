"""Format ekspor (murni). Kolom ledger SAMA dengan format impor agar bisa bolak-balik."""
import csv
import io
from decimal import Decimal

LEDGER_HEADERS = ["tanggal", "jenis", "simbol", "jumlah", "harga", "fee", "nominal", "catatan", "tags"]
HOLDING_HEADERS = [
    "simbol", "sektor", "lembar", "harga_rata_rata", "biaya_total", "harga_terakhir",
    "nilai_pasar", "untung_rugi", "untung_rugi_persen", "realized_pl", "sumber_harga",
]
KIND_LABEL = {"BUY": "BELI", "SELL": "JUAL", "DEPOSIT": "SETOR", "WITHDRAW": "TARIK", "DIVIDEND": "DIVIDEN"}


def sanitize_cell(v: str) -> str:
    """Cegah formula injection di Excel/Sheets: teks yang diawali = + - @ diberi apostrof."""
    return "'" + v if v and v[0] in "=+-@\t\r" else v


def fmt_num(d: Decimal | None) -> str:
    if d is None:
        return ""
    return format(d.normalize(), "f")


def to_csv(headers: list[str], rows: list[list[str]], sep: str = ",") -> str:
    """CSV UTF-8 dengan BOM (Excel membacanya benar). sep ';' untuk Excel berlokal Indonesia."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=sep, lineterminator="\r\n")
    w.writerow(headers)
    w.writerows(rows)
    return "\ufeff" + buf.getvalue()


def ledger_row(kind, day, symbol, qty, price, fee, nominal, note, tags=None) -> list[str]:
    return [
        day.isoformat(), KIND_LABEL[kind], sanitize_cell(symbol or ""),
        fmt_num(qty), fmt_num(price), fmt_num(fee), fmt_num(nominal), sanitize_cell(note or ""),
        "|".join(tags or []),
    ]
