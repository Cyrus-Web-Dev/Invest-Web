import Skeleton from "./Skeleton";

/** Placeholder bergaya grafik: batang-batang bergelombang saat data dimuat. */
export default function ChartSkeleton({ height = 300 }: { height?: number }) {
  const heights = [40, 62, 48, 75, 58, 82, 66, 90, 70, 55, 78, 64];
  return (
    <div className="chartskel" style={{ height }} aria-busy="true" aria-label="Memuat grafik">
      {heights.map((h, i) => (
        <div key={i} className="chartskel-bar" style={{ height: `${h}%`, animationDelay: `${i * 0.08}s` }} />
      ))}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <>
      <div className="grid stats">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="card"><Skeleton height={14} width={90} /><div style={{ height: 10 }} /><Skeleton height={26} /></div>
        ))}
      </div>
      <div className="card"><Skeleton height={18} width={200} /><div style={{ height: 12 }} /><ChartSkeleton /></div>
    </>
  );
}
