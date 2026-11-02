import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import { fmt } from "../format";
import { useChartAnimations } from "../chartAnim";
import { chartPalette, useTheme } from "../theme";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const label = (key: string) => `${MONTHS[Number(key.slice(5, 7)) - 1]} ${key.slice(2, 4)}`;

export default function DividendChart({ data }: { data: { month: string; amount: string }[] }) {
  const { theme } = useTheme();
  const anim = useChartAnimations();
  if (data.length === 0) return null;
  const pal = chartPalette(theme);
  const options: ApexOptions = {
    chart: { background: "transparent", foreColor: pal.text, toolbar: { show: false }, animations: anim },
    theme: { mode: theme },
    colors: [theme === "dark" ? "#34d399" : "#059669"],
    plotOptions: { bar: { borderRadius: 4, columnWidth: "60%" } },
    dataLabels: { enabled: false },
    grid: { borderColor: pal.grid },
    xaxis: { categories: data.map((d) => label(d.month)), labels: { rotate: -45 } },
    yaxis: { labels: { formatter: (v: number) => fmt(v, 0) } },
    tooltip: { y: { formatter: (v: number) => fmt(v) } },
  };
  return <Chart key={theme} type="bar" height={300} series={[{ name: "Dividen", data: data.map((d) => Number(d.amount)) }]} options={options} />;
}
