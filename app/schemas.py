import datetime as dt
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.services.tags import parse_tags, split_tags


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    cash_balance: Decimal
    is_admin: bool
    is_demo: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StockIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9^][A-Za-z0-9.\-]*$")
    name: str = Field(min_length=1, max_length=160)
    exchange: str = Field(min_length=1, max_length=20)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    sector: str | None = Field(default=None, max_length=80)
    kind: Literal["STOCK", "INDEX"] = "STOCK"


class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    name: str
    exchange: str
    currency: str
    sector: str | None
    is_active: bool
    kind: str


class CashFlowIn(BaseModel):
    type: Literal["DEPOSIT", "WITHDRAW"]
    amount: Decimal = Field(gt=0, le=Decimal("10000000000000"), max_digits=18, decimal_places=2)
    date: dt.date | None = None  # opsional: catatan bertanggal mundur


class TradeIn(BaseModel):
    stock_id: int = Field(gt=0)
    type: Literal["BUY", "SELL"]
    quantity: Decimal = Field(gt=0, le=Decimal("100000000"), max_digits=18, decimal_places=4)
    price: Decimal = Field(gt=0, le=Decimal("10000000"), max_digits=18, decimal_places=4)
    fee: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("1000000000000"), max_digits=18, decimal_places=4)
    note: str | None = Field(default=None, max_length=255)
    date: dt.date | None = None  # opsional: transaksi bertanggal mundur
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def _norm_tags(cls, v):
        return parse_tags(v)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    stock_id: int
    type: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    executed_at: datetime
    note: str | None
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def _split(cls, v):
        return split_tags(v) if (v is None or isinstance(v, str)) else list(v)


class HoldingOut(BaseModel):
    stock_id: int
    symbol: str
    quantity: Decimal
    avg_cost: Decimal
    total_cost: Decimal
    realized_pl: Decimal


class PriceBarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class QuoteOut(BaseModel):
    stock_id: int
    symbol: str
    price: Decimal
    as_of: date
    source: str


class SyncOut(BaseModel):
    stock_id: int
    symbol: str
    upserted: int


class DividendIn(BaseModel):
    stock_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, le=Decimal("10000000000000"), max_digits=18, decimal_places=2)
    paid_on: date


class DividendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    stock_id: int
    amount: Decimal
    paid_on: date


class HoldingValueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stock_id: int
    symbol: str
    sector: str | None
    quantity: Decimal
    avg_cost: Decimal
    total_cost: Decimal
    price: Decimal
    price_date: date | None
    price_source: str
    market_value: Decimal
    floating_pl: Decimal
    floating_pl_pct: Decimal | None
    realized_pl: Decimal


class TotalsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cash: Decimal
    holdings_value: Decimal
    net_worth: Decimal
    net_deposits: Decimal
    total_pl: Decimal
    roi_pct: Decimal | None
    floating_pl: Decimal
    realized_pl: Decimal
    dividends_total: Decimal
    dividend_yield_pct: Decimal | None
    yield_on_cost_pct: Decimal | None


class SummaryOut(BaseModel):
    totals: TotalsOut
    holdings: list[HoldingValueOut]
    xirr_pct: Decimal | None


class AllocationRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    label: str
    value: Decimal
    pct: Decimal


class AllocationOut(BaseModel):
    by_asset: list[AllocationRowOut]
    by_sector: list[AllocationRowOut]


class PerformancePointOut(BaseModel):
    date: date
    net_worth: float
    invested_capital: float
    cash: float
    holdings_value: float


class OkOut(BaseModel):
    ok: bool = True


class WatchAdd(BaseModel):
    stock_id: int = Field(gt=0)


class WatchItemOut(BaseModel):
    stock_id: int
    symbol: str
    name: str
    exchange: str
    currency: str
    sector: str | None
    price: Decimal | None
    price_date: date | None
    change_pct: Decimal | None


class AlertIn(BaseModel):
    stock_id: int = Field(gt=0)
    direction: Literal["ABOVE", "BELOW"]
    target_price: Decimal = Field(gt=0, le=Decimal("10000000"), max_digits=18, decimal_places=4)


