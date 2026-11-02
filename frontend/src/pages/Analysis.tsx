import { useState } from "react";
import { api } from "../api";
import AnimatedBar from "../components/AnimatedBar";
import BenchmarkChart from "../components/BenchmarkChart";
import ContributionBars from "../components/ContributionBars";
import Heatmap from "../components/Heatmap";
import ChartSkeleton from "../components/ChartSkeleton";
import Segmented from "../components/Segmented";
import Notice, { type NoticeState } from "../components/Notice";
import Stat from "../components/Stat";
import { fmt, fmtPct, tone } from "../format";
import { errMsg, useLoad } from "../hooks";

const RANGES = [
  { label: "3 Bulan", days: 90 },
  { label: "1 Tahun", days: 365 },
  { label: "3 Tahun", days: 1095 },
  { label: "Semua", days: 3650 },
];

const MONTHS_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];

const pctText = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${fmt(v, 2)}%`);

export default function Analysis() {
  const [days, setDays] = useState(365);
  const [benchId, setBenchId] = useState<number | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [msg, setMsg] = useState<NoticeState | null>(null);

  const benchmarks = useLoad(() => api.benchmarks(), []);
  const list = benchmarks.data ?? [];
  const activeId = benchId ?? (list.length > 0 ? list[0].id : null);
  const active = list.find((b) => b.id === activeId) ?? null;
  const compare = useLoad(
    () => (activeId ? api.benchmarkCompare(activeId, days) : Promise.resolve(null)),
    [activeId, days],
  );
  const risk = useLoad(() => api.risk(days, activeId), [activeId, days]);
  const attribution = useLoad(() => api.attribution(), []);
  const monthly = useLoad(() => api.monthlyReturns(), []);

  async function syncIndex(years: number) {
    if (!activeId) return;
    setSyncing(true);
    setMsg(null);
    try {
      const r = await api.syncStock(activeId, years * 365);
      setMsg({
        kind: r.upserted > 0 ? "ok" : "error",
        text: r.upserted > 0 ? `Berhasil menyimpan ${r.upserted} baris data indeks.` : "Penyedia tidak mengembalikan data indeks.",
      });
      benchmarks.reload();
      compare.reload();
      risk.reload();
    } catch (e) {
      setMsg({ kind: "error", text: errMsg(e) });
    } finally {
      setSyncing(false);
    }
  }

  const c = compare.data;
  const r = risk.data;
  const d = r?.diversification ?? null;
  const needData = "Butuh data lebih panjang";

  return (
    <>
      <Notice state={msg} />
      <section className="card">
        <div className="cardhead">
          <h2>Portofolio vs indeks</h2>
          <div className="btnrow">
            <select value={activeId ?? ""} onChange={(e) => setBenchId(Number(e.target.value))} style={{ width: "auto" }}>
              {list.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <Segmented value={days} onChange={setDays} options={RANGES.map((x) => ({ value: x.days, label: x.label }))} />
          </div>
        </div>
        <p className="muted small">
          Membandingkan hasil portofolio Anda dengan seandainya <b>modal yang sama</b> (setoran dan penarikan di tanggal yang sama)
          diinvestasikan seluruhnya di indeks. Perbandingan memakai nilai indeks apa adanya, tanpa konversi kurs.
        </p>
        {compare.error && <div className="notice error">{compare.error}</div>}
        {c?.warning && <div className="notice warn">{c.warning}</div>}
        {active && (
          <div className="btnrow" style={{ margin: "8px 0" }}>
            <span className="muted small" style={{ alignSelf: "center" }}>
              Data {active.symbol}: {active.first_date ? `${active.first_date} s/d ${active.last_date}` : "belum ada"}
            </span>
            <button className="btn ghost small" disabled={syncing} onClick={() => syncIndex(1)}>Sync 1 tahun</button>
            <button className="btn ghost small" disabled={syncing} onClick={() => syncIndex(3)}>Sync 3 tahun</button>
            <button className="btn ghost small" disabled={syncing} onClick={() => syncIndex(5)}>Sync 5 tahun</button>
          </div>
        )}
        {c && c.points.length > 0 && (
          <>
            <div className="grid stats">
              <Stat label="Return portofolio (sejak awal)" value={pctText(c.portfolio_return_pct)} tone={tone(c.portfolio_return_pct)} />
              <Stat label={`Return ${c.symbol} (modal sama)`} value={pctText(c.benchmark_return_pct)} tone={tone(c.benchmark_return_pct)} />
              <Stat
                label="Selisih (alpha)" value={pctText(c.alpha_pct)} tone={tone(c.alpha_pct)}
                sub={c.alpha_pct === null ? undefined : c.alpha_pct >= 0 ? "Mengungguli indeks" : "Tertinggal dari indeks"}
              />
            </div>
            <BenchmarkChart points={c.points} benchmarkName={c.symbol} />
          </>
        )}
        {compare.loading && !c && <ChartSkeleton />}
        {c && c.points.length === 0 && !c.warning && <p className="muted">Belum ada data untuk ditampilkan.</p>}
      </section>

      <div className="grid two">
        <section className="card">
          <h2>Risiko portofolio</h2>
          <p className="muted small">
            Dihitung dari return harian time-weighted (setoran dan penarikan tidak memengaruhi hasil), hari kerja saja, periode {days >= 3650 ? "seluruh riwayat" : `${days} hari terakhir`}.
            {r ? ` Jumlah observasi: ${r.observations}.` : ""}
          </p>
          {risk.error && <div className="notice error">{risk.error}</div>}
          {r && (
            <div className="grid stats">
              <Stat label="Return time-weighted" value={pctText(r.twr_pct)} tone={tone(r.twr_pct)} sub={r.twr_pct === null ? needData : undefined} />
              <Stat label="Volatilitas (tahunan)" value={pctText(r.volatility_pct)} sub={r.volatility_pct === null ? "Butuh ≥ 20 hari data" : "Makin tinggi = makin berfluktuasi"} />
              <Stat
                label="Max drawdown" value={pctText(r.max_drawdown_pct)} tone={tone(r.max_drawdown_pct)}
                sub={r.drawdown_peak && r.max_drawdown_pct !== 0 ? `${r.drawdown_peak} → ${r.drawdown_trough}` : r.max_drawdown_pct === null ? needData : "Belum ada penurunan"}
              />
              <Stat
                label={`Beta vs ${r.benchmark_symbol ?? "indeks"}`} value={r.beta === null ? "—" : fmt(r.beta, 2)}
                sub={r.beta === null ? (r.benchmark_symbol ? "Butuh ≥ 30 hari data & indeks" : "Pilih indeks pembanding") : r.beta > 1 ? "Lebih fluktuatif dari indeks" : "Kurang fluktuatif dari indeks"}
              />
            </div>
          )}
        </section>

        <section className="card">
          <h2>Diversifikasi</h2>
          {!d && <p className="muted">Belum ada posisi saham untuk dianalisis.</p>}
          {d && (
            <>
              <div className="scoreline">
                <b className="scorenum">{d.score}</b><span className="muted">/ 100 skor diversifikasi</span>
              </div>
              <AnimatedBar percent={d.score} />
              <ul className="insights" style={{ marginTop: 12 }}>
                <li className="info"><span>{d.holdings} saham di {d.sectors} sektor — setara {fmt(d.effective_n, 1)} saham berbobot sama</span></li>
                <li className="info"><span>Saham terbesar {fmt(d.top1_pct, 1)}% · tiga terbesar {fmt(d.top3_pct, 1)}%</span></li>
                {d.top_sector && <li className="info"><span>Sektor terbesar: {d.top_sector} ({fmt(d.top_sector_pct, 1)}%)</span></li>}
              </ul>
            </>
          )}
          {r && r.warnings.length > 0 && (
            <ul className="insights" style={{ marginTop: 10 }}>
              {r.warnings.map((w, i) => <li key={i} className="warn"><span>{w}</span></li>)}
            </ul>
          )}
          <p className="muted small" style={{ marginTop: 10 }}>
            Skor = (1 − HHI) × 100 dari bobot antar saham (kas tidak dihitung): 1 saham = 0, 2 saham sama besar = 50, 10 saham sama besar = 90.
            Ambang peringatan (30% per saham, 50% per sektor) hanyalah acuan umum.
          </p>
        </section>
      </div>

      <section className="card">
        <h2>Kontribusi per saham</h2>
        <p className="muted small">
          Total untung/rugi tiap saham sejak awal = terealisasi + belum terealisasi + dividen. Jumlahnya sama dengan total untung/rugi
          portofolio, sehingga terlihat saham mana yang paling mendorong (atau menyeret) hasil Anda, termasuk yang sudah dijual.
        </p>
        {attribution.error && <div className="notice error">{attribution.error}</div>}
        {attribution.data && attribution.data.rows.length === 0 && <p className="muted">Belum ada transaksi.</p>}
        {attribution.data && attribution.data.rows.length > 0 && (
          <>
            <ContributionBars rows={attribution.data.rows.map((r) => ({ symbol: r.symbol, total: Number(r.total) }))} />
            <div className="tablewrap" style={{ marginTop: 14 }}>
              <table>
                <thead>
                  <tr>
                    <th>Saham</th><th className="r">Modal dibeli</th><th className="r">Terealisasi</th><th className="r">Belum terealisasi</th>
                    <th className="r">Dividen</th><th className="r">Total</th><th className="r">Porsi laba</th>
                    <th className="r">Kontribusi return</th><th className="r">Return thd modal</th>
                  </tr>
                </thead>
                <tbody>
                  {attribution.data.rows.map((r) => (
                    <tr key={r.symbol}>
                      <td><b>{r.symbol}</b> {!r.held && <span className="badge neutral">sudah dijual</span>}</td>
                      <td className="r">{fmt(r.invested)}</td>
                      <td className={`r ${tone(r.realized)}`}>{fmt(r.realized)}</td>
                      <td className={`r ${tone(r.floating)}`}>{fmt(r.floating)}</td>
                      <td className="r">{fmt(r.dividends)}</td>
                      <td className={`r ${tone(r.total)}`}><b>{fmt(r.total)}</b></td>
                      <td className="r">{fmtPct(r.share_of_pl_pct)}</td>
                      <td className={`r ${tone(r.contribution_to_return_pct)}`}>{fmtPct(r.contribution_to_return_pct)}</td>
                      <td className={`r ${tone(r.return_on_cost_pct)}`}>{fmtPct(r.return_on_cost_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted small" style={{ marginTop: 8 }}>
              Total untung/rugi portofolio: <b>{fmt(attribution.data.total_pl)}</b> dari modal bersih {fmt(attribution.data.net_deposits)}.
              Kontribusi return = total saham itu ÷ modal bersih disetor. Porsi laba hanya ditampilkan bila total portofolio positif.
              {Math.abs(Number(attribution.data.residual)) >= 1 && ` Selisih pembulatan: ${fmt(attribution.data.residual)}.`}
            </p>
          </>
        )}
      </section>

      <section className="card">
        <h2>Return bulanan</h2>
        <p className="muted small">
          Return time-weighted per bulan (setoran dan penarikan tidak memengaruhi hasil). Hijau = bulan positif, merah = negatif.
          Bulan pertama dan bulan berjalan baru mencakup sebagian hari.
        </p>
        {monthly.error && <div className="notice error">{monthly.error}</div>}
        {monthly.loading && !monthly.data && <ChartSkeleton height={160} />}
        {monthly.data && monthly.data.rows.length === 0 && <p className="muted">Belum cukup data untuk return bulanan.</p>}
        {monthly.data && monthly.data.rows.length > 0 && (
          <>
            <Heatmap rows={monthly.data.rows} />
            <div className="grid stats" style={{ marginTop: 14, marginBottom: 0 }}>
              {monthly.data.best && (
                <Stat label="Bulan terbaik" value={`${monthly.data.best.pct.toFixed(2)}%`} tone="pos" sub={`${MONTHS_ID[monthly.data.best.month - 1]} ${monthly.data.best.year}`} />
              )}
              {monthly.data.worst && (
                <Stat label="Bulan terburuk" value={`${monthly.data.worst.pct.toFixed(2)}%`} tone={monthly.data.worst.pct < 0 ? "neg" : "pos"} sub={`${MONTHS_ID[monthly.data.worst.month - 1]} ${monthly.data.worst.year}`} />
              )}
              <Stat
                label="Bulan positif" value={`${monthly.data.positive_months} dari ${monthly.data.total_months}`}
                sub={monthly.data.total_months > 0 ? `${((monthly.data.positive_months / monthly.data.total_months) * 100).toFixed(0)}% bulan` : undefined}
              />
            </div>
          </>
        )}
      </section>
    </>
  );
}
