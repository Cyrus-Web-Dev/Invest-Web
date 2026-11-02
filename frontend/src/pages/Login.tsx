import { motion } from "framer-motion";
import { lazy, Suspense, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import Icon from "../components/icons";
import Notice, { type NoticeState } from "../components/Notice";
import { errMsg } from "../hooks";

// Three.js hanya dimuat jika perangkat mendukung; chunk terpisah agar aplikasi utama tetap ringan.
const Hero3D = lazy(() => import("../components/Hero3D"));

function canShow3D(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
  if (window.matchMedia("(max-width: 860px)").matches) return false;   // panel hero disembunyikan di layar kecil
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

const FEATURES = [
  "Pantau net worth, untung/rugi, dan imbal hasil tahunan (XIRR)",
  "Grafik alokasi aset, pertumbuhan portofolio, dan candlestick",
  "Catat transaksi, setoran modal, dan dividen dengan aman",
  "Katalog saham IDX dan bursa AS siap pakai",
];

export default function Login() {
  const { user, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<NoticeState | null>(null);
  const [show3d] = useState(canShow3D);

  if (user) return <Navigate to="/" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      if (mode === "login") await login(email.trim(), password);
      else await register(email.trim(), password, name.trim());
    } catch (err) {
      setMsg({ kind: "error", text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="authsplit">
      <aside className="authhero">
        {show3d && (
          <Suspense fallback={null}>
            <Hero3D />
          </Suspense>
        )}
        <div className="brand light"><span className="logo"><Icon name="activity" size={18} /></span> Stockfolio</div>
        <h1>Kelola portofolio saham dengan data yang jelas.</h1>
        <p>Platform pencatatan dan analitik untuk investor ritel.</p>
        <ul>
          {FEATURES.map((f) => (
            <li key={f}><span className="tick"><Icon name="check" size={14} /></span>{f}</li>
          ))}
        </ul>
      </aside>
      <div className="authpane">
        <motion.form className="authcard" onSubmit={submit} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: "easeOut" }}>
          <h2>{mode === "login" ? "Masuk ke akun" : "Buat akun baru"}</h2>
          <p className="muted">{mode === "login" ? "Selamat datang kembali." : "Gratis, hanya butuh satu menit."}</p>
          {mode === "register" && (
            <label>Nama lengkap
              <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
            </label>
          )}
          <label>Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </label>
          <label>Password {mode === "register" && <span className="muted">(minimal 8 karakter)</span>}
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
              minLength={mode === "register" ? 8 : 1} maxLength={128}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </label>
          <Notice state={msg} />
          <button className="btn" disabled={busy}>{busy ? "Memproses…" : mode === "login" ? "Masuk" : "Daftar"}</button>
          <button type="button" className="btn ghost" onClick={() => { setMode(mode === "login" ? "register" : "login"); setMsg(null); }}>
            {mode === "login" ? "Belum punya akun? Daftar" : "Sudah punya akun? Masuk"}
          </button>
        </motion.form>
      </div>
    </div>
  );
}
