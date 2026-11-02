import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { PageSkeleton } from "../components/ChartSkeleton";
import { fmt, fmtPct, fmtQty, tone } from "../format";
import { useLoad } from "../hooks";

export default function Journal() {
  const data = useLoad(() => api.journal(), []);
  const [tag, setTag] = useState("");
  const [heldOnly, setHeldOnly] = useState(false);

  if (data.error) return <div className="notice error">{data.error}</div>;
  if (!data.data) return <PageSkeleton />;
  const { items, tags } = data.data;
  const shown = items.filter((i) => (!tag || (tag === "(tanpa tag)" ? i.tags.length === 0 : i.tags.includes(tag))) && (!heldOnly || i.still_held));

  return (
    <>
      <section className="card">
        <h2>Ringkasan per tag</h2>
        <p className="muted small">
          Menilai <b>keputusan beli</b>: seberapa baik tiap pembelian dibanding harga terakhir. Return = harga terakhir ÷ harga beli − 1
          (belum memperhitungkan penjualan sebagian dan dividen). Return per tag dibobot dengan modal pembelian.
          Satu pembelian dengan beberapa tag dihitung di setiap tag-nya.
        </p>
        {tags.length === 0 ? (
          <p className="muted">Belum ada pembelian. Catat transaksi beli lengkap dengan alasan dan tag di halaman <Link to="/portfolio">Transaksi</Link>.</p>
        ) : (
          <div className="tablewrap">
            <table>
              <thead>
                <tr><th>Tag</th><th className="r">Jumlah beli</th><th className="r">Modal</th><th className="r">Return terbobot</th><th className="r">Rasio untung</th><th /></tr>
              </thead>
              <tbody>
                {tags.map((t) => (
                  <tr key={t.tag}>
                    <td><span className="tagchip">{t.tag}</span></td>
                    <td className="r">{t.count}</td>
                    <td className="r">{fmt(t.total_cost)}</td>
                    <td className={`r ${tone(t.weighted_return_pct)}`}>{fmtPct(t.weighted_return_pct)}</td>
                    <td className="r">{fmtPct(t.win_rate_pct)}</td>
                    <td className="r"><button className="btn ghost small" onClick={() => setTag(tag === t.tag ? "" : t.tag)}>{tag === t.tag ? "Tampilkan semua" : "Filter"}</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <div className="cardhead">
          <h2>Jurnal pembelian {tag && <span className="tagchip on">{tag}</span>}</h2>
          <label style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={heldOnly} onChange={(e) => setHeldOnly(e.target.checked)} style={{ width: "auto" }} />
            Hanya yang masih dimiliki
          </label>
        </div>
        {shown.length === 0 && <p className="muted">Tidak ada pembelian untuk filter ini.</p>}
        {shown.length > 0 && (
          <div className="tablewrap">
            <table>
              <thead>
                <tr><th>Tanggal</th><th>Saham</th><th className="r">Lembar</th><th className="r">Harga beli</th><th className="r">Harga kini</th><th className="r">Return</th><th className="r">Untung/Rugi</th><th>Alasan & tag</th></tr>
              </thead>
              <tbody>
                {shown.map((i) => (
                  <tr key={i.id}>
                    <td>{i.day}</td>
                    <td><b>{i.symbol}</b>{!i.still_held && <span className="badge neutral" style={{ marginLeft: 6 }}>sudah dijual</span>}</td>
                    <td className="r">{fmtQty(i.quantity)}</td>
                    <td className="r">{fmt(i.price)}</td>
                    <td className="r">{i.current_price ? fmt(i.current_price) : "—"}</td>
                    <td className={`r ${tone(i.return_pct)}`}>{fmtPct(i.return_pct)}</td>
                    <td className={`r ${tone(i.pnl)}`}>{i.pnl ? fmt(i.pnl) : "—"}</td>
                    <td style={{ whiteSpace: "normal", minWidth: 220 }}>
                      {i.note ?? <span className="muted">—</span>}
                      {i.tags.length > 0 && <div className="tagrow">{i.tags.map((t) => <span key={t} className="tagchip">{t}</span>)}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted small" style={{ marginTop: 10 }}>
          Tinjau berkala: apakah alasan beli masih berlaku? Pembelian dengan return negatif dan tesis yang sudah berubah adalah kandidat evaluasi.
        </p>
      </section>
    </>
  );
}
