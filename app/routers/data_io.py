import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import ImportErrorOut, ImportReportOut
from app.services.analytics import load_portfolio
from app.services.csv_import import TEMPLATE_CSV, parse_csv
from app.services.export_format import HOLDING_HEADERS, LEDGER_HEADERS, to_csv
from app.services.exporting import build_xlsx, holdings_rows, load_ledger
from app.services.import_runner import ImportReport, run_import

router = APIRouter(tags=["import-export"])
MAX_BYTES = 1_000_000  # 1 MB
MAX_ERRORS_SHOWN = 30


def _today():
    return datetime.now(timezone.utc).date()


def _csv_response(text: str, filename: str) -> Response:
    return Response(
        content=text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _report_out(rep: ImportReport) -> ImportReportOut:
    shown = rep.errors[:MAX_ERRORS_SHOWN]
    return ImportReportOut(
        ok=rep.ok, committed=rep.committed, duplicate=rep.duplicate, total_rows=rep.total_rows,
        counts=rep.counts, date_from=rep.date_from, date_to=rep.date_to, cash_effect=rep.cash_effect,
        resulting_cash=rep.resulting_cash,
        errors=[ImportErrorOut(line=e.line, message=e.message) for e in shown],
        more_errors=max(0, len(rep.errors) - len(shown)),
    )


@router.get("/portfolio/import/template.csv")
async def import_template(_: User = Depends(get_current_user)):
    return _csv_response("\ufeff" + TEMPLATE_CSV, "templat-impor-stockfolio.csv")


@router.post("/portfolio/import", response_model=ImportReportOut)
async def import_csv(
    file: UploadFile = File(...),
    dry_run: bool = Query(default=True, description="true = hanya periksa; false = impor sungguhan"),
    force: bool = Query(default=False, description="true = abaikan penolakan file duplikat"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Ukuran file maksimal 1 MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "File harus berencoding UTF-8 (simpan ulang sebagai CSV UTF-8)")

    rows, parse_errors = parse_csv(text, _today())
    if parse_errors:
        rep = ImportReport(total_rows=len(rows), errors=parse_errors)
        return _report_out(rep)
    sha = hashlib.sha256(data).hexdigest()
    rep = await run_import(db, user.id, rows, sha, file.filename, dry_run, force)
    return _report_out(rep)


@router.get("/export/transactions.csv")
async def export_transactions(
    sep: str = Query(default=",", pattern="^[,;]$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    text = to_csv(LEDGER_HEADERS, await load_ledger(db, user.id), sep)
    return _csv_response(text, f"stockfolio-transaksi-{_today()}.csv")


@router.get("/export/holdings.csv")
async def export_holdings(
    sep: str = Query(default=",", pattern="^[,;]$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    view = await load_portfolio(db, user)
    return _csv_response(to_csv(HOLDING_HEADERS, holdings_rows(view), sep), f"stockfolio-posisi-{_today()}.csv")


@router.get("/export/report.xlsx")
async def export_report(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    view = await load_portfolio(db, user)
    ledger = await load_ledger(db, user.id)
    try:
        content = build_xlsx(view, ledger, _today())
    except ImportError:
        raise HTTPException(501, "Pustaka openpyxl belum terpasang (jalankan ulang build Docker)")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="stockfolio-laporan-{_today()}.xlsx"'},
    )
