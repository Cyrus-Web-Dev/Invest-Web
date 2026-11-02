import { useState, type FormEvent } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import Notice, { type NoticeState } from "../components/Notice";
import TagInput from "../components/TagInput";
import { fmt, fmtDateTime, fmtQty, normDecimal, parseTags, todayUtc } from "../format";
import { errMsg, useLoad } from "../hooks";
import type { Stock } from "../types";

const BAD_NUMBER = "Isi angka yang valid (pakai titik atau koma untuk desimal, tanpa pemisah ribuan).";

function StockSelect({ stocks, value, onChange }: { stocks: Stock[]; value: string; onChange: (v: string) => void }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} required>
      <option value="">— pilih saham —</option>
      {stocks.map((s) => <option key={s.id} value={s.id}>{s.symbol} · {s.name}</option>)}
    </select>
  );
}

function CashForm() {
  const { refreshUser } = useAuth();
  const [type, setType] = useState<"DEPOSIT" | "WITHDRAW">("DEPOSIT");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<NoticeState | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const a = normDecimal(amount);
    if (!a) return setMsg({ kind: "error", text: BAD_NUMBER });
    setBusy(true);
    setMsg(null);
    try {
      await api.cash(type, a, date || undefined);
      await refreshUser();
      setAmount("");
      setMsg({ kind: "ok", text: type === "DEPOSIT" ? "Setoran dicatat." : "Penarikan dicatat." });
    } catch (err) {
      setMsg({ kind: "error", text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="form">
      <h3>Setor / tarik modal</h3>
      <div className="row">
        <label>Jenis
          <select value={type} onChange={(e) => setType(e.target.value as "DEPOSIT" | "WITHDRAW")}>
            <option value="DEPOSIT">Setor</option>
            <option value="WITHDRAW">Tarik</option>
          </select>
        </label>
        <label>Jumlah <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} required /></label>
      </div>
      <label>Tanggal (opsional, kosong = sekarang)
        <input type="date" value={date} max={todayUtc()} onChange={(e) => setDate(e.target.value)} />
      </label>
      <Notice state={msg} />
      <button className="btn" disabled={busy}>Simpan</button>
    </form>
  );
}

function TradeForm({ stocks, onDone }: { stocks: Stock[]; onDone: () => void }) {
  const { refreshUser } = useAuth();
  const [stockId, setStockId] = useState("");
  const [type, setType] = useState<"BUY" | "SELL">("BUY");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");
  const [fee, setFee] = useState("0");
  const [note, setNote] = useState("");
  const [tags, setTags] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<NoticeState | null>(null);

  async function fillPrice() {
    if (!stockId) return setMsg({ kind: "error", text: "Pilih saham terlebih dahulu." });
    setMsg(null);
    try {
      const q = await api.quote(Number(stockId));
      setPrice(q.price);
    } catch (err) {
      setMsg({ kind: "error", text: errMsg(err) });
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const q = normDecimal(qty), p = normDecimal(price), f = normDecimal(fee);
    if (!stockId || !q || !p || f === null) return setMsg({ kind: "error", text: BAD_NUMBER });
    setBusy(true);
    setMsg(null);
    try {
      await api.trade({ stock_id: Number(stockId), type, quantity: q, price: p, fee: f, note: note.trim() || null, date: date || null, tags: parseTags(tags) });
      await refreshUser();
      setQty(""); setNote(""); setTags("");
      setMsg({ kind: "ok", text: type === "BUY" ? "Pembelian dicatat." : "Penjualan dicatat." });
      onDone();
    } catch (err) {
      setMsg({ kind: "error", text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="form">
      <h3>Catat transaksi</h3>
      <label>Saham <StockSelect stocks={stocks} value={stockId} onChange={setStockId} /></label>
      <div className="row">
        <label>Jenis
          <select value={type} onChange={(e) => setType(e.target.value as "BUY" | "SELL")}>
            <option value="BUY">Beli</option>
            <option value="SELL">Jual</option>
          </select>
        </label>
        <label>Jumlah lembar <input inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} required /></label>
      </div>
      <div className="row">
        <label>Harga per lembar <input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} required /></label>
        <label>Fee <input inputMode="decimal" value={fee} onChange={(e) => setFee(e.target.value)} required /></label>
      </div>
      <button type="button" className="btn ghost" onClick={fillPrice}>Isi dengan harga terbaru</button>
      <label>Tanggal (opsional, kosong = sekarang)
        <input type="date" value={date} max={todayUtc()} onChange={(e) => setDate(e.target.value)} />
      </label>
      <label>Alasan / tesis (opsional) <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={255} placeholder="mis. valuasi murah, laporan kuartal solid" /></label>
      <TagInput value={tags} onChange={setTags} />
      <Notice state={msg} />
      <button className="btn" disabled={busy}>{busy ? "Menyimpan…" : "Simpan transaksi"}</button>
    </form>
  );
}

function DividendForm({ stocks, onDone }: { stocks: Stock[]; onDone: () => void }) {
  const { refreshUser } = useAuth();
  const [stockId, setStockId] = useState("");
  const [amount, setAmount] = useState("");
  const [paidOn, setPaidOn] = useState(todayUtc());
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<NoticeState | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const a = normDecimal(amount);
    if (!stockId || !a) return setMsg({ kind: "error", text: BAD_NUMBER });
    setBusy(true);
    setMsg(null);
    try {
      await api.addDividend({ stock_id: Number(stockId), amount: a, paid_on: paidOn });
      await refreshUser();
      setAmount("");
      setMsg({ kind: "ok", text: "Dividen dicatat dan ditambahkan ke kas." });
      onDone();
    } catch (err) {
      setMsg({ kind: "error", text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="form">
      <h3>Catat dividen</h3>
      <label>Saham <StockSelect stocks={stocks} value={stockId} onChange={setStockId} /></label>
      <div className="row">
        <label>Jumlah bersih (setelah pajak) <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} required /></label>
        <label>Tanggal diterima <input type="date" value={paidOn} max={todayUtc()} onChange={(e) => setPaidOn(e.target.value)} required /></label>
      </div>
      <Notice state={msg} />
      <button className="btn" disabled={busy}>Simpan dividen</button>
    </form>
  );
}

export default function Portfolio() {
  const stocks = useLoad(() => api.listStocks(), []);
  const txs = useLoad(() => api.transactions(), []);
  const divs = useLoad(() => api.dividends(), []);
  const list = stocks.data ?? [];
  const symbol = (id: number) => list.find((s) => s.id === id)?.symbol ?? `#${id}`;

  return (
    <>
      {list.length === 0 && stocks.data && (
        <div className="notice warn">Belum ada saham. Tambahkan dahulu di halaman Saham.</div>
      )}
      <div className="grid three">
        <section className="card"><CashForm /></section>
        <section className="card"><TradeForm stocks={list} onDone={txs.reload} /></section>
        <section className="card"><DividendForm stocks={list} onDone={divs.reload} /></section>
      </div>

      <section className="card">
        <h2>Riwayat transaksi</h2>
        {txs.error && <div className="notice error">{txs.error}</div>}
        {txs.data && txs.data.length === 0 && <p className="muted">Belum ada transaksi.</p>}
        {txs.data && txs.data.length > 0 && (
          <div className="tablewrap">
            <table>
              <thead>
                <tr><th>Waktu</th><th>Saham</th><th>Jenis</th><th className="r">Lembar</th><th className="r">Harga</th><th className="r">Fee</th><th className="r">Total</th><th>Catatan</th></tr>
              </thead>
              <tbody>
                {txs.data.map((t) => {
                  const gross = Number(t.quantity) * Number(t.price);
                  const total = t.type === "BUY" ? gross + Number(t.fee) : gross - Number(t.fee);
                  return (
                    <tr key={t.id}>
                      <td>{fmtDateTime(t.executed_at)}</td>
                      <td><b>{symbol(t.stock_id)}</b></td>
                      <td><span className={`badge ${t.type === "BUY" ? "buy" : "sell"}`}>{t.type === "BUY" ? "Beli" : "Jual"}</span></td>
                      <td className="r">{fmtQty(t.quantity)}</td>
                      <td className="r">{fmt(t.price)}</td>
                      <td className="r">{fmt(t.fee)}</td>
                      <td className="r">{fmt(total)}</td>
                      <td>{t.note ?? ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Riwayat dividen</h2>
        {divs.data && divs.data.length === 0 && <p className="muted">Belum ada dividen.</p>}
        {divs.data && divs.data.length > 0 && (
          <div className="tablewrap">
            <table>
              <thead><tr><th>Tanggal</th><th>Saham</th><th className="r">Jumlah</th></tr></thead>
              <tbody>
                {divs.data.map((d) => (
                  <tr key={d.id}><td>{d.paid_on}</td><td><b>{symbol(d.stock_id)}</b></td><td className="r">{fmt(d.amount)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
