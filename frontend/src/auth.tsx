import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api";
import type { User } from "./types";

interface AuthCtx {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  useEffect(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    api.me().then(setUser).catch(() => setToken(null)).finally(() => setReady(true));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const t = await api.login(email, password);
    setToken(t.access_token);
    setUser(await api.me());
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      await api.register(email, password, fullName);
      await login(email, password);
    },
    [login],
  );

  const refreshUser = useCallback(async () => {
    setUser(await api.me());
  }, []);

  return <Ctx.Provider value={{ user, ready, login, register, logout, refreshUser }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth harus dipakai di dalam AuthProvider");
  return v;
}
