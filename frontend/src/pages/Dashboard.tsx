import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import CountUp from "../components/CountUp";
import Icon from "../components/icons";
import PerformanceChart from "../components/PerformanceChart";
import ChartSkeleton from "../components/ChartSkeleton";
import PieAllocation from "../components/PieAllocation";
import Segmented from "../components/Segmented";
import Skeleton from "../components/Skeleton";
import Sparkline from "../components/Sparkline";
import Stat from "../components/Stat";
import { fmt, fmtPct, fmtQty, tone } from "../format";
import { useLoad } from "../hooks";
import type { Allocation, Summary } from "../types";

const RANGES = [
  { label: "1 Bulan", days: 30 },
  { label: "3 Bulan", days: 90 },
  { label: "1 Tahun", days: 365 },
  { label: "Semua", days: 3650 },
];

interface Insight { kind: "warn" | "info" | "ok"; text: string }

function buildInsights(s: Summary, alloc: Allocation | null): Insight[] {
  const out: Insight[] = [];
  const hv = Number(s.totals.holdings_value);
  const nw = Number(s.totals.net_worth);

  if (s.holdings.length > 0 && hv > 0) {
    const top = s.holdings[0]; // backend mengurutkan nilai pasar terbesar dulu
    const w = (Number(top.market_value) / hv) * 100;
    if (w > 30) {
      out.push({ kind: "warn", text: `${top.symbol} menguasai ${w.toFixed(1)}% nilai saham Anda (acuan umum: maksimal ±30% per saham). Pertimbangkan diversifikasi.` });
    }
  }
  if (alloc) {
    const topSector = alloc.by_sector.find((r) => r.label !== "Kas");
    if (topSector && Number(topSector.pct) > 50) {
      out.push({ kind: "warn", text: `Sektor ${topSector.label} mencakup ${fmt(topSector.pct, 1)}% portofolio. Risiko terkonsentrasi di satu sektor.` });
    }
  }
  const priced = s.holdings.filter((h) => h.price_source === "market" && h.floating_pl_pct !== null);
  if (priced.length >= 2) {
    const sorted = [...priced].sort((a, b) => Number(b.floating_pl_pct) - Number(a.floating_pl_pct));
    const best = sorted[0];
    const worst = sorted[sorted.length - 1];
    out.push({ kind: "ok", text: `Performa terbaik: ${best.symbol} (${fmt(best.floating_pl_pct)}%). Terlemah: ${worst.symbol} (${fmt(worst.floating_pl_pct)}%).` });
  }
  if (nw > 0 && s.holdings.length > 0) {
    const cashPct = (Number(s.totals.cash) / nw) * 100;
    if (cashPct > 50) {
      out.push({ kind: "info", text: `Kas ${cashPct.toFixed(1)}% dari net worth — sebagian besar dana belum diinvestasikan.` });
    }
  }
  if (s.totals.dividend_yield_pct !== null) {
    out.push({ kind: "info", text: `Dividen 12 bulan terakhir setara ${fmtPct(s.totals.dividend_yield_pct)} dari nilai pasar saham (yield on cost ${fmtPct(s.totals.yield_on_cost_pct)}).` });
  }
  return out;
}

