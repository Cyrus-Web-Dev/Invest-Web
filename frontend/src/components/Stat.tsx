import CountUp from "./CountUp";
import Icon, { type IconName } from "./icons";

export default function Stat({
  label, value, sub, tone, icon, count,
}: { label: string; value: string; sub?: string; tone?: string; icon?: IconName; count?: number }) {
  return (
    <div className="card stat">
      <div className="stat-top">
        <span className="label">{label}</span>
        {icon && <span className="stat-icon"><Icon name={icon} size={16} /></span>}
      </div>
      <div className={`value ${tone ?? ""}`}>
        {count !== undefined && Number.isFinite(count) ? <CountUp value={count} /> : value}
      </div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}
