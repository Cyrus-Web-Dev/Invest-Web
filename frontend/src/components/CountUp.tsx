import { animate, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { fmt } from "../format";

/** Angka yang "menghitung naik" ke nilai tujuan. Tanpa animasi bila pengguna memilih reduced motion. */
export default function CountUp({
  value, digits = 2, duration = 0.9,
}: { value: string | number; digits?: number; duration?: number }) {
  const target = Number(value);
  const reduce = useReducedMotion();
  const current = useRef(0);
  const [shown, setShown] = useState<number>(reduce || !Number.isFinite(target) ? target : 0);

  useEffect(() => {
    if (!Number.isFinite(target)) return;
    if (reduce) {
      current.current = target;
      setShown(target);
      return;
    }
    const controls = animate(current.current, target, {
      duration,
      ease: "easeOut",
      onUpdate: (v) => {
        current.current = v;
        setShown(v);
      },
    });
    return () => controls.stop();
  }, [target, reduce, duration]);

  return <>{Number.isFinite(shown) ? fmt(shown, digits) : "—"}</>;
}