class AlertOut(BaseModel):
    id: int
    stock_id: int
    symbol: str
    direction: str
    target_price: Decimal
    is_active: bool
    created_at: datetime
    triggered_at: datetime | None
    triggered_price: Decimal | None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    title: str
    message: str
    created_at: datetime
    read_at: datetime | None


class NotificationsOut(BaseModel):
    unread: int
    items: list[NotificationOut]


class ImportErrorOut(BaseModel):
    line: int | None
    message: str


class ImportReportOut(BaseModel):
    ok: bool
    committed: bool
    duplicate: bool
    total_rows: int
    counts: dict[str, int]
    date_from: date | None
    date_to: date | None
    cash_effect: Decimal
    resulting_cash: Decimal | None
    errors: list[ImportErrorOut]
    more_errors: int = 0


class BenchmarkOut(BaseModel):
    id: int
    symbol: str
    name: str
    first_date: date | None
    last_date: date | None


class BenchmarkPointOut(BaseModel):
    date: date
    portfolio: float
    benchmark: float
    invested: float


class BenchmarkCompareOut(BaseModel):
    symbol: str
    name: str
    index_start: date | None
    warning: str | None
    portfolio_return_pct: float | None
    benchmark_return_pct: float | None
    alpha_pct: float | None
    points: list[BenchmarkPointOut]


class ConcentrationOut(BaseModel):
    holdings: int
    sectors: int
    top1_pct: float
    top3_pct: float
    top_sector: str | None
    top_sector_pct: float
    effective_n: float
    score: int


class RiskOut(BaseModel):
    window_days: int
    observations: int
    start: date | None
    end: date | None
    twr_pct: float | None
    volatility_pct: float | None
    max_drawdown_pct: float | None
    drawdown_peak: date | None
    drawdown_trough: date | None
    beta: float | None
    benchmark_symbol: str | None
    diversification: ConcentrationOut | None
    warnings: list[str]


class TradeUpdate(BaseModel):
    stock_id: int | None = Field(default=None, gt=0)
    type: Literal["BUY", "SELL"] | None = None
    quantity: Decimal | None = Field(default=None, gt=0, le=Decimal("100000000"), max_digits=18, decimal_places=4)
    price: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000"), max_digits=18, decimal_places=4)
    fee: Decimal | None = Field(default=None, ge=0, le=Decimal("1000000000000"), max_digits=18, decimal_places=4)
    note: str | None = Field(default=None, max_length=255)
    date: dt.date | None = None
    tags: list[str] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _norm_tags(cls, v):
        return None if v is None else parse_tags(v)


class CashUpdate(BaseModel):
    type: Literal["DEPOSIT", "WITHDRAW"] | None = None
    amount: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000000000"), max_digits=18, decimal_places=2)
    date: dt.date | None = None


class DividendUpdate(BaseModel):
    stock_id: int | None = Field(default=None, gt=0)
    amount: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000000000"), max_digits=18, decimal_places=2)
    paid_on: dt.date | None = None


class LedgerItemOut(BaseModel):
    kind: Literal["TRADE", "CASH", "DIVIDEND"]
    id: int
    at: datetime
    day: dt.date
    type: str
    stock_id: int | None
    symbol: str | None
    quantity: Decimal | None
    price: Decimal | None
    fee: Decimal | None
    amount: Decimal | None
    note: str | None
    tags: list[str] = Field(default_factory=list)


class LedgerPageOut(BaseModel):
    total: int
    items: list[LedgerItemOut]


class TargetIn(BaseModel):
    target_price: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000"), max_digits=18, decimal_places=4)
    stop_price: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000"), max_digits=18, decimal_places=4)
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _check(self):
        if self.target_price is None and self.stop_price is None:
            raise ValueError("Isi minimal salah satu: target harga atau stop loss")
        if self.target_price is not None and self.stop_price is not None and self.stop_price >= self.target_price:
            raise ValueError("Stop loss harus lebih rendah dari target harga")
        return self


