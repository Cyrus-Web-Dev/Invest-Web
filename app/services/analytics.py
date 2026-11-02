from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from itertools import groupby

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CashFlow, Dividend, HistoricalPrice, Stock, Transaction, User
from app.services.metrics import (
    ZERO, HoldingValue, Totals, build_totals, make_events, to_day, value_holding, xirr,
)
from app.services.performance import build_performance_series
from app.services.positions import Position, Trade, compute_position
from app.services.risk import (
    Concentration, Point, bench_returns, beta, concentration, max_drawdown, monthly_returns,
    shadow_benchmark, total_return, twr_returns, volatility, weekday_points, yearly_from_monthly,
)
from app.services.attribution import AttrInput, StockContribution, build_attribution
from app.services.metrics import money


@dataclass
class PortfolioView:
    holdings: list[HoldingValue]
    totals: Totals
    xirr_pct: Decimal | None


def _today():
    return datetime.now(timezone.utc).date()


async def _positions(db: AsyncSession, user_id: int) -> dict[int, Position]:
    rows = (await db.scalars(
        select(Transaction).where(Transaction.user_id == user_id)
        .order_by(Transaction.stock_id, Transaction.executed_at, Transaction.id)
    )).all()
    return {
        sid: compute_position(Trade(t.type, t.quantity, t.price, t.fee) for t in group)
        for sid, group in groupby(rows, key=lambda t: t.stock_id)
    }


async def _latest_prices(db: AsyncSession, stock_ids: list[int]) -> dict[int, tuple]:
    if not stock_ids:
        return {}
    latest = (
        select(HistoricalPrice.stock_id.label("sid"), func.max(HistoricalPrice.trade_date).label("d"))
        .where(HistoricalPrice.stock_id.in_(stock_ids))
        .group_by(HistoricalPrice.stock_id)
        .subquery()
    )
    q = select(HistoricalPrice.stock_id, HistoricalPrice.close, HistoricalPrice.trade_date).join(
        latest, and_(HistoricalPrice.stock_id == latest.c.sid, HistoricalPrice.trade_date == latest.c.d)
    )
    return {sid: (close, d) for sid, close, d in (await db.execute(q)).all()}


async def load_portfolio(db: AsyncSession, user: User) -> PortfolioView:
    positions = await _positions(db, user.id)
    open_ids = [sid for sid, p in positions.items() if p.quantity > 0]
    stocks = {}
    if open_ids:
        stocks = {s.id: s for s in (await db.scalars(select(Stock).where(Stock.id.in_(open_ids)))).all()}
    prices = await _latest_prices(db, open_ids)

    holdings = []
    for sid in open_ids:
        s = stocks[sid]
        price, price_date = prices.get(sid, (None, None))
        holdings.append(value_holding(sid, s.symbol, s.sector, positions[sid], price, price_date))
    holdings.sort(key=lambda h: h.market_value, reverse=True)

    flows = (await db.scalars(select(CashFlow).where(CashFlow.user_id == user.id))).all()
    divs = (await db.scalars(select(Dividend).where(Dividend.user_id == user.id))).all()
    deposits = sum((c.amount for c in flows if c.type == "DEPOSIT"), ZERO)
    withdrawals = sum((c.amount for c in flows if c.type == "WITHDRAW"), ZERO)
    today = _today()
    cutoff = today - timedelta(days=365)
    div_total = sum((d.amount for d in divs), ZERO)
    div_12m = sum((d.amount for d in divs if d.paid_on >= cutoff), ZERO)
    realized = sum((p.realized_pl for p in positions.values()), ZERO)

    totals = build_totals(user.cash_balance, holdings, deposits, withdrawals, div_total, div_12m, realized)

    cf = [(to_day(c.occurred_at), -c.amount if c.type == "DEPOSIT" else c.amount) for c in flows]
    cf.append((today, totals.net_worth))
    x = xirr(cf)
    xirr_pct = Decimal(str(round(x * 100, 2))) if x is not None else None
    return PortfolioView(holdings, totals, xirr_pct)


async def load_performance(db: AsyncSession, user: User, days: int) -> list[dict]:
    txs = (await db.scalars(
        select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.id)
    )).all()
    flows = (await db.scalars(select(CashFlow).where(CashFlow.user_id == user.id))).all()
    divs = (await db.scalars(select(Dividend).where(Dividend.user_id == user.id))).all()
    events = make_events(txs, flows, divs)
    if not events:
        return []
    min_day = min(e.day for e in events)
    ids = {t.stock_id for t in txs}
    closes: dict[int, list] = {}
    if ids:
        rows = await db.execute(
            select(HistoricalPrice.stock_id, HistoricalPrice.trade_date, HistoricalPrice.close)
            .where(HistoricalPrice.stock_id.in_(ids),
                   HistoricalPrice.trade_date >= min_day - timedelta(days=7))
            .order_by(HistoricalPrice.trade_date)
        )
        for sid, d, c in rows.all():
            closes.setdefault(sid, []).append((d, c))
    return build_performance_series(events, closes, _today(), days)


