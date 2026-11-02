import { motion } from "framer-motion";
import { useId } from "react";

export interface SegOption<T extends string | number> { value: T; label: string }

/** Kontrol segmen dengan "pil" yang meluncur ke pilihan aktif. */
export default function Segmented<T extends string | number>({
  options, value, onChange,
}: { options: SegOption<T>[]; value: T; onChange: (v: T) => void }) {
  const id = useId();
  return (
    <div className="seg animated" role="tablist">
      {options.map((o) => (
        <button
          key={String(o.value)} type="button" role="tab" aria-selected={o.value === value}
          className={o.value === value ? "on" : ""} onClick={() => onChange(o.value)}
        >
          {o.value === value && (
            <motion.span layoutId={`seg-${id}`} className="segpill" transition={{ type: "spring", stiffness: 500, damping: 40 }} />
          )}
          <span className="seglabel">{o.label}</span>
        </button>
      ))}
    </div>
  );
}
