import pytest

pytest.importorskip("reportlab")

from datetime import date  # noqa: E402

from app.services.report_pdf import build_annual_pdf  # noqa: E402
from app.services.tax_report import build_annual_report  # noqa: E402
from tests.test_tax_report import DIVS, TODAY, TRADES  # noqa: E402


def test_pdf_is_valid_and_nonempty():
    r = build_annual_report(TRADES, DIVS, {"BBB": (__import__("decimal").Decimal("1600"), date(2026, 10, 30))}, 2026, TODAY)
    data = build_annual_pdf(r, "Uji Coba", demo=True)
    assert data.startswith(b"%PDF") and data.rstrip().endswith(b"%%EOF") and len(data) > 2500


def test_pdf_handles_empty_year():
    r = build_annual_report([], [], {}, 2030, TODAY)
    assert build_annual_pdf(r, "Kosong").startswith(b"%PDF")
