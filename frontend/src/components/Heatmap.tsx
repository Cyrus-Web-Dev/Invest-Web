import type { CSSProperties } from "react";
import { tone } from "../format";
import type { MonthlyRow } from "../types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

/** Warna sel: hijau untuk positif, merah untuk negatif; makin pekat makin besar (jenuh di ±8%). */
function cellStyle(v: number | null): CSSProperties {
  if (v === null) return {};
  const a = Math.min(1, Math.abs(v) / 8) * 0.75 + 0.12;
  const rgb = v >= 0 ? "16,185,129" : "239,68,68";
  return { backgroundColor: `rgba(${rgb},${a.toFixed(2)})`, color: a > 0.6 ? "#fff" : undefined };
}

export default function Heatmap({ rows }: { rows: MonthlyRow[] }) {
  return (
    <div className="tablewrap">
      <table className="heat">
        <thead>
          <tr><th>Tahun</th>{MONTHS.map((m) => <th key={m} className="c">{m}</th>)}<th className="c">Setahun</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.year}>
              <td><b>{r.year}</b></td>
              {r.months.map((v, i) => (
                <td key={i} className="c heatcell" style={cellStyle(v)} title={v === null ? "" : `${v.toFixed(2)}%`}>
                  {v === null ? "" : v.toFixed(1)}
                </td>
              ))}
              <td className={`c ${tone(r.total)}`}><b>{r.total === null ? "—" : `${r.total.toFixed(1)}%`}</b></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
