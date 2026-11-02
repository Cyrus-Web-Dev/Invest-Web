import { useState, type FormEvent } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import Notice, { type NoticeState } from "../components/Notice";
import TagInput from "../components/TagInput";
import { fmt, fmtQty, normDecimal, parseTags, todayUtc } from "../format";
import { errMsg, useLoad } from "../hooks";
import type { LedgerItem, Stock } from "../types";

const TYPE_LABEL: Record<string, string> = { BUY: "Beli", SELL: "Jual", DEPOSIT: "Setor", WITHDRAW: "Tarik", DIVIDEND: "Dividen" };
const BAD_NUMBER = "Isi angka yang valid (desimal pakai titik atau koma, tanpa pemisah ribuan).";

function EditForm({
  item, stocks, onClose, onSaved,
}: { item: LedgerItem; stocks: Stock[]; onClose: () => void; onSaved: () => void }) {
  const { refreshUser } = useAuth();
  const [stockId, setStockId] = useState(item.stock_id ? String(item.stock_id) : "");
  const [type, setType] = useState<string>(item.type);
  const [qty, setQty] = useState(item.quantity ?? "");
  const [price, setPrice] = useState(item.price ?? "");
  const [fee, setFee] = useState(item.fee ?? "0");
  const [amount, setAmount] = useState(item.amount ?? "");
  const [date, setDate] = useState(item.day);
  const [note, setNote] = useState(item.note ?? "");
  const [tags, setTags] = useState((item.tags ?? []).join(", "));
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<NoticeState | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const dateChanged = date !== item.day;
    let body: Record<string, unknown>;
    if (item.kind === "TRADE") {
      const q = normDecimal(qty), p = normDecimal(price), f = normDecimal(fee);
      if (!stockId || !q || !p || f === null) return setMsg({ kind: "error", text: BAD_NUMBER });
      body = { stock_id: Number(stockId), type, quantity: q, price: p, fee: f, note: note.trim() || null, tags: parseTags(tags) };
      if (dateChanged) body.date = date;
    } else if (item.kind === "CASH") {
      const a = normDecimal(amount);
      if (!a) return setMsg({ kind: "error", text: BAD_NUMBER });
      body = { type, amount: a };
      if (dateChanged) body.date = date;
    } else {
      const a = normDecimal(amount);
      if (!stockId || !a) return setMsg({ kind: "error", text: BAD_NUMBER });
      body = { stock_id: Number(stockId), amount: a };
      if (dateChanged) body.paid_on = date;
    }
    setBusy(true);
    setMsg(null);
    try {
      await api.updateLedger(item.kind, item.id, body);
      await refreshUser();
      onSaved();
    } catch (err) {
      setMsg({ kind: "error", text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  const stockSelect = (
    <label>Saham
      <select value={stockId} onChange={(e) => setStockId(e.target.value)} required>
        <option value="">— pilih saham —</option>
        {stocks.map((s) => <option key={s.id} value={s.id}>{s.symbol} · {s.name}</option>)}
      </select>
    </label>
  );

  return (
    <section className="card">
      <form className="form" onSubmit={submit}>
        <div className="cardhead">
          <h2>Ubah catatan: {TYPE_LABEL[item.type]}{item.symbol ? ` ${item.symbol}` : ""} · {item.day}</h2>
          <button type="button" className="btn ghost small" onClick={onClose}>Batal</button>
        </div>
        <p className="muted small">
          Setelah diubah, seluruh riwayat dihitung ulang berurutan tanggal. Perubahan ditolak jika membuat saldo kas
          negatif atau penjualan melebihi kepemilikan di tanggal mana pun.
        </p>
        {item.kind === "TRADE" && (
          <>
            {stockSelect}
            <div className="row">
              <label>Jenis
                <select value={type} onChange={(e) => setType(e.target.value)}>
                  <option value="BUY">Beli</option><option value="SELL">Jual</option>
                </select>
              </label>
              <label>Jumlah lembar <input inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} required /></label>
            </div>
            <div className="row">
              <label>Harga per lembar <input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} required /></label>
              <label>Fee <input inputMode="decimal" value={fee} onChange={(e) => setFee(e.target.value)} required /></label>
            </div>
          </>
        )}
        {item.kind === "CASH" && (
          <div className="row">
            <label>Jenis
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option value="DEPOSIT">Setor</option><option value="WITHDRAW">Tarik</option>
              </select>
            </label>
            <label>Nominal <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} required /></label>
          </div>
        )}
        {item.kind === "DIVIDEND" && (
          <>
            {stockSelect}
            <label>Nominal bersih <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} required /></label>
          </>
        )}
        <label>Tanggal
          <input type="date" value={date} max={todayUtc()} onChange={(e) => setDate(e.target.value)} required />
        </label>
        {item.kind === "TRADE" && (
          <>
            <label>Alasan / tesis <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={255} /></label>
            <TagInput value={tags} onChange={setTags} />
          </>
        )}
        <Notice state={msg} />
        <button className="btn" disabled={busy}>{busy ? "Menyimpan…" : "Simpan perubahan"}</button>
      </form>
    </section>
  );
}

