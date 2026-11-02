import { useState, type FormEvent } from "react";
import { api } from "../api";
import Icon from "../components/icons";
import Notice, { type NoticeState } from "../components/Notice";
import { fmt, fmtDateTime, fmtPct, normDecimal, tone } from "../format";
import { errMsg, useLoad } from "../hooks";
import type { AlertItem, Stock, WatchItem } from "../types";

const condition = (a: AlertItem) => `${a.direction === "ABOVE" ? "Naik ≥" : "Turun ≤"} ${fmt(a.target_price)}`;

function AlertForm({
  stocks, watch, initialStockId, onDone,
}: { stocks: Stock[]; watch: WatchItem[]; initialStockId: string; onDone: () => void }) {
  const [stockId, setStockId] = useState(initialStockId);
  const [direction, setDirection] = useState<"ABOVE" | "BELOW">("BELOW");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<NoticeState | null>(null);
  const current = watch.find((w) => String(w.stock_id) === stockId);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const t = normDecimal(target);
    if (!stockId || !t) return setMsg({ kind: "error", text: "Pilih saham dan isi harga target dengan angka yang valid." });
    setBusy(true);
    setMsg(null);
    try {
      await api.createAlert({ stock_id: Number(stockId), direction, target_price: t });
      setTarget("");
      setMsg({ kind: "ok", text: "Alert dibuat. Diperiksa otomatis setiap 15 menit." });
      onDone();
    } catch (err) {
      setMsg({ kind: "error", text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="form">
      <h3>Buat alert harga</h3>
      <label>Saham
        <select value={stockId} onChange={(e) => setStockId(e.target.value)} required>
          <option value="">— pilih saham —</option>
          {stocks.map((s) => <option key={s.id} value={s.id}>{s.symbol} · {s.name}</option>)}
        </select>
      </label>
      <div className="row">
        <label>Kondisi
          <select value={direction} onChange={(e) => setDirection(e.target.value as "ABOVE" | "BELOW")}>
            <option value="BELOW">Turun hingga ≤</option>
            <option value="ABOVE">Naik mencapai ≥</option>
          </select>
        </label>
        <label>Harga target <input inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} required /></label>
      </div>
      {current?.price && <p className="muted small">Harga terakhir {current.symbol}: <b>{fmt(current.price)}</b> ({current.price_date})</p>}
      <Notice state={msg} />
      <button className="btn" disabled={busy}>{busy ? "Menyimpan…" : "Buat alert"}</button>
    </form>
  );
}

export default function Watchlist() {
  const stocks = useLoad(() => api.listStocks(), []);
  const watch = useLoad(() => api.watchlist(), []);
  const alerts = useLoad(() => api.alerts(), []);
  const [pick, setPick] = useState("");
  const [alertStock, setAlertStock] = useState("");
  const [msg, setMsg] = useState<NoticeState | null>(null);

  const stockList = stocks.data ?? [];
  const watchList = watch.data ?? [];
  const watchedIds = new Set(watchList.map((w) => w.stock_id));
  const addable = stockList.filter((s) => !watchedIds.has(s.id));
  const active = (alerts.data ?? []).filter((a) => a.is_active);
  const history = (alerts.data ?? []).filter((a) => !a.is_active);

  async function add() {
    if (!pick) return;
    setMsg(null);
    try {
      await api.addWatch(Number(pick));
      setPick("");
      watch.reload();
    } catch (e) {
      setMsg({ kind: "error", text: errMsg(e) });
    }
  }

  async function remove(id: number) {
    setMsg(null);
    try {
      await api.removeWatch(id);
      watch.reload();
    } catch (e) {
      setMsg({ kind: "error", text: errMsg(e) });
    }
  }

  async function removeAlert(id: number) {
    setMsg(null);
    try {
      await api.deleteAlert(id);
      alerts.reload();
    } catch (e) {
      setMsg({ kind: "error", text: errMsg(e) });
    }
  }

  return (
    <>
      <div className="grid two">
        <section className="card">
          <h2>Daftar pantauan</h2>
          <div className="searchrow" style={{ marginBottom: 10 }}>
            <select value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">— tambah saham ke pantauan —</option>
              {addable.map((s) => <option key={s.id} value={s.id}>{s.symbol} · {s.name}</option>)}
            </select>
            <button className="btn" onClick={add} disabled={!pick}>Pantau</button>
          </div>
          <Notice state={msg} />
          {watch.error && <div className="notice error">{watch.error}</div>}
          {watch.data && watchList.length === 0 && (
            <p className="muted">Belum ada saham yang dipantau. Pilih saham di atas untuk mulai memantau harga tanpa harus membelinya.</p>
          )}
          {watchList.length > 0 && (
            <div className="tablewrap">
              <table>
                <thead>
                  <tr><th>Saham</th><th className="r">Harga</th><th className="r">Perubahan</th><th /></tr>
                </thead>
                <tbody>
                  {watchList.map((w) => (
                    <tr key={w.stock_id}>
                      <td><b>{w.symbol}</b><div className="muted small">{w.name}</div></td>
                      <td className="r">{w.price ? `${fmt(w.price)} ${w.currency}` : <span className="badge">belum ada harga</span>}</td>
                      <td className={`r ${tone(w.change_pct)}`}>{fmtPct(w.change_pct)}</td>
                      <td className="r">
                        <button className="btn ghost small" onClick={() => setAlertStock(String(w.stock_id))}>Alert</button>{" "}
                        <button className="iconbtn" onClick={() => remove(w.stock_id)} aria-label="Hapus" title="Hapus"><Icon name="trash" size={15} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="muted small" style={{ marginTop: 10 }}>
            Harga diambil dari penutupan terakhir di database. Sync harga dari halaman Saham agar data terbaru.
          </p>
        </section>

        <section className="card">
          <AlertForm
            key={alertStock}
            stocks={stockList}
            watch={watchList}
            initialStockId={alertStock}
            onDone={alerts.reload}
          />
        </section>
      </div>

      <section className="card">
        <h2>Alert aktif</h2>
        {alerts.error && <div className="notice error">{alerts.error}</div>}
        {alerts.data && active.length === 0 && <p className="muted">Belum ada alert aktif.</p>}
        {active.length > 0 && (
          <div className="tablewrap">
            <table>
              <thead><tr><th>Saham</th><th>Kondisi</th><th>Dibuat</th><th /></tr></thead>
              <tbody>
                {active.map((a) => (
                  <tr key={a.id}>
                    <td><b>{a.symbol}</b></td>
                    <td>{condition(a)}</td>
                    <td>{fmtDateTime(a.created_at)}</td>
                    <td className="r"><button className="iconbtn" onClick={() => removeAlert(a.id)} aria-label="Hapus alert" title="Hapus"><Icon name="trash" size={15} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {history.length > 0 && (
        <section className="card">
          <h2>Riwayat alert terpicu</h2>
          <div className="tablewrap">
            <table>
              <thead><tr><th>Saham</th><th>Kondisi</th><th>Terpicu</th><th className="r">Harga saat terpicu</th><th /></tr></thead>
              <tbody>
                {history.map((a) => (
                  <tr key={a.id}>
                    <td><b>{a.symbol}</b></td>
                    <td>{condition(a)}</td>
                    <td>{a.triggered_at ? fmtDateTime(a.triggered_at) : "—"}</td>
                    <td className="r">{fmt(a.triggered_price)}</td>
                    <td className="r"><button className="iconbtn" onClick={() => removeAlert(a.id)} aria-label="Hapus" title="Hapus"><Icon name="trash" size={15} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
