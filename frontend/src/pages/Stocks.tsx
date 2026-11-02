import { useState, type FormEvent } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import CandlestickChart from "../components/CandlestickChart";
import Notice, { type NoticeState } from "../components/Notice";
import Segmented from "../components/Segmented";
import Stat from "../components/Stat";
import { fmt, fmtPct, tone } from "../format";
import { errMsg, useLoad } from "../hooks";
import type { Stock } from "../types";

const RANGES = [
  { label: "1 Bulan", days: 30 },
  { label: "3 Bulan", days: 90 },
  { label: "6 Bulan", days: 180 },
  { label: "1 Tahun", days: 365 },
];

function StockDetail({ stock }: { stock: Stock }) {
  const [days, setDays] = useState(180);
  const [msg, setMsg] = useState<NoticeState | null>(null);
  const [syncing, setSyncing] = useState(false);
  const prices = useLoad(() => api.prices(stock.id, days), [stock.id, days]);
  const quote = useLoad(() => api.quote(stock.id), [stock.id]);
  const watch = useLoad(() => api.watchlist(), [stock.id]);
  const watched = watch.data?.some((w) => w.stock_id === stock.id) ?? false;

  async function toggleWatch() {
    try {
      if (watched) await api.removeWatch(stock.id);
      else await api.addWatch(stock.id);
      watch.reload();
    } catch (e) {
      setMsg({ kind: "error", text: errMsg(e) });
    }
  }

  async function sync() {
    setSyncing(true);
    setMsg(null);
    try {
      const r = await api.syncStock(stock.id);
      setMsg({
        kind: r.upserted > 0 ? "ok" : "error",
        text: r.upserted > 0
          ? `Berhasil menyimpan ${r.upserted} baris data harga.`
          : "Penyedia tidak mengembalikan data. Periksa simbol (saham IDX memakai akhiran .JK, mis. BBCA.JK).",
      });
      prices.reload();
      quote.reload();
    } catch (e) {
      setMsg({ kind: "error", text: errMsg(e) });
    } finally {
      setSyncing(false);
    }
  }

  const bars = prices.data ?? [];
  const last = bars.length > 0 ? bars[bars.length - 1] : null;
  const prev = bars.length > 1 ? bars[bars.length - 2] : null;
  const change = last && prev ? Number(last.close) - Number(prev.close) : null;
  const changePct = change !== null && prev && Number(prev.close) > 0 ? (change / Number(prev.close)) * 100 : null;
  const high = bars.length > 0 ? Math.max(...bars.map((b) => Number(b.high))) : null;
  const low = bars.length > 0 ? Math.min(...bars.map((b) => Number(b.low))) : null;

  return (
    <section className="card">
      <div className="cardhead">
        <h2>{stock.symbol} <span className="muted">· {stock.name}</span></h2>
        <div className="btnrow">
          <button className="btn ghost" onClick={toggleWatch}>{watched ? "Hapus dari pantauan" : "+ Pantau"}</button>
          <button className="btn" onClick={sync} disabled={syncing}>{syncing ? "Menyinkronkan…" : "Sync harga"}</button>
        </div>
      </div>
      <div className="tags">
        <span className="badge neutral">{stock.exchange}</span>
        <span className="badge neutral">{stock.currency}</span>
        {stock.sector && <span className="badge neutral">{stock.sector}</span>}
      </div>
      <Notice state={msg} />
      <div className="grid stats" style={{ marginTop: 12 }}>
        {quote.data ? (
          <Stat label="Harga terakhir" value={`${fmt(quote.data.price)} ${stock.currency}`} sub={`${quote.data.as_of} · sumber: ${quote.data.source}`} />
        ) : (
          <Stat label="Harga terakhir" value="—" sub={quote.error ?? "Memuat…"} />
        )}
        <Stat
          label="Perubahan terakhir"
          value={change === null ? "—" : fmt(change)}
          tone={tone(change)}
          sub={changePct === null ? undefined : fmtPct(changePct.toFixed(2))}
        />
        <Stat label="Tertinggi (periode)" value={high === null ? "—" : fmt(high)} />
        <Stat label="Terendah (periode)" value={low === null ? "—" : fmt(low)} />
      </div>
      <div style={{ margin: "12px 0" }}>
        <Segmented value={days} onChange={setDays} options={RANGES.map((r) => ({ value: r.days, label: r.label }))} />
      </div>
      {prices.error && <div className="notice error">{prices.error}</div>}
      {prices.data && prices.data.length === 0 && (
        <p className="muted">Belum ada data harga untuk rentang ini. Klik <b>Sync harga</b>.</p>
      )}
      {prices.data && prices.data.length > 0 && <div className="fadein"><CandlestickChart bars={prices.data} /></div>}
    </section>
  );
}

