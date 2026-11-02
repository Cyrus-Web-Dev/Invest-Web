import { useEffect, useRef } from "react";
import {
  ColorType, createChart,
  type CandlestickData, type HistogramData, type IChartApi, type ISeriesApi, type Time,
} from "lightweight-charts";
import { chartPalette, useTheme, type Theme } from "../theme";
import type { PriceBar } from "../types";

const UP = "#16a34a";
const DOWN = "#dc2626";

type ChartOpts = Parameters<IChartApi["applyOptions"]>[0];

function themeOptions(theme: Theme): ChartOpts {
  const p = chartPalette(theme);
  return {
    layout: { background: { type: ColorType.Solid, color: p.bg }, textColor: p.text },
    grid: { vertLines: { color: p.grid }, horzLines: { color: p.grid } },
  };
}

export default function CandlestickChart({ bars }: { bars: PriceBar[] }) {
  const { theme } = useTheme();
  const themeRef = useRef(theme);
  themeRef.current = theme;

  const boxRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  // Buat grafik sekali saat komponen tampil.
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const chart = createChart(el, {
      width: el.clientWidth,
      height: 420,
      ...themeOptions(themeRef.current),
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    const candles = chart.addCandlestickSeries({
      upColor: UP, downColor: DOWN, wickUpColor: UP, wickDownColor: DOWN, borderVisible: false,
    });
    const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "" });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    chartRef.current = chart;
    candleRef.current = candles;
    volumeRef.current = volume;

    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
    };
  }, []);

  // Ganti warna saat tema berubah.
  useEffect(() => {
    chartRef.current?.applyOptions(themeOptions(theme));
  }, [theme]);

  // Isi/perbarui data (backend mengurutkan naik per tanggal).
  useEffect(() => {
    if (!candleRef.current || !volumeRef.current || !chartRef.current) return;
    const candles: CandlestickData<Time>[] = bars.map((b) => ({
      time: b.trade_date, open: Number(b.open), high: Number(b.high), low: Number(b.low), close: Number(b.close),
    }));
    const volumes: HistogramData<Time>[] = bars.map((b) => ({
      time: b.trade_date, value: b.volume, color: Number(b.close) >= Number(b.open) ? "#86efac" : "#fca5a5",
    }));
    candleRef.current.setData(candles);
    volumeRef.current.setData(volumes);
    chartRef.current.timeScale().fitContent();
  }, [bars]);

  return <div ref={boxRef} style={{ width: "100%" }} />;
}
