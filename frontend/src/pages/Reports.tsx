import { useEffect, useState } from "react";
import { api, downloadFile } from "../api";
import { PageSkeleton } from "../components/ChartSkeleton";
import Notice, { type NoticeState } from "../components/Notice";
import Stat from "../components/Stat";
import { fmt, fmtQty, tone } from "../format";
import { errMsg, useLoad } from "../hooks";

export default function Reports() {
  const years = useLoad(() => api.reportYears(), []);
  const [year, setYear] = useState<number | null>(null);
  const [msg, setMsg] = useState<NoticeState | null>(null);

  useEffect(() => {
    if (year === null && years.data && years.data.length > 0) setYear(years.data[0]);
  }, [year, years.data]);

  const report = useLoad(() => (year ? api.annualReport(year) : Promise.resolve(null)), [year]);

  async function download(path: string, name: string) {
    setMsg(null);
    try {
      await downloadFile(path, name);
    } catch (e) {
      setMsg({ kind: "error", text: errMsg(e) });
    }
  }

  if (years.error) return <div className="notice error">{years.error}</div>;
  if (!years.data || (year !== null && !report.data && !report.error)) return <PageSkeleton />;
  const r = report.data;

  return (
    <>
      <Notice state={msg} />
      <section className="card">
        <div className="cardhead">
          <h2>Laporan tahunan</h2>
          <div className="btnrow">
            <select value={year ?? ""} onChange={(e) => setYear(Number(e.target.value))} style={{ width: "auto" }}>
              {years.data.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            <button className="btn" disabled={!year} onClick={() => year && download(`/reports/annual.pdf?year=${year}`, `stockfolio-laporan-${year}.pdf`)}>Unduh PDF</button>
            <button className="btn ghost" disabled={!year} onClick={() => year && download(`/reports/realized.csv?year=${year}`, `stockfolio-penjualan-${year}.csv`)}>CSV penjualan</button>
          </div>
        </div>
        <p className="muted small">
          Ringkasan penjualan, laba/rugi terealisasi, dividen, dan posisi akhir tahun yang dihitung dari catatan Anda. Berguna sebagai bahan
          pelaporan pajak, tetapi bukan nasihat pajak dan bukan dokumen resmi.
        </p>
      </section>
      {report.error && <div className="notice error">{report.error}</div>}

      {r && (
        <>
          <div className="grid stats">
            <Stat icon="cash" label="Hasil penjualan bruto" value={fmt(r.totals.gross_sales)} count={Number(r.totals.gross_sales)} sub={`${r.totals.sales_count} penjualan`} />
            <Stat icon="up" label="Laba/rugi terealisasi" value={fmt(r.totals.realized_pl)} count={Number(r.totals.realized_pl)} tone={tone(r.totals.realized_pl)} />
            <Stat icon="percent" label="Dividen diterima" value={fmt(r.totals.dividends)} count={Number(r.totals.dividends)} />
            <Stat icon="wallet" label="Harga perolehan yang dijual" value={fmt(r.totals.cost_basis)} sub={`Fee jual ${fmt(r.totals.sell_fees)}`} />
          </div>

          <div className="grid two">
            <section className="card">
              <h2>Per saham</h2>
              {r.by_stock.length === 0 ? <p className="muted">Tidak ada penjualan atau dividen pada {r.year}.</p> : (
                <div className="tablewrap"><table>
                  <thead><tr><th>Saham</th><th className="r">Hasil jual</th><th className="r">Harga perolehan</th><th className="r">Laba/rugi</th><th className="r">Dividen</th></tr></thead>
                  <tbody>{r.by_stock.map((s) => (
                    <tr key={s.symbol}><td><b>{s.symbol}</b></td><td className="r">{fmt(s.gross)}</td><td className="r">{fmt(s.cost_basis)}</td>
                      <td className={`r ${tone(s.realized)}`}>{fmt(s.realized)}</td><td className="r">{fmt(s.dividends)}</td></tr>
                  ))}</tbody>
                </table></div>
              )}
            </section>
            <section className="card">
              <h2>Posisi per {r.as_of}</h2>
              {r.positions.length === 0 ? <p className="muted">Tidak ada posisi terbuka.</p> : (
                <div className="tablewrap"><table>
                  <thead><tr><th>Saham</th><th className="r">Lembar</th><th className="r">Harga perolehan</th><th className="r">Nilai pasar</th></tr></thead>
                  <tbody>{r.positions.map((p) => (
                    <tr key={p.symbol}><td><b>{p.symbol}</b></td><td className="r">{fmtQty(p.quantity)}</td><td className="r">{fmt(p.total_cost)}</td>
                      <td className="r">{p.market_value ? fmt(p.market_value) : <span className="badge">belum ada harga</span>}</td></tr>
                  ))}</tbody>
                </table></div>
              )}
            </section>
          </div>

          <section className="card">
            <h2>Rincian penjualan {r.year}</h2>
            {r.sales.length === 0 ? <p className="muted">Tidak ada penjualan.</p> : (
              <div className="tablewrap"><table>
                <thead><tr><th>Tanggal</th><th>Saham</th><th className="r">Lembar</th><th className="r">Nilai bruto</th><th className="r">Fee</th><th className="r">Harga perolehan</th><th className="r">Laba/rugi</th></tr></thead>
                <tbody>{r.sales.map((s, i) => (
                  <tr key={i}><td>{s.day}</td><td><b>{s.symbol}</b></td><td className="r">{fmtQty(s.quantity)}</td><td className="r">{fmt(s.gross)}</td>
                    <td className="r">{fmt(s.fee)}</td><td className="r">{fmt(s.cost_basis)}</td><td className={`r ${tone(s.realized)}`}>{fmt(s.realized)}</td></tr>
                ))}</tbody>
              </table></div>
            )}
          </section>

          <section className="card">
            <h2>Catatan penting</h2>
            <ul className="insights">{r.notes.map((n, i) => <li key={i} className="info"><span>{n}</span></li>)}</ul>
          </section>
        </>
      )}
    </>
  );
}
