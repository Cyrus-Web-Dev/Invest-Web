import { useState, type FormEvent } from "react";
import { api } from "../api";
import AnimatedBar from "../components/AnimatedBar";
import Notice, { type NoticeState } from "../components/Notice";
import { fmt, fmtDateTime, fmtPct, fmtQty, normDecimal, tone } from "../format";
import { errMsg, useLoad } from "../hooks";
import type { HoldingValue, TargetItem } from "../types";

interface Row {
  stockId: number; symbol: string; name: string; quantity: string | null; avg: string | null;
  price: string | null; target: TargetItem | null;
}

function TargetForm({
  row, onClose, onSaved,
}: { row: Row; onClose: () => void; onSaved: (m: string) => void }) {
  const [target, setTarget] = useState(row.target?.target_price ?? "");
  const [stop, setStop] = useState(row.target?.stop_price ?? "");
  const [note, setNote] = useState(row.target?.note ?? "");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<NoticeState | null>(null);

  const t = normDecimal(target), s = normDecimal(stop);
  const avg = row.avg ? Number(row.avg) : null;
  const preview: string[] = [];
  if (avg && t) preview.push(`Target ${fmt(t)} = ${fmtPct(((Number(t) / avg - 1) * 100).toFixed(2))} dari harga rata-rata`);
  if (avg && s) preview.push(`Stop loss ${fmt(s)} = ${fmtPct(((Number(s) / avg - 1) * 100).toFixed(2))} dari harga rata-rata`);
  if (avg && t && s && Number(t) > avg && avg > Number(s)) {
    preview.push(`Risk/reward ≈ 1 : ${((Number(t) - avg) / (avg - Number(s))).toFixed(2)}`);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (target.trim() && !t) return setMsg({ kind: "error", text: "Target harga tidak valid." });
    if (stop.trim() && !s) return setMsg({ kind: "error", text: "Stop loss tidak valid." });
    if (!t && !s) return setMsg({ kind: "error", text: "Isi minimal salah satu: target harga atau stop loss." });
    setBusy(true);
    setMsg(null);
    try {
      await api.setTarget(row.stockId, { target_price: t, stop_price: s, note: note.trim() || null });
      onSaved(`Target ${row.symbol} disimpan. Diperiksa otomatis setiap 15 menit selama Anda masih memegang saham ini.`);
    } catch (err) {
      setMsg({ kind: "error", text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <form className="form" onSubmit={submit}>
        <div className="cardhead">
          <h2>Target & stop loss: {row.symbol}</h2>
          <button type="button" className="btn ghost small" onClick={onClose}>Tutup</button>
        </div>
        <p className="muted small">
          Harga rata-rata: <b>{row.avg ? fmt(row.avg) : "— (belum dimiliki)"}</b> · Harga terakhir: <b>{row.price ? fmt(row.price) : "—"}</b>
        </p>
        <div className="row">
          <label>Target jual <input inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="mis. 10500" /></label>
          <label>Stop loss <input inputMode="decimal" value={stop} onChange={(e) => setStop(e.target.value)} placeholder="mis. 8800" /></label>
        </div>
        <label>Catatan / alasan (opsional) <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={255} /></label>
        {preview.length > 0 && <ul className="insights">{preview.map((p) => <li key={p} className="info"><span>{p}</span></li>)}</ul>}
        <Notice state={msg} />
        <button className="btn" disabled={busy}>{busy ? "Menyimpan…" : "Simpan"}</button>
      </form>
    </section>
  );
}

export default function Targets() {
  const summary = useLoad(() => api.summary(), []);
  const targets = useLoad(() => api.targets(), []);
  const stocks = useLoad(() => api.listStocks(), []);
  const [editing, setEditing] = useState<Row | null>(null);
  const [pick, setPick] = useState("");
  const [msg, setMsg] = useState<NoticeState | null>(null);

  const holdings: HoldingValue[] = summary.data?.holdings ?? [];
  const tmap = new Map<number, TargetItem>((targets.data ?? []).map((t) => [t.stock_id, t]));
  const rows: Row[] = holdings.map((h) => ({
    stockId: h.stock_id, symbol: h.symbol, name: h.symbol, quantity: h.quantity, avg: h.avg_cost,
    price: h.price_source === "market" ? h.price : null, target: tmap.get(h.stock_id) ?? null,
  }));
  for (const t of targets.data ?? []) {
    if (!holdings.some((h) => h.stock_id === t.stock_id)) {
      rows.push({ stockId: t.stock_id, symbol: t.symbol, name: t.name, quantity: null, avg: null, price: t.price, target: t });
    }
  }
  const used = new Set(rows.map((r) => r.stockId));
  const addable = (stocks.data ?? []).filter((s) => !used.has(s.id));

  async function remove(r: Row) {
    if (!window.confirm(`Hapus target dan stop loss ${r.symbol}?`)) return;
    setMsg(null);
    try {
      await api.deleteTarget(r.stockId);
      targets.reload();
    } catch (e) {
      setMsg({ kind: "error", text: errMsg(e) });
    }
  }

  function startAdd() {
    const s = (stocks.data ?? []).find((x) => String(x.id) === pick);
    if (!s) return;
    setEditing({ stockId: s.id, symbol: s.symbol, name: s.name, quantity: null, avg: null, price: null, target: null });
    setPick("");
  }

  return (
    <>
      <Notice state={msg} />
      {editing && (
        <TargetForm
          key={editing.stockId} row={editing} onClose={() => setEditing(null)}
          onSaved={(m) => { setEditing(null); setMsg({ kind: "ok", text: m }); targets.reload(); }}
        />
      )}
      <section className="card">
        <div className="cardhead">
          <h2>Target harga & stop loss</h2>
          <div className="searchrow">
            <select value={pick} onChange={(e) => setPick(e.target.value)} style={{ width: 240 }}>
              <option value="">— atur untuk saham lain —</option>
              {addable.map((s) => <option key={s.id} value={s.id}>{s.symbol} · {s.name}</option>)}
            </select>
            <button className="btn ghost small" disabled={!pick} onClick={startAdd}>Atur</button>
          </div>
        </div>
        <p className="muted small">
          Tetapkan rencana keluar sebelum emosi ikut bermain. Notifikasi dikirim sekali saat harga menyentuh target atau stop loss,
          selama Anda masih memegang saham itu. Harga yang dipakai = penutupan terakhir di database (sync dari halaman Saham).
        </p>
        {(summary.error || targets.error) && <div className="notice error">{summary.error ?? targets.error}</div>}
        {rows.length === 0 && summary.data && <p className="muted">Belum ada posisi atau target. Pilih saham di atas untuk mulai.</p>}
        {rows.length > 0 && (
          <div className="tablewrap">
            <table>
              <thead>
                <tr>
                  <th>Saham</th><th className="r">Rata-rata</th><th className="r">Harga</th><th className="r">Target</th>
                  <th className="r">Stop loss</th><th>Progres ke target</th><th className="r">R/R</th><th>Status</th><th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const t = r.target;
                  const progress = t?.progress_pct != null ? Number(t.progress_pct) : null;
                  return (
                    <tr key={r.stockId}>
                      <td><b>{r.symbol}</b><div className="muted small">{r.quantity ? `${fmtQty(r.quantity)} lembar` : "belum dimiliki"}</div></td>
                      <td className="r">{r.avg ? fmt(r.avg) : "—"}</td>
                      <td className="r">{r.price ? fmt(r.price) : "—"}</td>
                      <td className="r">{t?.target_price ? <>{fmt(t.target_price)}<div className={`small ${tone(t.to_target_pct)}`}>{fmtPct(t.to_target_pct)} lagi</div></> : "—"}</td>
                      <td className="r">{t?.stop_price ? <>{fmt(t.stop_price)}<div className={`small ${tone(t.to_stop_pct)}`}>{fmtPct(t.to_stop_pct)} dari harga</div></> : "—"}</td>
                      <td style={{ minWidth: 130 }}>
                        {progress !== null ? (
                          <>
                            <AnimatedBar percent={progress} />
                            <div className="small muted">{progress.toFixed(0)}%</div>
                          </>
                        ) : "—"}
                      </td>
                      <td className="r">{t?.risk_reward ? `1 : ${fmt(t.risk_reward)}` : "—"}</td>
                      <td>
                        {t?.target_hit_at && <span className="badge buy" title={fmtDateTime(t.target_hit_at)}>Target tercapai</span>}
                        {t?.stop_hit_at && <span className="badge sell" title={fmtDateTime(t.stop_hit_at)}>Stop tersentuh</span>}
                        {t && !t.target_hit_at && !t.stop_hit_at && <span className="badge neutral">Aktif</span>}
                        {!t && <span className="muted small">Belum diatur</span>}
                      </td>
                      <td className="r">
                        <button className="btn ghost small" onClick={() => setEditing(r)}>{t ? "Ubah" : "Atur"}</button>{" "}
                        {t && <button className="btn ghost small" onClick={() => remove(r)}>Hapus</button>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