export default function Ledger() {
  const { refreshUser } = useAuth();
  const [type, setType] = useState("");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(100);
  const [tag, setTag] = useState("");
  const [editing, setEditing] = useState<LedgerItem | null>(null);
  const [msg, setMsg] = useState<NoticeState | null>(null);
  const ledger = useLoad(() => api.ledger({ limit, type, q, tag }), [limit, type, q, tag]);
  const stocks = useLoad(() => api.listStocks(), []);

  async function remove(item: LedgerItem) {
    const label = `${TYPE_LABEL[item.type]}${item.symbol ? ` ${item.symbol}` : ""} tanggal ${item.day}`;
    if (!window.confirm(`Hapus catatan ini?\n\n${label}\n\nSaldo kas dan posisi akan dihitung ulang. Tindakan ini tidak bisa dibatalkan.`)) return;
    setMsg(null);
    try {
      await api.deleteLedger(item.kind, item.id);
      await refreshUser();
      setMsg({ kind: "ok", text: "Catatan dihapus dan riwayat dihitung ulang." });
      ledger.reload();
    } catch (e) {
      setMsg({ kind: "error", text: errMsg(e) });
    }
  }

  const rows = ledger.data?.items ?? [];
  const total = ledger.data?.total ?? 0;
  const tagOptions = Array.from(new Set([...(tag ? [tag] : []), ...rows.flatMap((r) => r.tags ?? [])])).sort();

  return (
    <>
      <Notice state={msg} />
      {editing && (
        <EditForm
          key={`${editing.kind}-${editing.id}`}
          item={editing}
          stocks={stocks.data ?? []}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); setMsg({ kind: "ok", text: "Perubahan disimpan dan riwayat dihitung ulang." }); ledger.reload(); }}
        />
      )}
      <section className="card">
        <div className="cardhead">
          <h2>Riwayat buku besar <span className="muted">({total})</span></h2>
          <div className="btnrow">
            <select value={type} onChange={(e) => { setType(e.target.value); setLimit(100); }} style={{ width: "auto" }}>
              <option value="">Semua jenis</option>
              {Object.entries(TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select value={tag} onChange={(e) => { setTag(e.target.value); setLimit(100); }} style={{ width: "auto" }}>
              <option value="">Semua tag</option>
              {tagOptions.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <form className="searchrow" onSubmit={(e) => { e.preventDefault(); setQ(qInput.trim()); setLimit(100); }}>
              <input value={qInput} onChange={(e) => setQInput(e.target.value)} placeholder="Cari simbol" style={{ width: 150 }} />
              <button className="btn ghost small">Cari</button>
            </form>
          </div>
        </div>
        {ledger.error && <div className="notice error">{ledger.error}</div>}
        {ledger.data && rows.length === 0 && <p className="muted">Tidak ada catatan.</p>}
        {rows.length > 0 && (
          <div className="tablewrap">
            <table>
              <thead>
                <tr>
                  <th>Tanggal</th><th>Jenis</th><th>Saham</th><th className="r">Lembar</th><th className="r">Harga</th>
                  <th className="r">Fee</th><th className="r">Total</th><th>Catatan</th><th />
                </tr>
              </thead>
              <tbody>
                {rows.map((i) => {
                  const gross = Number(i.quantity ?? 0) * Number(i.price ?? 0);
                  const total = i.kind === "TRADE" ? (i.type === "BUY" ? gross + Number(i.fee ?? 0) : gross - Number(i.fee ?? 0)) : Number(i.amount ?? 0);
                  const outflow = i.type === "BUY" || i.type === "WITHDRAW";
                  return (
                    <tr key={`${i.kind}-${i.id}`}>
                      <td>{i.day}</td>
                      <td><span className={`badge ${i.type === "BUY" || i.type === "DEPOSIT" ? "buy" : i.type === "SELL" || i.type === "WITHDRAW" ? "sell" : "neutral"}`}>{TYPE_LABEL[i.type]}</span></td>
                      <td>{i.symbol ? <b>{i.symbol}</b> : "—"}</td>
                      <td className="r">{i.quantity ? fmtQty(i.quantity) : "—"}</td>
                      <td className="r">{i.price ? fmt(i.price) : "—"}</td>
                      <td className="r">{i.fee ? fmt(i.fee) : "—"}</td>
                      <td className={`r ${outflow ? "neg" : "pos"}`}>{outflow ? "−" : "+"}{fmt(total)}</td>
                      <td style={{ whiteSpace: "normal" }}>{i.note ?? ""}{(i.tags ?? []).length > 0 && <div className="tagrow">{i.tags.map((t) => <span key={t} className="tagchip">{t}</span>)}</div>}</td>
                      <td className="r">
                        <button className="btn ghost small" onClick={() => { setEditing(i); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Ubah</button>{" "}
                        <button className="btn ghost small" onClick={() => remove(i)}>Hapus</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {rows.length < total && (
          <div style={{ textAlign: "center", marginTop: 12 }}>
            <button className="btn ghost" onClick={() => setLimit((l) => l + 100)}>Muat lebih banyak</button>
          </div>
        )}
        <p className="muted small" style={{ marginTop: 10 }}>
          Total = nilai transaksi termasuk fee. Tanda − berarti uang keluar dari kas, + berarti masuk.
          Waktu transaksi yang tanggalnya diubah disimpan pada tengah hari UTC.
        </p>
      </section>
    </>
  );
}
