import type { ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import Splash from "./components/Splash";
import Analysis from "./pages/Analysis";
import Dashboard from "./pages/Dashboard";
import Dividends from "./pages/Dividends";
import DataPage from "./pages/Data";
import Journal from "./pages/Journal";
import Ledger from "./pages/Ledger";
import Login from "./pages/Login";
import Portfolio from "./pages/Portfolio";
import Reports from "./pages/Reports";
import Stocks from "./pages/Stocks";
import Targets from "./pages/Targets";
import Watchlist from "./pages/Watchlist";

function RequireAuth({ children }: { children: ReactElement }) {
  const { user, ready } = useAuth();
  if (!ready) return <Splash />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="analysis" element={<Analysis />} />
        <Route path="stocks" element={<Stocks />} />
        <Route path="watchlist" element={<Watchlist />} />
        <Route path="targets" element={<Targets />} />
        <Route path="dividends" element={<Dividends />} />
        <Route path="reports" element={<Reports />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="ledger" element={<Ledger />} />
        <Route path="journal" element={<Journal />} />
        <Route path="data" element={<DataPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
