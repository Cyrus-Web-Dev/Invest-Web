from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import Dividend, HistoricalPrice, Stock, Transaction, User
from app.seed.catalog import ensure_benchmarks
from app.schemas import (
    AllocationOut, AllocationRowOut, BenchmarkCompareOut, BenchmarkOut, BenchmarkPointOut,
    AttributionOut, CalendarMonthOut, ConcentrationOut, DividendAnalyticsOut, HoldingValueOut, JournalItemOut, JournalOut, MonthAmountOut, MonthExtremeOut, MonthlyOut, MonthlyRowOut, PerformancePointOut, RiskOut, StockContributionOut, StockDividendOut, SummaryOut, TagStatOut, TotalsOut,
    YearAmountOut,
)
from app.services.analytics import (
    _latest_prices, _positions, load_attribution, load_benchmark, load_monthly, load_performance,
    load_portfolio, load_risk,
)
from app.services.journal import BuyRecord, build_journal
from app.services.tags import split_tags
from app.services.dividends import (
    DivRecord, monthly_totals, per_stock, projected_calendar, sum_between, trailing_12m, yearly_totals,
)
from app.services.metrics import ZERO, allocation

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=SummaryOut)
async def summary(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    view = await load_portfolio(db, user)
    return SummaryOut(
        totals=TotalsOut.model_validate(view.totals),
        holdings=[HoldingValueOut.model_validate(h) for h in view.holdings],
        xirr_pct=view.xirr_pct,
    )


@router.get("/allocation", response_model=AllocationOut)
async def allocation_chart(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    view = await load_portfolio(db, user)
    by_asset: dict[str, Decimal] = {h.symbol: h.market_value for h in view.holdings}
    by_sector: dict[str, Decimal] = {}
    for h in view.holdings:
        label = h.sector or "Tanpa sektor"
        by_sector[label] = by_sector.get(label, Decimal("0")) + h.market_value
    by_asset["Kas"] = view.totals.cash
    by_sector["Kas"] = view.totals.cash
    return AllocationOut(
        by_asset=[AllocationRowOut.model_validate(r) for r in allocation(by_asset)],
        by_sector=[AllocationRowOut.model_validate(r) for r in allocation(by_sector)],
    )


@router.get("/performance", response_model=list[PerformancePointOut])
async def performance(
    days: int = Query(default=365, ge=1, le=3650),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await load_performance(db, user, days)


def _pct(x: float | None) -> float | None:
    return None if x is None else round(x * 100, 2)


async def _index_or_404(db: AsyncSession, benchmark_id: int) -> Stock:
    bench = await db.get(Stock, benchmark_id)
    if bench is None or bench.kind != "INDEX" or not bench.is_active:
        raise HTTPException(404, "Indeks pembanding tidak ditemukan")
    return bench


@router.get("/benchmarks", response_model=list[BenchmarkOut])
async def benchmarks(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    await ensure_benchmarks(db)
    rows = (await db.execute(
        select(Stock.id, Stock.symbol, Stock.name,
               func.min(HistoricalPrice.trade_date), func.max(HistoricalPrice.trade_date))
        .outerjoin(HistoricalPrice, HistoricalPrice.stock_id == Stock.id)
        .where(Stock.kind == "INDEX", Stock.is_active.is_(True))
        .group_by(Stock.id, Stock.symbol, Stock.name)
        .order_by(Stock.symbol)
    )).all()
    return [BenchmarkOut(id=i, symbol=s, name=n, first_date=a, last_date=b) for i, s, n, a, b in rows]


@router.get("/benchmark", response_model=BenchmarkCompareOut)
async def benchmark_compare(
    benchmark_id: int = Query(gt=0),
    days: int = Query(default=365, ge=30, le=3650),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    bench = await _index_or_404(db, benchmark_id)
    v = await load_benchmark(db, user, bench, days)
    r2 = lambda x: None if x is None else round(x, 2)  # noqa: E731
    return BenchmarkCompareOut(
        symbol=v.symbol, name=v.name, index_start=v.index_start, warning=v.warning,
        portfolio_return_pct=r2(v.portfolio_return), benchmark_return_pct=r2(v.benchmark_return),
        alpha_pct=r2(v.alpha), points=[BenchmarkPointOut(**p) for p in (v.points or [])],
    )


@router.get("/risk", response_model=RiskOut)
async def risk(
    days: int = Query(default=365, ge=30, le=3650),
    benchmark_id: int | None = Query(default=None, gt=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    bench = await _index_or_404(db, benchmark_id) if benchmark_id is not None else None
    v = await load_risk(db, user, days, bench)
    d = v.diversification
    return RiskOut(
        window_days=v.window_days, observations=v.observations, start=v.start, end=v.end,
        twr_pct=_pct(v.twr), volatility_pct=_pct(v.vol), max_drawdown_pct=_pct(v.mdd),
        drawdown_peak=v.dd_peak, drawdown_trough=v.dd_trough,
        beta=None if v.beta is None else round(v.beta, 2), benchmark_symbol=v.benchmark_symbol,
        diversification=None if d is None else ConcentrationOut(
            holdings=d.holdings, sectors=d.sectors, top1_pct=round(d.top1_pct, 1), top3_pct=round(d.top3_pct, 1),
            top_sector=d.top_sector, top_sector_pct=round(d.top_sector_pct, 1),
            effective_n=round(d.effective_n, 1), score=d.score,
        ),
        warnings=v.warnings or [],
    )


@router.get("/dividends", response_model=DividendAnalyticsOut)
async def dividend_analytics(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from datetime import date as _date, datetime as _dt, timezone as _tz
    from decimal import Decimal as _D

    rows = (await db.execute(
        select(Dividend.stock_id, Stock.symbol, Dividend.paid_on, Dividend.amount)
        .join(Stock, Stock.id == Dividend.stock_id).where(Dividend.user_id == user.id)
    )).all()
    records = [DivRecord(sid, sym, d, a) for sid, sym, d, a in rows]
    view = await load_portfolio(db, user)
    held = {h.symbol: (h.quantity, h.total_cost, h.market_value) for h in view.holdings}
    today = _dt.now(_tz.utc).date()

    held_records = [r for r in records if r.symbol in held]
    annual = trailing_12m(held_records, today)
    return DividendAnalyticsOut(
        total_all_time=sum((r.amount for r in records), ZERO),
        last_12m=trailing_12m(records, today),
        ytd=sum_between(records, _date(today.year, 1, 1), today),
        annual_projection=annual,
        avg_per_month=(annual / 12).quantize(_D("0.01")),
        monthly=[MonthAmountOut(month=m, amount=a) for m, a in monthly_totals(records, today, 24)],
        yearly=[YearAmountOut(year=y, amount=a) for y, a in yearly_totals(records)],
        by_stock=[StockDividendOut(
            symbol=s.symbol, total=s.total, last_12m=s.last_12m, last_paid=s.last_paid, payments=s.payments,
            held=s.held, quantity=s.quantity, yield_on_cost_pct=s.yield_on_cost_pct,
            current_yield_pct=s.current_yield_pct) for s in per_stock(records, held, today)],
        calendar=[CalendarMonthOut(month=c.month, amount=c.amount, symbols=c.symbols)
                  for c in projected_calendar(records, set(held), today)],
    )


@router.get("/journal", response_model=JournalOut)
async def journal(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Jurnal keputusan beli (500 terbaru): return sejak beli, alasan, tag, dan ringkasan per tag."""
    rows = (await db.execute(
        select(Transaction, Stock.symbol).join(Stock, Stock.id == Transaction.stock_id)
        .where(Transaction.user_id == user.id, Transaction.type == "BUY")
        .order_by(Transaction.executed_at.desc(), Transaction.id.desc()).limit(500)
    )).all()
    buys = [BuyRecord(t.id, t.executed_at.date(), t.stock_id, sym, t.quantity, t.price, t.fee, t.note,
                      split_tags(t.tags)) for t, sym in rows]
    ids = list({b.stock_id for b in buys})
    prices = {sid: close for sid, (close, _d) in (await _latest_prices(db, ids)).items()}
    positions = await _positions(db, user.id)
    held = {sid for sid, p in positions.items() if p.quantity > 0}
    items, stats = build_journal(buys, prices, held)
    return JournalOut(
        items=[JournalItemOut(**i.__dict__) for i in items],
        tags=[TagStatOut(**s.__dict__) for s in stats],
    )


@router.get("/attribution", response_model=AttributionOut)
async def attribution(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Kontribusi tiap saham terhadap total untung/rugi sejak awal (terealisasi + belum terealisasi + dividen)."""
    v = await load_attribution(db, user)
    return AttributionOut(
        total_pl=v.total_pl, net_deposits=v.net_deposits, residual=v.residual,
        rows=[StockContributionOut(**r.__dict__) for r in v.rows],
    )


@router.get("/monthly", response_model=MonthlyOut)
async def monthly_returns_view(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Return bulanan time-weighted (setoran/penarikan dinetralkan) untuk heatmap."""
    v = await load_monthly(db, user)
    pc = lambda x: None if x is None else round(x * 100, 2)  # noqa: E731
    return MonthlyOut(
        as_of=v.as_of,
        rows=[MonthlyRowOut(year=r["year"], months=[pc(m) for m in r["months"]], total=pc(r["total"])) for r in v.rows],
        best=MonthExtremeOut(year=v.best["year"], month=v.best["month"], pct=pc(v.best["pct"])) if v.best else None,
        worst=MonthExtremeOut(year=v.worst["year"], month=v.worst["month"], pct=pc(v.worst["pct"])) if v.worst else None,
        positive_months=v.positive_months, total_months=v.total_months,
    )
