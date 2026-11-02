import { motion } from "framer-motion";

export default function AnimatedBar({ percent }: { percent: number }) {
  const w = Math.min(100, Math.max(0, Number.isFinite(percent) ? percent : 0));
  return (
    <div className="bar">
      <motion.div className="barfill" initial={{ width: 0 }} animate={{ width: `${w}%` }} transition={{ duration: 0.8, ease: "easeOut" }} />
    </div>
  );
}
