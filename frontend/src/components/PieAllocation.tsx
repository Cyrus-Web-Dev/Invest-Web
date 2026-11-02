import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import { fmt } from "../format";
import { useChartAnimations } from "../chartAnim";
import { chartPalette, useTheme } from "../theme";
import type { AllocationRow } from "../types";

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#06b6d4", "#8b5cf6", "#ec4899", "#84cc16", "#f97316", "#14b8a6", "#64748b"];

export default function PieAllocation({ rows }: { rows: AllocationRow[] }) {
  const { theme } = useTheme();
  const anim = useChartAnimations();
  if (rows.length === 0) return <p className="muted">Belum ada aset untuk ditampilkan.</p>;
  const pal = chartPalette(theme);
  const values = rows.map((r) => Number(r.value));
  const total = values.reduce((a, b) => a + b, 0);
  const options: ApexOptions = {
    chart: { background: "transparent", foreColor: pal.text, animations: anim },
    theme: { mode: theme },
    colors: COLORS,
    labels: rows.map((r) => r.label),
    stroke: { colors: [pal.bg], width: 2 },
    legend: { position: "bottom", labels: { colors: pal.text } },
    dataLabels: { formatter: (val: string | number | number[]) => `${Number(val).toFixed(1)}%` },
    tooltip: { y: { formatter: (v: number) => fmt(v) } },
    plotOptions: {
      pie: {
        donut: { size: "62%", labels: { show: true, total: { show: true, label: "Total", formatter: () => fmt(total, 0) } } },
      },
    },
  };
  return <Chart key={theme} type="donut" height={340} series={values} options={options} />;
}
