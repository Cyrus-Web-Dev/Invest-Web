import { useRef, useState } from "react";
import { api, downloadFile } from "../api";
import { useAuth } from "../auth";
import Notice, { type NoticeState } from "../components/Notice";
import { fmt, tone } from "../format";
import { errMsg } from "../hooks";
import type { ImportReport } from "../types";

const KIND_LABEL: Record<string, string> = {
  BUY: "Beli", SELL: "Jual", DEPOSIT: "Setor", WITHDRAW: "Tarik", DIVIDEND: "Dividen",
};
const today = () => new Date().toISOString().slice(0, 10);

export default function DataPage() {
  const { refreshUser } = useAuth();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<NoticeState | null>(null);

  async function run(dryRun: boolean, force = false) {
    if (!file) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.importFile(file, dryRun, force);
      setReport(r);
      if (r.committed) {
        await refreshUser();
        setMsg({ kind: "ok", text: `${r.total_rows} baris berhasil diimpor. Buka Dashboard untuk melihat hasilnya.` });
        setFile(null);
        if (fileRef.current) fileRef.current.value = "";
      }
    } catch (e) {
      setReport(null);
      setMsg({ kind: "error", text: errMsg(e) });
    } finally {
      setBusy(false);
    }
  }

  async function download(path: string, name: string) {
    setMsg(null);
    try {
      await downloadFile(path, name);
    } catch (e) {
      setMsg({ kind: "error", text: errMsg(e) });
    }
  }

  return (
    <>
      <Notice state={msg} />
      <div className="grid two">
        <section className="card">
          <h2>Impor transaksi dari CSV</h2>
          <p className="muted small">
            Satu file bisa berisi pembelian, penjualan, setoran, penarikan, dan dividen dengan tanggal lampau.
            Semua baris diperiksa dulu; jika ada satu saja yang bermasalah, tidak ada yang diimpor.
          </p>
          <ul className="muted small" style={{ paddingLeft: 18 }}>
            <li>Kolom: <code>tanggal, jenis, simbol, jumlah, harga, fee, nominal, catatan</code></li>
            <li>Jenis: BELI, JUAL, SETOR, TARIK, DIVIDEN. Jumlah dalam lembar (1 lot = 100 lembar).</li>
            <li>Angka tanpa pemisah ribuan. Desimal pakai titik atau koma. Pemisah kolom , atau ;</li>
            <li>Simbol harus ada di katalog saham. Saldo kas tidak boleh negatif pada tanggal mana pun.</li>
          </ul>
          <div className="btnrow" style={{ margin: "10px 0" }}>
            <button className="btn ghost" onClick={() => download("/portfolio/import/template.csv", "templat-impor-stockfolio.csv")}>
              Unduh templat CSV
            </button>
          </div>
          <input
            ref={fileRef} type="file" accept=".csv,text/csv"
            onChange={(e) => { setFile(e.target.files?.[0] ?? null); setReport(null); setMsg(null); }}
          />
          <div className="btnrow" style={{ marginTop: 12 }}>
            <button className="btn ghost" disabled={!file || busy} onClick={() => run(true)}>
              {busy ? "Memeriksa…" : "1. Periksa file"}
            </button>
            <button className="btn" disabled={!file || busy || !report?.ok || report.committed} onClick={() => run(false)}>
              2. Impor sekarang
            </button>
            {report?.duplicate && !report.ok && (
              <button className="btn ghost" disabled={busy} onClick={() => run(false, true)}>
                Impor ulang tetap
              </button>
            )}
          </div>

          {report && (
            <div style={{ marginTop: 16 }}>
              {report.ok && !report.committed && (
                <div className="notice ok">File valid dan siap diimpor. Periksa ringkasan di bawah, lalu klik “Impor sekarang”.</div>
              )}
              {!report.ok && (
                <div className="notice error">
                  {report.duplicate ? "File ini sudah pernah diimpor." : "File tidak bisa diimpor. Perbaiki baris berikut lalu periksa ulang."}
                </div>
              )}
              {report.total_rows > 0 && (
                <ul className="insights">
                  <li className="info"><span>
                    {report.total_rows} baris valid · {Object.entries(report.counts).map(([k, v]) => `${KIND_LABEL[k] ?? k} ${v}`).join(" · ")}
                    {report.date_from && ` · ${report.date_from} s/d ${report.date_to}`}
                  </span></li>
                  {report.resulting_cash !== null && (
                    <li className="info"><span>
                      Efek ke kas: <b className={tone(report.cash_effect)}>{fmt(report.cash_effect)}</b> → saldo menjadi <b>{fmt(report.resulting_cash)}</b>
                    </span></li>
                  )}
                </ul>
              )}
              {report.errors.length > 0 && (
                <div className="tablewrap" style={{ marginTop: 10 }}>
                  <table>
                    <thead><tr><th>Baris</th><th>Masalah</th></tr></thead>
                    <tbody>
                      {report.errors.map((e, i) => (
                        <tr key={i}><td>{e.line ?? "—"}</td><td style={{ whiteSpace: "normal" }}>{e.message}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  {report.more_errors > 0 && <p className="muted small">…dan {report.more_errors} masalah lainnya.</p>}
                </div>
              )}
            </div>
          )}
        </section>

        <section className="card">
          <h2>Ekspor data</h2>
          <p className="muted small">
            Unduh data Anda untuk arsip, pelaporan pajak, atau analisis di Excel.
            Format CSV transaksi sama dengan format impor. Jangan mengimpor ulang hasil ekspor ke akun yang sama.
          </p>
          <div className="form">
            <button className="btn" onClick={() => download("/export/report.xlsx", `stockfolio-laporan-${today()}.xlsx`)}>
              Laporan Excel (.xlsx) — ringkasan, posisi, transaksi
            </button>
            <button className="btn ghost" onClick={() => download("/export/transactions.csv", `stockfolio-transaksi-${today()}.csv`)}>
              Transaksi (CSV, pemisah koma)
            </button>
            <button className="btn ghost" onClick={() => download("/export/transactions.csv?sep=%3B", `stockfolio-transaksi-${today()}.csv`)}>
              Transaksi (CSV, pemisah titik koma — untuk Excel Indonesia)
            </button>
            <button className="btn ghost" onClick={() => download("/export/holdings.csv", `stockfolio-posisi-${today()}.csv`)}>
              Posisi saat ini (CSV)
            </button>
          </div>
        </section>
      </div>
    </>
  );
}