class TargetOut(BaseModel):
    stock_id: int
    symbol: str
    name: str
    currency: str
    quantity: Decimal
    avg_cost: Decimal | None
    price: Decimal | None
    price_date: dt.date | None
    target_price: Decimal | None
    stop_price: Decimal | None
    note: str | None
    target_hit_at: datetime | None
    stop_hit_at: datetime | None
    target_from_cost_pct: Decimal | None
    stop_from_cost_pct: Decimal | None
    to_target_pct: Decimal | None
    to_stop_pct: Decimal | None
    progress_pct: Decimal | None
    risk_reward: Decimal | None


class MonthAmountOut(BaseModel):
    month: str
    amount: Decimal


class YearAmountOut(BaseModel):
    year: int
    amount: Decimal


class StockDividendOut(BaseModel):
    symbol: str
    total: Decimal
    last_12m: Decimal
    last_paid: dt.date
    payments: int
    held: bool
    quantity: Decimal | None
    yield_on_cost_pct: Decimal | None
    current_yield_pct: Decimal | None


class CalendarMonthOut(BaseModel):
    month: int
    amount: Decimal
    symbols: list[str]


class DividendAnalyticsOut(BaseModel):
    total_all_time: Decimal
    last_12m: Decimal
    ytd: Decimal
    annual_projection: Decimal
    avg_per_month: Decimal
    monthly: list[MonthAmountOut]
    yearly: list[YearAmountOut]
    by_stock: list[StockDividendOut]
    calendar: list[CalendarMonthOut]


class JournalItemOut(BaseModel):
    id: int
    day: dt.date
    symbol: str
    quantity: Decimal
    price: Decimal
    cost: Decimal
    current_price: Decimal | None
    return_pct: Decimal | None
    pnl: Decimal | None
    still_held: bool
    note: str | None
    tags: list[str]


class TagStatOut(BaseModel):
    tag: str
    count: int
    total_cost: Decimal
    weighted_return_pct: Decimal | None
    win_rate_pct: Decimal | None


class JournalOut(BaseModel):
    items: list[JournalItemOut]
    tags: list[TagStatOut]


class ReportTotalsOut(BaseModel):
    sales_count: int
    gross_sales: Decimal
    sell_fees: Decimal
    net_proceeds: Decimal
    cost_basis: Decimal
    realized_pl: Decimal
    dividends: Decimal


class SaleLineOut(BaseModel):
    day: dt.date
    symbol: str
    quantity: Decimal
    gross: Decimal
    fee: Decimal
    net: Decimal
    cost_basis: Decimal
    realized: Decimal


class StockYearOut(BaseModel):
    symbol: str
    gross: Decimal
    cost_basis: Decimal
    realized: Decimal
    dividends: Decimal


class DividendLineOut(BaseModel):
    day: dt.date
    symbol: str
    amount: Decimal


class YearEndPositionOut(BaseModel):
    symbol: str
    quantity: Decimal
    total_cost: Decimal
    avg_cost: Decimal
    price: Decimal | None
    price_date: dt.date | None
    market_value: Decimal | None


class AnnualReportOut(BaseModel):
    year: int
    as_of: dt.date
    generated_on: dt.date
    totals: ReportTotalsOut
    by_stock: list[StockYearOut]
    sales: list[SaleLineOut]
    dividends: list[DividendLineOut]
    positions: list[YearEndPositionOut]
    notes: list[str]


class StockContributionOut(BaseModel):
    symbol: str
    sector: str | None
    invested: Decimal
    realized: Decimal
    floating: Decimal
    dividends: Decimal
    total: Decimal
    share_of_pl_pct: Decimal | None
    contribution_to_return_pct: Decimal | None
    return_on_cost_pct: Decimal | None
    held: bool


class AttributionOut(BaseModel):
    total_pl: Decimal
    net_deposits: Decimal
    residual: Decimal
    rows: list[StockContributionOut]


class MonthlyRowOut(BaseModel):
    year: int
    months: list[float | None]
    total: float | None


class MonthExtremeOut(BaseModel):
    year: int
    month: int
    pct: float


class MonthlyOut(BaseModel):
    as_of: dt.date | None
    rows: list[MonthlyRowOut]
    best: MonthExtremeOut | None
    worst: MonthExtremeOut | None
    positive_months: int
    total_months: int
