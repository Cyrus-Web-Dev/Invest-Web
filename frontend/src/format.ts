const cache = new Map<string, Intl.NumberFormat>();
function nf(min: number, max: number): Intl.NumberFormat {
  const key = `${min}-${max}`;
  let f = cache.get(key);
  if (!f) {
    f = new Intl.NumberFormat("id-ID", { minimumFractionDigits: min, maximumFractionDigits: max });
    cache.set(key, f);
  }
  return f;
}

export function fmt(v: string | number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  return Number.isFinite(n) ? nf(digits, digits).format(n) : "—";
}

export function fmtQty(v: string | number): string {
  const n = Number(v);
  return Number.isFinite(n) ? nf(0, 4).format(n) : "—";
}

export const fmtPct = (v: string | null | undefined) => (v === null || v === undefined ? "—" : `${fmt(v, 2)}%`);

export function tone(v: string | number | null | undefined): string {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return "";
  return n > 0 ? "pos" : "neg";
}

export const fmtDateTime = (iso: string) => new Date(iso).toLocaleString("id-ID");

/** Terima "10.5" atau "10,5"; kembalikan string dengan titik desimal, atau null jika tidak valid. */
export function normDecimal(s: string): string | null {
  const t = s.trim();
  if (/^\d+(\.\d+)?$/.test(t)) return t;
  if (/^\d+,\d+$/.test(t)) return t.replace(",", ".");
  return null;
}

/** Tanggal hari ini menurut UTC (sama dengan acuan validasi di server). */
export const todayUtc = () => new Date().toISOString().slice(0, 10);

/** "Value, jangka panjang" -> ["value", "jangka-panjang"] (server memvalidasi ulang; maks. 5 tag). */
export function parseTags(s: string): string[] {
  const out: string[] = [];
  for (const raw of s.split(",")) {
    const t = raw.trim().toLowerCase().replace(/[\s_]+/g, "-");
    if (t && !out.includes(t)) out.push(t);
  }
  return out.slice(0, 5);
}