function AddStockForm({ onCreated, isAdmin }: { onCreated: (s: Stock) => void; isAdmin: boolean }) {
  const [symbol, setSymbol] = useState("");
  const [name, setName] = useState("");
  const [exchange, setExchange] = useState("IDX");
  const [currency, setCurrency] = useState("IDR");
  const [sector, setSector] = useState("");
  const [kind, setKind] = useState<"STOCK" | "INDEX">("STOCK");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<NoticeState | null>(null);

  function onSymbol(v: string) {
    setSymbol(v);
    if (v.trim().toUpperCase().endsWith(".JK")) {   // saham IDX: isi otomatis bursa dan mata uang
      setExchange("IDX");
      setCurrency("IDR");
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const s = await api.createStock({
        symbol: symbol.trim(), name: name.trim(), exchange: exchange.trim(),
        currency: currency.trim(), sector: sector.trim() || null, kind,
      });
      setSymbol(""); setName(""); setSector("");
      let syncNote = 'Klik "Sync harga" untuk mengambil data.';
      try {
        const r = await api.syncStock(s.id);
        syncNote = r.upserted > 0 ? `Data harga ${r.upserted} baris berhasil diambil.` : 'Data harga belum tersedia; coba "Sync harga" nanti.';
      } catch {
        /* sync bisa dicoba manual dari tombol Sync harga */
      }
      setMsg({ kind: "ok", text: `${s.symbol} ditambahkan. ${syncNote}` });
      onCreated(s);
    } catch (err) {
      setMsg({ kind: "error", text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="form">
      <h3>Tambah saham lain</h3>
      {!isAdmin && (
        <p className="muted small">Simbol divalidasi ke penyedia harga (Yahoo Finance). Saham IDX berakhiran .JK. Maksimal 10 penambahan per hari.</p>
      )}
      <p className="muted small">Metrik portofolio masih satu mata uang; hindari mencampur saham IDR dan USD.</p>
      <label>Simbol <input value={symbol} onChange={(e) => onSymbol(e.target.value)} placeholder="BBCA.JK atau AAPL" required maxLength={20} /></label>
      <label>Nama <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={160} /></label>
      <div className="row">
        <label>Bursa <input value={exchange} onChange={(e) => setExchange(e.target.value)} required maxLength={20} /></label>
        <label>Mata uang <input value={currency} onChange={(e) => setCurrency(e.target.value)} required minLength={3} maxLength={3} /></label>
      </div>
      <label>Sektor (opsional) <input value={sector} onChange={(e) => setSector(e.target.value)} maxLength={80} /></label>
      {isAdmin && (
        <label>Jenis
          <select value={kind} onChange={(e) => setKind(e.target.value as "STOCK" | "INDEX")}>
            <option value="STOCK">Saham / ETF (bisa diperdagangkan)</option>
            <option value="INDEX">Indeks pembanding (tidak bisa dibeli)</option>
          </select>
        </label>
      )}
      <Notice state={msg} />
      <button className="btn" disabled={busy}>{busy ? "Menyimpan…" : "Tambah"}</button>
    </form>
  );
}

export default function Stocks() {
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [market, setMarket] = useState<"all" | "idx" | "global">("all");
  const [selected, setSelected] = useState<Stock | null>(null);
  const stocks = useLoad(() => api.listStocks(q), [q]);

  const shown = (stocks.data ?? []).filter((s) =>
    market === "all" ? true : market === "idx" ? s.exchange === "IDX" : s.exchange !== "IDX",
  );

  return (
    <div className="grid sidebar">
      <div>
        <section className="card">
          <form className="searchrow" onSubmit={(e) => { e.preventDefault(); setQ(search.trim()); }}>
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari simbol / nama" />
            <button className="btn ghost">Cari</button>
          </form>
          <div style={{ marginTop: 10 }}>
            <Segmented
              value={market} onChange={setMarket}
              options={[{ value: "all", label: "Semua" }, { value: "idx", label: "IDX" }, { value: "global", label: "Global" }]}
            />
          </div>
          {stocks.error && <div className="notice error">{stocks.error}</div>}
          <ul className="list">
            {shown.map((s) => (
              <li key={s.id}>
                <button className={selected?.id === s.id ? "on" : ""} onClick={() => setSelected(s)}>
                  <span className="liststock"><b>{s.symbol}</b><span className="badge neutral">{s.sector ?? s.exchange}</span></span>
                  <span className="muted">{s.name}</span>
                </button>
              </li>
            ))}
            {stocks.data && shown.length === 0 && <li className="muted" style={{ padding: 10 }}>Tidak ada saham.</li>}
          </ul>
        </section>
        <section className="card">
          <AddStockForm isAdmin={!!user?.is_admin} onCreated={(s) => { stocks.reload(); setSelected(s); }} />
        </section>
      </div>
      <div>
        {selected ? <StockDetail key={selected.id} stock={selected} /> : (
          <section className="card"><p className="muted">Pilih saham di sebelah kiri untuk melihat grafik candlestick dan harga terbaru.</p></section>
        )}
      </div>
    </div>
  );
}
