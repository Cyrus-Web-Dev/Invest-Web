import type {
  AlertItem, Allocation, Benchmark, BenchmarkCompare, Dividend, ImportReport, LedgerItem, LedgerPage,
  Notifications, PerformancePoint, PriceBar, Quote, Risk, Stock, Summary, SyncResult, Transaction, User,
  WatchItem, AnnualReport, Attribution, DividendAnalytics, Journal, Monthly, TargetItem,
} from "./types";

const TOKEN_KEY = "stockfolio_token";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) => {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function parseDetail(detail: any): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d?.loc) ? d.loc.slice(1).join(".") : "";
        return field ? `${field}: ${d?.msg}` : String(d?.msg ?? "");
      })
      .filter(Boolean)
      .join("; ");
  }
  return null;
}

interface Opts {
  method?: string; json?: unknown; form?: Record<string, string>; formData?: FormData; auth?: boolean;
}

async function request<T>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = new URLSearchParams(opts.form);
  } else if (opts.formData) {
    body = opts.formData;
  }
  const token = getToken();
  if (opts.auth !== false && token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { method: opts.method ?? (body ? "POST" : "GET"), headers, body });
  } catch {
    throw new ApiError(0, "Tidak dapat terhubung ke server");
  }
  if (!res.ok) {
    let message = `Terjadi kesalahan (${res.status})`;
    try {
      const data = await res.json();
      message = parseDetail(data?.detail) ?? message;
    } catch {
      /* respons bukan JSON */
    }
    if (res.status === 401 && opts.auth !== false) onUnauthorized?.();
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

/** Unduh file dari endpoint yang butuh token (tautan biasa tidak bisa mengirim header Authorization). */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    throw new ApiError(0, "Tidak dapat terhubung ke server");
  }
  if (!res.ok) {
    if (res.status === 401) onUnauthorized?.();
    throw new ApiError(res.status, `Gagal mengunduh (${res.status})`);
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const qs = (params: Record<string, string | number | undefined>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

const ledgerPath = (kind: LedgerItem["kind"], id: number) =>
  kind === "TRADE" ? `/portfolio/transactions/${id}` : kind === "CASH" ? `/portfolio/cash/${id}` : `/portfolio/dividends/${id}`;

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", { form: { username: email, password }, auth: false }),
  register: (email: string, password: string, full_name: string) =>
    request<User>("/auth/register", { json: { email, password, full_name }, auth: false }),
  me: () => request<User>("/auth/me"),

  listStocks: (q?: string) => request<Stock[]>(`/stocks${qs({ q, limit: 200 })}`),
  createStock: (body: { symbol: string; name: string; exchange: string; currency: string; sector: string | null; kind?: "STOCK" | "INDEX" }) =>
    request<Stock>("/stocks", { json: body }),
  prices: (id: number, days: number) => request<PriceBar[]>(`/stocks/${id}/prices${qs({ days })}`),
  quote: (id: number) => request<Quote>(`/stocks/${id}/quote`),
  syncStock: (id: number, days?: number) =>
    request<SyncResult>(`/stocks/${id}/sync${qs({ days })}`, { method: "POST" }),

  cash: (type: "DEPOSIT" | "WITHDRAW", amount: string, date?: string) =>
    request<User>("/portfolio/cash", { json: { type, amount, date: date ?? null } }),
  trade: (body: {
    stock_id: number; type: "BUY" | "SELL"; quantity: string; price: string; fee: string; note: string | null;
    date?: string | null; tags?: string[];
  }) => request<Transaction>("/portfolio/transactions", { json: body }),
  transactions: () => request<Transaction[]>(`/portfolio/transactions${qs({ limit: 100 })}`),
  dividends: () => request<Dividend[]>(`/portfolio/dividends${qs({ limit: 100 })}`),
  addDividend: (body: { stock_id: number; amount: string; paid_on: string }) =>
    request<Dividend>("/portfolio/dividends", { json: body }),

  watchlist: () => request<WatchItem[]>("/watchlist"),
  addWatch: (stock_id: number) => request<{ ok: boolean }>("/watchlist", { json: { stock_id } }),
  removeWatch: (stock_id: number) => request<{ ok: boolean }>(`/watchlist/${stock_id}`, { method: "DELETE" }),
  alerts: () => request<AlertItem[]>("/alerts"),
  createAlert: (body: { stock_id: number; direction: "ABOVE" | "BELOW"; target_price: string }) =>
    request<AlertItem>("/alerts", { json: body }),
  deleteAlert: (id: number) => request<{ ok: boolean }>(`/alerts/${id}`, { method: "DELETE" }),
  notifications: () => request<Notifications>("/notifications?limit=15"),
  readAllNotifications: () => request<{ ok: boolean }>("/notifications/read-all", { method: "POST" }),

  importFile: (file: File, dryRun: boolean, force = false) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<ImportReport>(`/portfolio/import?dry_run=${dryRun}&force=${force}`, { method: "POST", formData: fd });
  },

  benchmarks: () => request<Benchmark[]>("/analytics/benchmarks"),
  benchmarkCompare: (benchmark_id: number, days: number) =>
    request<BenchmarkCompare>(`/analytics/benchmark${qs({ benchmark_id, days })}`),
  risk: (days: number, benchmark_id?: number | null) =>
    request<Risk>(`/analytics/risk${qs({ days, benchmark_id: benchmark_id ?? undefined })}`),

  ledger: (p: { limit: number; type?: string; q?: string; tag?: string }) => request<LedgerPage>(`/portfolio/ledger${qs(p)}`),
  updateLedger: (kind: LedgerItem["kind"], id: number, body: Record<string, unknown>) =>
    request<LedgerItem>(ledgerPath(kind, id), { method: "PATCH", json: body }),
  deleteLedger: (kind: LedgerItem["kind"], id: number) =>
    request<{ ok: boolean }>(ledgerPath(kind, id), { method: "DELETE" }),

  attribution: () => request<Attribution>("/analytics/attribution"),
  monthlyReturns: () => request<Monthly>("/analytics/monthly"),
  reportYears: () => request<number[]>("/reports/years"),
  annualReport: (year: number) => request<AnnualReport>(`/reports/annual${qs({ year })}`),
  journal: () => request<Journal>("/analytics/journal"),
  targets: () => request<TargetItem[]>("/targets"),
  setTarget: (stock_id: number, body: { target_price: string | null; stop_price: string | null; note: string | null }) =>
    request<{ ok: boolean }>(`/targets/${stock_id}`, { method: "PUT", json: body }),
  deleteTarget: (stock_id: number) => request<{ ok: boolean }>(`/targets/${stock_id}`, { method: "DELETE" }),
  dividendAnalytics: () => request<DividendAnalytics>("/analytics/dividends"),

  summary: () => request<Summary>("/analytics/summary"),
  allocation: () => request<Allocation>("/analytics/allocation"),
  performance: (days: number) => request<PerformancePoint[]>(`/analytics/performance${qs({ days })}`),
};
