import { parseTags } from "../format";

const SUGGESTIONS = ["value", "growth", "dividend", "speculative", "trading", "jangka-panjang", "defensif", "profit-taking", "cut-loss"];

export default function TagInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const current = parseTags(value);
  function toggle(tag: string) {
    const next = current.includes(tag) ? current.filter((t) => t !== tag) : [...current, tag];
    onChange(next.join(", "));
  }
  return (
    <>
      <label>Tag (opsional, maks. 5, pisahkan dengan koma)
        <input value={value} onChange={(e) => onChange(e.target.value)} placeholder="mis. value, dividend" />
      </label>
      <div className="tagrow">
        {SUGGESTIONS.map((t) => (
          <button type="button" key={t} className={`tagchip ${current.includes(t) ? "on" : ""}`} onClick={() => toggle(t)}>{t}</button>
        ))}
      </div>
    </>
  );
}