# ======================= Fase 10: risiko & benchmark =======================
async def _ledger(db: AsyncSession, user_id: int):
    txs = (await db.scalars(
        select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.id)
    )).all()
    flows = (await db.scalars(select(CashFlow).where(CashFlow.user_id == user_id))).all()
    divs = (await db.scalars(select(Dividend).where(Dividend.user_id == user_id))).all()
    return txs, flows, divs


async def _closes_for(db: AsyncSession, ids: set[int], since: date) -> dict[int, list[tuple[date, Decimal]]]:
    out: dict[int, list[tuple[date, Decimal]]] = {}
    if not ids:
        return out
    rows = await db.execute(
        select(HistoricalPrice.stock_id, HistoricalPrice.trade_date, HistoricalPrice.close)
        .where(HistoricalPrice.stock_id.in_(ids), HistoricalPrice.trade_date >= since)
        .order_by(HistoricalPrice.trade_date)
    )
    for sid, d, c in rows.all():
        out.setdefault(sid, []).append((d, c))
    return out


@dataclass
class RiskView:
    window_days: int
    observations: int = 0
    start: date | None = None
    end: date | None = None
    twr: float | None = None
    vol: float | None = None
    mdd: float | None = None
    dd_peak: date | None = None
    dd_trough: date | None = None
    beta: float | None = None
    benchmark_symbol: str | None = None
    diversification: Concentration | None = None
    warnings: list[str] | None = None


def _diversification(view: PortfolioView) -> tuple[Concentration | None, list[str]]:
    values = {h.symbol: float(h.market_value) for h in view.holdings}
    sectors: dict[str, float] = {}
    for h in view.holdings:
        label = h.sector or "Tanpa sektor"
        sectors[label] = sectors.get(label, 0.0) + float(h.market_value)
    c = concentration(values, sectors)
    warnings: list[str] = []
    if c:
        top = max(values, key=lambda k: values[k])
        if c.top1_pct > 30:
            warnings.append(f"{top} menguasai {c.top1_pct:.1f}% nilai saham (acuan umum: maksimal ±30% per saham).")
        if c.top_sector and c.top_sector_pct > 50:
            warnings.append(f"Sektor {c.top_sector} mencakup {c.top_sector_pct:.1f}% nilai saham (acuan umum: maksimal ±50%).")
        if c.holdings < 5:
            warnings.append(f"Portofolio baru berisi {c.holdings} saham; pertimbangkan menambah agar risiko lebih tersebar.")
    return c, warnings


async def load_risk(db: AsyncSession, user: User, days: int, bench: Stock | None) -> RiskView:
    view = RiskView(window_days=days, benchmark_symbol=bench.symbol if bench else None)
    portfolio = await load_portfolio(db, user)
    view.diversification, view.warnings = _diversification(portfolio)

    txs, flows, divs = await _ledger(db, user.id)
    events = make_events(txs, flows, divs)
    if not events:
        return view
    min_day = min(e.day for e in events)
    ids = {t.stock_id for t in txs}
    closes = await _closes_for(db, ids | ({bench.id} if bench else set()), min_day - timedelta(days=7))
    series = build_performance_series(
        events, {k: v for k, v in closes.items() if bench is None or k != bench.id}, _today(), 36500
    )
    pts = [Point(p["date"], p["net_worth"], p["invested_capital"]) for p in series]
    if len(pts) < 2:
        return view
    cutoff = pts[-1].day - timedelta(days=days)
    window = [p for p in weekday_points(pts) if p.day >= cutoff]
    rets = twr_returns(window)
    view.observations = len(rets)
    if window:
        view.start, view.end = window[0].day, window[-1].day
    view.twr = total_return(rets)
    view.vol = volatility(rets)
    dd = max_drawdown(rets, window[0].day) if window else None
    if dd:
        view.mdd, view.dd_peak, view.dd_trough = dd
    if bench and closes.get(bench.id):
        idx = {d: float(c) for d, c in closes[bench.id]}
        view.beta = beta(rets, bench_returns([p.day for p in window], idx))
    return view


@dataclass
class BenchmarkView:
    symbol: str
    name: str
    index_start: date | None = None
    warning: str | None = None
    portfolio_return: float | None = None
    benchmark_return: float | None = None
    alpha: float | None = None
    points: list[dict] | None = None


