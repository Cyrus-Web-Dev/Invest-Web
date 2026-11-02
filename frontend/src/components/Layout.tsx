import { AnimatePresence, motion } from "framer-motion";
import { NavLink, useLocation, useOutlet } from "react-router-dom";
import { useAuth } from "../auth";
import { fmt } from "../format";
import { useTheme } from "../theme";
import Icon from "./icons";
import NotificationBell from "./NotificationBell";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/analysis", label: "Analisis" },
  { to: "/stocks", label: "Saham" },
  { to: "/watchlist", label: "Pantauan" },
  { to: "/targets", label: "Target" },
  { to: "/dividends", label: "Dividen" },
  { to: "/reports", label: "Laporan" },
  { to: "/portfolio", label: "Transaksi" },
  { to: "/ledger", label: "Riwayat" },
  { to: "/journal", label: "Jurnal" },
  { to: "/data", label: "Impor / Ekspor" },
];

const initials = (name?: string) =>
  (name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w.charAt(0).toUpperCase())
    .join("") || "?";

export default function Layout() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const location = useLocation();
  const outlet = useOutlet();
  return (
    <>
      {user?.is_demo && (
        <div className="demobar">MODE DEMO · semua data adalah simulasi untuk peragaan aplikasi, bukan data investasi nyata</div>
      )}
      <header className="topbar">
        <div className="brand">
          <span className="logo"><Icon name="activity" size={18} /></span>
          Stockfolio
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}>
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span layoutId="navpill" className="navpill" transition={{ type: "spring", stiffness: 500, damping: 40 }} />
                  )}
                  <span className="navlabel">{n.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="userbox">
          <span className="cashchip" title="Saldo kas">
            <Icon name="wallet" size={15} /> {fmt(user?.cash_balance)}
          </span>
          <NotificationBell />
          <button className="iconbtn" onClick={toggle} aria-label="Ganti tema" title="Ganti tema">
            <Icon name={theme === "dark" ? "sun" : "moon"} size={17} />
          </button>
          <span className="avatar" title={user?.email}>{initials(user?.full_name)}</span>
          <span className="username">{user?.full_name}</span>
          <button className="btn ghost small" onClick={logout}>Keluar</button>
        </div>
      </header>
      <main className="container">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.16, ease: "easeOut" }}
          >
            {outlet}
          </motion.div>
        </AnimatePresence>
      </main>
      <footer className="footer">
        Stockfolio · Data harga dari Yahoo Finance dapat tertunda · Bukan saran investasi
      </footer>
    </>
  );
}
