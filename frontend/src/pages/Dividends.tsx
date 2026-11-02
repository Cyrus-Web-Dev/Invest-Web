import { Link } from "react-router-dom";
import { api } from "../api";
import { PageSkeleton } from "../components/ChartSkeleton";
import DividendChart from "../components/DividendChart";
import Skeleton from "../components/Skeleton";
import Stat from "../components/Stat";
import { fmt, fmtPct, fmtQty } from "../format";
import { useLoad } from "../hooks";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

export default function Dividends() {
  const data = useLoad(() => api.dividendAnalytics(), []);
  if (data.error) return <div className="notice error">{data.error}</div>;
  if (!data.data) return <PageSkeleton />;
  const d = data.data;
  const empty = d.by_stock.length === 0;
  const currentMonth = new Date().getMonth() + 1;

  return (
    <>
      <div className="grid stats">
        <Stat icon="percent" label="Total dividen diterima" value={fmt(d.total_all_time)} count={Number(d.total_all_time)} />
        <Stat icon="cash" label="12 bulan terakhir" value={fmt(d.last_12m)} count={Number(d.last_12m)} />
        <Stat icon="wallet" label="Tahun ini" value={fmt(d.ytd)} count={Number(d.ytd)} />
        <Stat icon="up" label="Estimasi per bulan" value={fmt(d.avg_per_month)} count={Number(d.avg_per_month)} sub={`≈ ${fmt(d.annual_projection)} per tahun`} />
      </div>

      {empty && (
        <div className="notice warn">
          Belum ada dividen tercatat. Catat dividen di halaman <Link to="/portfolio">Transaksi</Link> atau impor lewat CSV
          untuk melihat pendapatan pasif, yield, dan kalender perkiraan di sini.
        </div>
      )}

      <section className="card">
        <h2>Dividen per bulan (24 bulan terakhir)</h2>
        <DividendChart data={d.monthly} />
      </section>

      <section className="card">
        <h2>Kalender dividen (perkiraan)</h2>
        <p className="muted small">
          Disusun dari catatan dividen Anda selama 24 bulan terakhir untuk saham yang <b>masih dimiliki</b>: bulan dan nominal
          mengikuti pola yang pernah terjadi (rata-rata per tahun). Ini bukan jadwal resmi emiten, dan nominal belum
          menyesuaikan perubahan jumlah lembar Anda.
        </p>
        <div className="calgrid">
          {d.calendar.map((c) => (
            <div key={c.month} className={`calcell ${Number(c.amount) > 0 ? "has" : ""} ${c.month === currentMonth ? "now" : ""}`}>
              <div className="calmonth">{MONTHS[c.month - 1]}</div>
              <div className="calamt">{Number(c.amount) > 0 ? fmt(c.amount, 0) : "—"}</div>
              <div className="calsym">{c.symbols.join(", ")}</div>
            </div>
          ))}
        </div>
      </section>

      <div className="grid two">
        <section className="card">
          <h2>Per saham</h2>
          {empty ? <p className="muted">Belum ada data.</p> : (
            <div className="tablewrap">
              <table>
                <thead>
                  <tr><th>Saham</th><th className="r">Total</th><th className="r">12 bln</th><th className="r">Yield on cost</th><th className="r">Yield kini</th><th className="r">Terakhir</th></tr>
                </thead>
                <tbody>
                  {d.by_stock.map((s) => (
                    <tr key={s.symbol}>
                      <td><b>{s.symbol}</b> {!s.held && <span className="badge neutral">tidak dimiliki</span>}
                        <div className="muted small">{s.payments}x{s.quantity ? ` · ${fmtQty(s.quantity)} lembar` : ""}</div></td>
                      <td className="r">{fmt(s.total)}</td>
                      <td className="r">{fmt(s.last_12m)}</td>
                      <td className="r">{fmtPct(s.yield_on_cost_pct)}</td>
                      <td className="r">{fmtPct(s.current_yield_pct)}</td>
                      <td className="r">{s.last_paid}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="muted small" style={{ marginTop: 8 }}>
            Yield on cost = dividen 12 bulan ÷ modal yang tertanam di saham itu. Yield kini = dividen 12 bulan ÷ nilai pasar saat ini.
          </p>
        </section>

        <section className="card">
          <h2>Per tahun</h2>
          {d.yearly.length === 0 ? <p className="muted">Belum ada data.</p> : (
            <div className="tablewrap">
              <table>
                <thead><tr><th>Tahun</th><th className="r">Dividen diterima</th></tr></thead>
                <tbody>
                  {[...d.yearly].reverse().map((y) => (
                    <tr key={y.year}><td>{y.year}</td><td className="r">{fmt(y.amount)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
