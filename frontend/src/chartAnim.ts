import { useReducedMotion } from "framer-motion";
import type { ApexOptions } from "apexcharts";

type Anim = NonNullable<NonNullable<ApexOptions["chart"]>["animations"]>;

/** Pengaturan animasi grafik ApexCharts; dimatikan jika pengguna memilih "kurangi animasi". */
export function useChartAnimations(): Anim {
  const reduce = useReducedMotion();
  if (reduce) return { enabled: false };
  return {
    enabled: true,
    easing: "easeout",
    speed: 650,
    animateGradually: { enabled: true, delay: 80 },
    dynamicAnimation: { enabled: true, speed: 300 },
  };
}
