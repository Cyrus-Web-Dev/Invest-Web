// Nilai uang dari API berbentuk string (Decimal) agar presisi terjaga.
export interface User { id: number; email: string; full_name: string; cash_balance: string; is_admin: boolean; is_demo: boolean }
export interface Stock {
  id: number; symbol: string; name: string; exchange: string;
  currency: string; sector: string | null; is_active: boolean; kind: string;
}
export interface PriceBar {
  trade_date: string; open: string; high: string; low: string; close: string; volume: number;
}
export interface Quote {
  stock_id: number; symbol: string; price: string; as_of: string;
  source: "cache" | "live" | "db_fallback";
}
export interface SyncResult { stock_id: number; symbol: string; upserted: number }
export interface Transaction {
  id: number; stock_id: number; type: "BUY" | "SELL"; quantity: string; price: string;
  fee: string; executed_at: string; note: string | null;
}
export interface Dividend { id: number; stock_id: number; amount: string; paid_on: string }
export interface HoldingValue {
  stock_id: number; symbol: string; sector: string | null; quantity: string; avg_cost: string;
  total_cost: string; price: string; price_date: string | null; price_source: "market" | "cost";
  market_value: string; floating_pl: string; floating_pl_pct: string | null; realized_pl: string;
}
export interface Totals {
  cash: string; holdings_value: string; net_worth: string; net_deposits: string;
  total_pl: string; roi_pct: string | null; floating_pl: string; realized_pl: string;
  dividends_total: string; dividend_yield_pct: string | null; yield_on_cost_pct: string | null;
}
export interface Summary { totals: Totals; holdings: HoldingValue[]; xirr_pct: string | null }
export interface AllocationRow { label: string; value: string; pct: string }
export interface Allocation { by_asset: AllocationRow[]; by_sector: AllocationRow[] }
export interface PerformancePoint {
  date: string; net_worth: number; invested_capital: number; cash: number; holdings_value: number;
}

export interface WatchItem {
  stock_id: number; symbol: string; name: string; exchange: string; currency: string;
  sector: string | null; price: string | null; price_date: string | null; change_pct: string | null;
}
export interface AlertItem {
  id: number; stock_id: number; symbol: string; direction: "ABOVE" | "BELOW"; target_price: string;
  is_active: boolean; created_at: string; triggered_at: string | null; triggered_price: string | null;
}
export interface AppNotification {
  id: number; kind: string; title: string; message: string; created_at: string; read_at: string | null;
}
export interface Notifications { unread: number; items: AppNotification[] }

export interface ImportError { line: number | null; message: string }
export interface ImportReport {
  ok: boolean; committed: boolean; duplicate: boolean; total_rows: number; counts: Record<string, number>;
  date_from: string | null; date_to: string | null; cash_effect: string; resulting_cash: string | null;
  errors: ImportError[]; more_errors: number;
}

export interface Benchmark { id: number; symbol: string; name: string; first_date: string | null; last_date: string | null }
export interface BenchmarkPoint { date: string; portfolio: number; benchmark: number; invested: number }
export interface BenchmarkCompare {
  symbol: string; name: string; index_start: string | null; warning: string | null;
  portfolio_return_pct: number | null; benchmark_return_pct: number | null; alpha_pct: number | null;
  points: BenchmarkPoint[];
}
export interface Diversification {
  holdings: number; sectors: number; top1_pct: number; top3_pct: number; top_sector: string | null;
  top_sector_pct: number; effective_n: number; score: number;
}
export interface Risk {
  window_days: number; observations: number; start: string | null; end: string | null;
  twr_pct: number | null; volatility_pct: number | null; max_drawdown_pct: number | null;
  drawdown_peak: string | null; drawdown_trough: string | null; beta: number | null;
  benchmark_symbol: string | null; diversification: Diversification | null; warnings: string[];
}

export interface LedgerItem {
  kind: "TRADE" | "CASH" | "DIVIDEND"; id: number; at: string; day: string;
  type: "BUY" | "SELL" | "DEPOSIT" | "WITHDRAW" | "DIVIDEND";
  stock_id: number | null; symbol: string | null; quantity: string | null; price: string | null;
  fee: string | null; amount: string | null; note: string | null; tags: string[];
}
export interface LedgerPage { total: number; items: LedgerItem[] }

export interface TargetItem {
  stock_id: number; symbol: string; name: string; currency: string; quantity: string; avg_cost: string | null;
  price: string | null; price_date: string | null; target_price: string | null; stop_price: string | null;
  note: string | null; target_hit_at: string | null; stop_hit_at: string | null;
  target_from_cost_pct: string | null; stop_from_cost_pct: string | null; to_target_pct: string | null;
  to_stop_pct: string | null; progress_pct: string | null; risk_reward: string | null;
}
export interface DividendAnalytics {
  total_all_time: string; last_12m: string; ytd: string; annual_projection: string; avg_per_month: string;
  monthly: { month: string; amount: string }[];
  yearly: { year: number; amount: string }[];
  by_stock: {
    symbol: string; total: string; last_12m: string; last_paid: string; payments: number; held: boolean;
    quantity: string | null; yield_on_cost_pct: string | null; current_yield_pct: string | null;
  }[];
  calendar: { month: number; amount: string; symbols: string[] }[];
}

export interface JournalItem {
  id: number; day: string; symbol: string; quantity: string; price: string; cost: string;
  current_price: string | null; return_pct: string | null; pnl: string | null; still_held: boolean;
  note: string | null; tags: string[];
}
export interface TagStat {
  tag: string; count: number; total_cost: string; weighted_return_pct: string | null; win_rate_pct: string | null;
}
export interface Journal { items: JournalItem[]; tags: TagStat[] }

export interface SaleLine { day: string; symbol: string; quantity: string; gross: string; fee: string; net: string; cost_basis: string; realized: string }
export interface AnnualReport {
  year: number; as_of: string; generated_on: string;
  totals: { sales_count: number; gross_sales: string; sell_fees: string; net_proceeds: string; cost_basis: string; realized_pl: string; dividends: string };
  by_stock: { symbol: string; gross: string; cost_basis: string; realized: string; dividends: string }[];
  sales: SaleLine[];
  dividends: { day: string; symbol: string; amount: string }[];
  positions: { symbol: string; quantity: string; total_cost: string; avg_cost: string; price: string | null; price_date: string | null; market_value: string | null }[];
  notes: string[];
}

export interface StockContribution {
  symbol: string; sector: string | null; invested: string; realized: string; floating: string; dividends: string;
  total: string; share_of_pl_pct: string | null; contribution_to_return_pct: string | null; return_on_cost_pct: string | null; held: boolean;
}
export interface Attribution { total_pl: string; net_deposits: string; residual: string; rows: StockContribution[] }
export interface MonthlyRow { year: number; months: (number | null)[]; total: number | null }
export interface MonthExtreme { year: number; month: number; pct: number }
export interface Monthly {
  as_of: string | null; rows: MonthlyRow[]; best: MonthExtreme | null; worst: MonthExtreme | null;
  positive_months: number; total_months: number;
}