async def load_benchmark(db: AsyncSession, user: User, bench: Stock, days: int) -> BenchmarkView:
    view = BenchmarkView(symbol=bench.symbol, name=bench.name, points=[])
    txs, flows, divs = await _ledger(db, user.id)
    events = make_events(txs, flows, divs)
    if not events:
        view.warning = "Belum ada transaksi atau setoran untuk dibandingkan."
        return view
    min_day = min(e.day for e in events)
    closes = await _closes_for(db, {t.stock_id for t in txs} | {bench.id}, min_day - timedelta(days=7))
    idx = {d: float(c) for d, c in closes.get(bench.id, [])}
    if not idx:
        view.warning = "Belum ada data harga untuk indeks ini. Klik Sync untuk mengambilnya."
        return view
    view.index_start = min(idx)
    series = build_performance_series(
        events, {k: v for k, v in closes.items() if k != bench.id}, _today(), 36500
    )
    if not series:
        return view
    cap: dict[date, float] = {}
    for e in events:
        if e.capital_delta != 0:
            cap[e.day] = cap.get(e.day, 0.0) + float(e.capital_delta)
    shadow = shadow_benchmark(cap, idx, [p["date"] for p in series])

    last = series[-1]
    invested = last["invested_capital"]
    if invested > 0:
        view.portfolio_return = (last["net_worth"] - invested) / invested * 100
        view.benchmark_return = (shadow[-1] - invested) / invested * 100
        view.alpha = view.portfolio_return - view.benchmark_return
    if view.index_start > min_day + timedelta(days=7):
        view.warning = (
            f"Data indeks baru tersedia sejak {view.index_start}, sedangkan portofolio dimulai {min_day}. "
            "Sync ulang dengan rentang lebih panjang agar perbandingan adil."
        )
    cutoff = last["date"] - timedelta(days=days)
    view.points = [
        {"date": p["date"], "portfolio": p["net_worth"], "benchmark": round(shadow[i], 2),
         "invested": p["invested_capital"]}
        for i, p in enumerate(series) if p["date"] >= cutoff
    ]
    return view


# ======================= Fase 17: atribusi & return bulanan =======================
@dataclass
class AttributionView:
    total_pl: Decimal
    net_deposits: Decimal
    rows: list[StockContribution]
    residual: Decimal


async def load_attribution(db: AsyncSession, user: User) -> AttributionView:
    portfolio = await load_portfolio(db, user)
    positions = await _positions(db, user.id)
    invested = dict((await db.execute(
        select(Transaction.stock_id, func.sum(Transaction.quantity * Transaction.price + Transaction.fee))
        .where(Transaction.user_id == user.id, Transaction.type == "BUY").group_by(Transaction.stock_id)
    )).all())
    divs = dict((await db.execute(
        select(Dividend.stock_id, func.sum(Dividend.amount)).where(Dividend.user_id == user.id)
        .group_by(Dividend.stock_id)
    )).all())
    ids = set(positions) | set(divs)
    stocks = {s.id: s for s in (await db.scalars(select(Stock).where(Stock.id.in_(ids)))).all()} if ids else {}
    prices = await _latest_prices(db, [i for i, p in positions.items() if p.quantity > 0])

    items: list[AttrInput] = []
    for sid in ids:
        s = stocks[sid]
        pos = positions.get(sid)
        held = pos is not None and pos.quantity > 0
        floating = ZERO
        if held:
            price, pdate = prices.get(sid, (None, None))
            floating = value_holding(sid, s.symbol, s.sector, pos, price, pdate).floating_pl
        items.append(AttrInput(
            symbol=s.symbol, sector=s.sector, invested=money(invested.get(sid, ZERO)),
            realized=money(pos.realized_pl) if pos else ZERO, floating=floating,
            dividends=divs.get(sid, ZERO), held=held,
        ))
    rows, residual = build_attribution(items, portfolio.totals.total_pl, portfolio.totals.net_deposits)
    return AttributionView(portfolio.totals.total_pl, portfolio.totals.net_deposits, rows, residual)


@dataclass
class MonthlyView:
    as_of: date | None
    rows: list[dict]
    best: dict | None
    worst: dict | None
    positive_months: int
    total_months: int


async def load_monthly(db: AsyncSession, user: User) -> MonthlyView:
    empty = MonthlyView(None, [], None, None, 0, 0)
    txs, flows, divs = await _ledger(db, user.id)
    events = make_events(txs, flows, divs)
    if not events:
        return empty
    min_day = min(e.day for e in events)
    closes = await _closes_for(db, {t.stock_id for t in txs}, min_day - timedelta(days=7))
    series = build_performance_series(events, closes, _today(), 36500)
    pts = [Point(p["date"], p["net_worth"], p["invested_capital"]) for p in series]
    rets = twr_returns(weekday_points(pts))
    months = monthly_returns(rets)
    if not months:
        return empty
    yearly = yearly_from_monthly(months)
    rows = [
        {"year": y, "months": [months.get((y, m)) for m in range(1, 13)], "total": yearly[y]}
        for y in sorted(yearly)
    ]
    ordered = sorted(months.items(), key=lambda kv: kv[1])
    (wy, wm), wv = ordered[0]
    (by, bm), bv = ordered[-1]
    return MonthlyView(
        as_of=pts[-1].day, rows=rows, best={"year": by, "month": bm, "pct": bv},
        worst={"year": wy, "month": wm, "pct": wv},
        positive_months=sum(1 for v in months.values() if v > 0), total_months=len(months),
    )
