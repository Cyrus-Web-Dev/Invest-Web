import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import { fmt } from "../format";
import { useChartAnimations } from "../chartAnim";
import { chartPalette, useTheme } from "../theme";
import type { PerformancePoint } from "../types";

export default function PerformanceChart({ points }: { points: PerformancePoint[] }) {
  const { theme } = useTheme();
  const anim = useChartAnimations();
  if (points.length === 0) {
    return <p className="muted">Belum ada data. Setor kas dan lakukan transaksi terlebih dahulu.</p>;
  }
  const pal = chartPalette(theme);
  const ts = (d: string) => new Date(d).getTime();
  const series = [
    { name: "Net Worth", data: points.map((p) => [ts(p.date), p.net_worth] as [number, number]) },
    { name: "Modal disetor", data: points.map((p) => [ts(p.date), p.invested_capital] as [number, number]) },
  ];
  const options: ApexOptions = {
    chart: { background: "transparent", foreColor: pal.text, toolbar: { show: false }, zoom: { enabled: false }, animations: anim },
    theme: { mode: theme },
    colors: [theme === "dark" ? "#818cf8" : "#4f46e5", "#94a3b8"],
    stroke: { width: [3, 2], dashArray: [0, 6], curve: "straight" },
    dataLabels: { enabled: false },
    grid: { borderColor: pal.grid },
    legend: { position: "top", labels: { colors: pal.text } },
    xaxis: { type: "datetime", axisBorder: { show: false } },
    yaxis: { labels: { formatter: (v: number) => fmt(v, 0) } },
    tooltip: { x: { format: "dd MMM yyyy" }, y: { formatter: (v: number) => fmt(v) } },
  };
  return <Chart key={theme} type="line" height={340} series={series} options={options} />;
}
