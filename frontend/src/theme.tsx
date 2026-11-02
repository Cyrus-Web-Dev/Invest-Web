import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type Theme = "light" | "dark";
const KEY = "stockfolio_theme";

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* penyimpanan tidak tersedia */
  }
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

interface ThemeCtx { theme: Theme; toggle: () => void }
const Ctx = createContext<ThemeCtx | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* abaikan */
    }
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  return <Ctx.Provider value={{ theme, toggle }}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useTheme harus dipakai di dalam ThemeProvider");
  return v;
}

/** Warna untuk grafik (library grafik tidak membaca variabel CSS). */
export function chartPalette(theme: Theme) {
  return theme === "dark"
    ? { text: "#94a3b8", grid: "#1f2a44", bg: "#111a2e" }
    : { text: "#64748b", grid: "#e2e8f0", bg: "#ffffff" };
}
