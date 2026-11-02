import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import { fmt } from "../format";
import { useChartAnimations } from "../chartAnim";
import { chartPalette, useTheme } from "../theme";
import type { BenchmarkPoint } from "../types";

export default function BenchmarkChart({ points, benchmarkName }: { points: BenchmarkPoint[]; benchmarkName: string }) {
  const { theme } = useTheme();
  const anim = useChartAnimations();
  if (points.length === 0) return null;
  const pal = chartPalette(theme);
  const ts = (d: string) => new Date(d).getTime();
  const series = [
    { name: "Portofolio Anda", data: points.map((p) => [ts(p.date), p.portfolio] as [number, number]) },
    { name: `${benchmarkName} (modal sama)`, data: points.map((p) => [ts(p.date), p.benchmark] as [number, number]) },
    { name: "Modal disetor", data: points.map((p) => [ts(p.date), p.invested] as [number, number]) },
  ];
  const options: ApexOptions = {
    chart: { background: "transparent", foreColor: pal.text, toolbar: { show: false }, zoom: { enabled: false }, animations: anim },
    theme: { mode: theme },
    colors: [theme === "dark" ? "#818cf8" : "#4f46e5", "#f59e0b", "#94a3b8"],
    stroke: { width: [3, 3, 2], dashArray: [0, 0, 6], curve: "straight" },
    dataLabels: { enabled: false },
    grid: { borderColor: pal.grid },
    legend: { position: "top", labels: { colors: pal.text } },
    xaxis: { type: "datetime", axisBorder: { show: false } },
    yaxis: { labels: { formatter: (v: number) => fmt(v, 0) } },
    tooltip: { x: { format: "dd MMM yyyy" }, y: { formatter: (v: number) => fmt(v) } },
  };
  return <Chart key={theme} type="line" height={340} series={series} options={options} />;
}
