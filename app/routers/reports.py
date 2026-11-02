from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import (
    AnnualReportOut, DividendLineOut, ReportTotalsOut, SaleLineOut, StockYearOut, YearEndPositionOut,
)
from app.services.export_format import sanitize_cell, to_csv
from app.services.report_pdf import build_annual_pdf
from app.services.reports import closing_prices, load_report_inputs
from app.services.tax_report import AnnualReport, available_years, build_annual_report, positions_at

router = APIRouter(prefix="/reports", tags=["reports"])


def _today():
    return datetime.now(timezone.utc).date()


async def _report(db: AsyncSession, user: User, year: int) -> AnnualReport:
    today = _today()
    trades, divs = await load_report_inputs(db, user.id)
    as_of = min(date(year, 12, 31), today)
    try:
        symbols = [s for s, p in positions_at(trades, as_of).items() if p.quantity > 0]
        prices = await closing_prices(db, symbols, as_of)
        return build_annual_report(trades, divs, prices, year, today)
    except ValueError as e:   # buku besar tidak konsisten (seharusnya tidak pernah terjadi)
        raise HTTPException(409, str(e))


@router.get("/years", response_model=list[int])
async def report_years(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    trades, divs = await load_report_inputs(db, user.id)
    return available_years(trades, divs, _today())


@router.get("/annual", response_model=AnnualReportOut)
async def annual_report(
    year: int = Query(ge=2000, le=2100), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    r = await _report(db, user, year)
    return AnnualReportOut(
        year=r.year, as_of=r.as_of, generated_on=r.generated_on, totals=ReportTotalsOut(**r.totals.__dict__),
        by_stock=[StockYearOut(**s.__dict__) for s in r.by_stock], sales=[SaleLineOut(**s.__dict__) for s in r.sales],
        dividends=[DividendLineOut(**d.__dict__) for d in r.dividends],
        positions=[YearEndPositionOut(**p.__dict__) for p in r.positions], notes=r.notes,
    )


@router.get("/annual.pdf")
async def annual_pdf(
    year: int = Query(ge=2000, le=2100), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    r = await _report(db, user, year)
    try:
        content = build_annual_pdf(r, user.full_name, demo=user.is_demo)
    except ImportError:
        raise HTTPException(501, "Pustaka reportlab belum terpasang (jalankan ulang build Docker)")
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="stockfolio-laporan-{year}.pdf"'})


@router.get("/realized.csv")
async def realized_csv(
    year: int = Query(ge=2000, le=2100), sep: str = Query(default=",", pattern="^[,;]$"),
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    r = await _report(db, user, year)
    headers = ["tanggal", "simbol", "jumlah", "nilai_jual_bruto", "fee_jual", "nilai_jual_bersih", "harga_perolehan", "laba_rugi_terealisasi"]
    rows = [[str(s.day), sanitize_cell(s.symbol), format(s.quantity.normalize(), "f"), str(s.gross), str(s.fee),
             str(s.net), str(s.cost_basis), str(s.realized)] for s in r.sales]
    return Response(content=to_csv(headers, rows, sep).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="stockfolio-penjualan-{year}.csv"'})
