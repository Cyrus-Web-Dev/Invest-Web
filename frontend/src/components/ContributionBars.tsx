import { motion } from "framer-motion";
import { fmt, tone } from "../format";

/** Batang kontribusi dua arah dari garis tengah: kanan = untung, kiri = rugi. */
export default function ContributionBars({ rows }: { rows: { symbol: string; total: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.total)));
  return (
    <div className="contrib">
      {rows.map((r) => {
        const w = (Math.abs(r.total) / max) * 50;
        const pos = r.total >= 0;
        return (
          <div key={r.symbol} className="contribrow">
            <span className="contriblabel">{r.symbol}</span>
            <div className="contribtrack">
              <div className="contribmid" />
              <motion.div
                className={`contribbar ${pos ? "pos" : "neg"}`}
                style={pos ? { left: "50%" } : { right: "50%" }}
                initial={{ width: 0 }} animate={{ width: `${w}%` }} transition={{ duration: 0.7, ease: "easeOut" }}
              />
            </div>
            <span className={`contribval ${tone(r.total)}`}>{fmt(r.total, 0)}</span>
          </div>
        );
      })}
    </div>
  );
}
