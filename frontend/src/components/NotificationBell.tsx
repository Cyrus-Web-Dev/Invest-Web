import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { fmtDateTime } from "../format";
import type { Notifications } from "../types";
import Icon from "./icons";

export default function NotificationBell() {
  const [data, setData] = useState<Notifications | null>(null);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.notifications());
    } catch {
      /* kegagalan polling diabaikan */
    }
  }, []);

  useEffect(() => {
    load();
    const id = window.setInterval(load, 60_000);
    return () => window.clearInterval(id);
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  async function readAll() {
    try {
      await api.readAllNotifications();
      await load();
    } catch {
      /* abaikan */
    }
  }

  const unread = data?.unread ?? 0;
  return (
    <div className="bellwrap" ref={boxRef}>
      <button className="iconbtn" onClick={() => { setOpen((o) => !o); load(); }} aria-label="Notifikasi" title="Notifikasi">
        <Icon name="bell" size={17} />
        {unread > 0 && <span className="badgecount">{unread > 9 ? "9+" : unread}</span>}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            className="notifpanel"
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.14 }}
          >
            <div className="notifhead">
              <b>Notifikasi</b>
              {unread > 0 && <button className="btn ghost small" onClick={readAll}>Tandai dibaca</button>}
            </div>
            {data && data.items.length > 0 ? (
              <ul className="notiflist">
                {data.items.map((n) => (
                  <li key={n.id} className={n.read_at ? "" : "unread"}>
                    <b>{n.title}</b>
                    <div>{n.message}</div>
                    <time>{fmtDateTime(n.created_at)}</time>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted" style={{ padding: 14 }}>Belum ada notifikasi.</p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