function Onboarding({ depositDone, tradeDone }: { depositDone: boolean; tradeDone: boolean }) {
  const steps = [
    { done: false, title: "Pilih & sinkronkan saham", desc: "Katalog saham IDX dan AS sudah tersedia. Buka halaman Saham lalu klik Sync harga.", to: "/stocks", cta: "Buka Saham" },
    { done: depositDone, title: "Setor modal awal", desc: "Catat dana yang Anda siapkan untuk investasi.", to: "/portfolio", cta: "Setor modal" },
    { done: tradeDone, title: "Catat transaksi pertama", desc: "Masukkan pembelian saham pertama Anda.", to: "/portfolio", cta: "Catat transaksi" },
  ];
  return (
    <section className="card">
      <h2>Mulai dalam 3 langkah</h2>
      <div className="steps">
        {steps.map((s, i) => (
          <div key={s.title} className={`step ${s.done ? "done" : ""}`}>
            <span className="stepnum">{s.done ? <Icon name="check" size={15} /> : i + 1}</span>
            <div>
              <b>{s.title}</b>
              <p className="muted">{s.desc}</p>
              <Link className="btn ghost small" to={s.to}>{s.cta}</Link>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function DashboardSkeleton() {
  return (
    <>
      <div className="card"><Skeleton height={28} width={180} /><div style={{ height: 12 }} /><Skeleton height={44} width={280} /></div>
      <div className="grid stats">
        {[0, 1, 2, 3].map((i) => <div key={i} className="card"><Skeleton height={14} width={90} /><div style={{ height: 10 }} /><Skeleton height={26} /></div>)}
      </div>
    </>
  );
}

export default function Dashboard() {
  const [days, setDays] = useState(365);
  const [view, setView] = useState<"asset" | "sector">("asset");
  const summary = useLoad(() => api.summary(), []);
  const alloc = useLoad(() => api.allocation(), []);
  const perf = useLoad(() => api.performance(days), [days]);

  if (summary.error) return <div className="notice error">{summary.error}</div>;
  if (!summary.data) return <DashboardSkeleton />;
  const { totals: t, holdings, xirr_pct } = summary.data;
  const missingPrice = holdings.some((h) => h.price_source === "cost");
  const hv = Number(t.holdings_value);
  const plUp = Number(t.total_pl) >= 0;
  const brandNew = Number(t.net_deposits) === 0 && holdings.length === 0 && Number(t.realized_pl) === 0;
  const insights = buildInsights(summary.data, alloc.data);

  return (
    <>
      <section className="hero">
        <div className="hero-main">
          <div className="hero-label">Total kekayaan bersih</div>
          <div className="hero-value"><CountUp value={t.net_worth} /></div>
          <div className="hero-meta">
            <span className={`chip ${plUp ? "up" : "down"}`}>
              <Icon name={plUp ? "up" : "down"} size={14} /> {fmt(t.total_pl)} ({fmtPct(t.roi_pct)})
            </span>
            <span className="hero-sub">Saham {fmt(t.holdings_value)} · Kas {fmt(t.cash)}</span>
          </div>
          <div className="hero-actions">
            <Link className="btn light" to="/portfolio"><Icon name="plus" size={15} /> Setor / catat transaksi</Link>
            <Link className="btn glass" to="/stocks">Lihat saham</Link>
          </div>
        </div>
        <div className="hero-spark">
          {perf.data && perf.data.length > 1 && <Sparkline values={perf.data.map((p) => p.net_worth)} />}
        </div>
      </section>

      {brandNew ? (
        <Onboarding depositDone={false} tradeDone={false} />
      ) : (
        <>
          <div className="grid stats">
            <Stat icon="wallet" label="Modal bersih disetor" value={fmt(t.net_deposits)} count={Number(t.net_deposits)} />
            <Stat icon={Number(t.floating_pl) >= 0 ? "up" : "down"} label="Floating P/L" value={fmt(t.floating_pl)} count={Number(t.floating_pl)} tone={tone(t.floating_pl)} />
            <Stat icon="cash" label="Realized P/L" value={fmt(t.realized_pl)} count={Number(t.realized_pl)} tone={tone(t.realized_pl)} />
            <Stat icon="activity" label="Imbal hasil tahunan (XIRR)" value={fmtPct(xirr_pct)} tone={tone(xirr_pct)} sub={xirr_pct === null ? "Butuh data minimal 30 hari" : undefined} />
            <Stat icon="percent" label="Total dividen" value={fmt(t.dividends_total)} count={Number(t.dividends_total)} sub={`Yield ${fmtPct(t.dividend_yield_pct)} · YoC ${fmtPct(t.yield_on_cost_pct)}`} />
          </div>

          {missingPrice && (
            <div className="notice warn">
              Sebagian saham belum punya data harga pasar, sehingga nilainya dihitung dari harga rata-rata.
              Buka halaman <Link to="/stocks">Saham</Link> lalu klik <b>Sync harga</b>.
            </div>
          )}

          {insights.length > 0 && (
            <section className="card">
              <h2>Insight portofolio</h2>
              <ul className="insights">
                {insights.map((i, idx) => (
                  <li key={idx} className={i.kind}>
                    <Icon name={i.kind === "warn" ? "alert" : i.kind === "ok" ? "check" : "info"} size={16} />
                    <span>{i.text}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <div className="grid two">
            <section className="card">
              <div className="cardhead">
                <h2>Alokasi Aset</h2>
                <Segmented
                  value={view} onChange={setView}
                  options={[{ value: "asset", label: "Per saham" }, { value: "sector", label: "Per sektor" }]}
                />
              </div>
              {alloc.error && <div className="notice error">{alloc.error}</div>}
              {alloc.data ? <PieAllocation rows={view === "asset" ? alloc.data.by_asset : alloc.data.by_sector} /> : !alloc.error && <ChartSkeleton height={340} />}
            </section>

            <section className="card">
              <div className="cardhead">
                <h2>Pertumbuhan Portofolio</h2>
                <Segmented value={days} onChange={setDays} options={RANGES.map((r) => ({ value: r.days, label: r.label }))} />
              </div>
              {perf.error && <div className="notice error">{perf.error}</div>}
              {perf.data ? <PerformanceChart points={perf.data} /> : !perf.error && <ChartSkeleton height={340} />}
            </section>
          </div>

          <section className="card">
            <h2>Posisi Saat Ini</h2>
            {holdings.length === 0 ? (
              <p className="muted">Belum ada posisi terbuka. Catat pembelian di halaman <Link to="/portfolio">Transaksi</Link>.</p>
            ) : (
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>
                      <th>Saham</th><th>Sektor</th><th className="r">Lembar</th><th className="r">Harga rata-rata</th>
                      <th className="r">Harga terakhir</th><th className="r">Nilai pasar</th><th className="r">Bobot</th>
                      <th className="r">Untung/Rugi</th><th className="r">%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {holdings.map((h) => (
                      <tr key={h.stock_id}>
                        <td><b>{h.symbol}</b></td>
                        <td>{h.sector ?? "—"}</td>
                        <td className="r">{fmtQty(h.quantity)}</td>
                        <td className="r">{fmt(h.avg_cost)}</td>
                        <td className="r">
                          {fmt(h.price)} {h.price_source === "cost" && <span className="badge">belum ada harga</span>}
                        </td>
                        <td className="r">{fmt(h.market_value)}</td>
                        <td className="r">{hv > 0 ? `${((Number(h.market_value) / hv) * 100).toFixed(1)}%` : "—"}</td>
                        <td className={`r ${tone(h.floating_pl)}`}>{fmt(h.floating_pl)}</td>
                        <td className={`r ${tone(h.floating_pl_pct)}`}>{fmtPct(h.floating_pl_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}
