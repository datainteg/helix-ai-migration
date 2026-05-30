"use client";

/**
 * NotificationBell — Topbar bell + unread badge + dropdown.
 *
 * Polls the unread count every 25s (SSE stream exists server-side for a future
 * live upgrade). Light-themed to match the app. Mark-read no-ops silently in
 * read-only demo sessions (the API client swallows the 403).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bell, Check, CircleDot } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchNotifications, fetchUnreadCount, markRead, markAllRead,
  type Notification, type Severity,
} from "@/lib/notifications/api";

const POLL_MS = 25_000;

const SEV_COLOR: Record<Severity, string> = {
  info: "var(--con-info)",
  warning: "var(--con-warn)",
  error: "var(--con-err)",
  success: "var(--con-ok)",
};

function relTime(iso: string | null): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(0);
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const poll = useCallback(async () => {
    try {
      const { count } = await fetchUnreadCount();
      setCount(count);
    } catch { /* unauthenticated or transient — ignore */ }
  }, []);

  // Poll unread count.
  useEffect(() => {
    let cancelled = false;
    const tick = async () => { if (!cancelled) await poll(); };
    void tick();
    const id = setInterval(tick, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [poll]);

  // Load list when the panel opens.
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    fetchNotifications(false, 30)
      .then((n) => setItems(n))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [open]);

  // Close on outside click + Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);

  const onRead = async (id: string) => {
    setItems((cur) => cur.map((n) => (n.id === id ? { ...n, read: true } : n)));
    setCount((c) => Math.max(0, c - 1));
    await markRead(id);
  };

  const onReadAll = async () => {
    setItems((cur) => cur.map((n) => ({ ...n, read: true })));
    setCount(0);
    await markAllRead();
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={count > 0 ? `Notifications (${count} unread)` : "Notifications"}
        aria-haspopup="dialog"
        aria-expanded={open}
        className={cn(
          "relative grid place-items-center h-8 w-8 rounded-md border transition-colors",
          open ? "border-[var(--con-brand)] bg-app-2 text-ink" : "border-hx-2 bg-surface text-ink-2 hover:bg-app-2"
        )}
      >
        <Bell className="h-[15px] w-[15px]" />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[15px] h-[15px] px-1 grid place-items-center rounded-full bg-[var(--con-err)] text-white text-[9px] font-semibold tabular-nums">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {open && (
        <div role="dialog" aria-label="Notifications" className="absolute right-0 top-[42px] z-50 w-[min(360px,calc(100vw-1.5rem))] rounded-xl border border-hx bg-surface shadow-[0_24px_60px_-24px_rgba(10,10,10,0.45)] overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-hx bg-surface-hi">
            <span className="text-[13px] font-semibold text-ink">Notifications</span>
            {items.some((n) => !n.read) && (
              <button type="button" onClick={onReadAll} className="inline-flex items-center gap-1 text-[11.5px] text-ink-3 hover:text-ink">
                <Check className="h-3.5 w-3.5" /> Mark all read
              </button>
            )}
          </div>

          <div className="max-h-[380px] overflow-y-auto">
            {loading ? (
              <div className="px-4 py-6 text-center text-[12.5px] text-ink-4">Loading…</div>
            ) : items.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <Bell className="h-6 w-6 mx-auto text-ink-5" />
                <p className="mt-2 text-[12.5px] text-ink-3">You're all caught up</p>
              </div>
            ) : (
              items.map((n) => {
                const inner = (
                  <div className={cn("flex items-start gap-2.5 px-4 py-3 border-b border-hx last:border-b-0 hover:bg-app-2 transition-colors", !n.read && "bg-[var(--con-brand-soft)]/40")}>
                    <span className="mt-1 flex-shrink-0" style={{ color: SEV_COLOR[n.severity] }}>
                      <CircleDot className="h-3.5 w-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[12.5px] font-medium text-ink leading-snug">{n.title}</div>
                      {n.body && <div className="text-[11.5px] text-ink-3 mt-0.5 line-clamp-2">{n.body}</div>}
                      <div className="text-[10.5px] text-ink-4 mt-1 font-mono">{relTime(n.created_at)}</div>
                    </div>
                    {!n.read && (
                      <button type="button" onClick={(e) => { e.preventDefault(); e.stopPropagation(); void onRead(n.id); }} aria-label="Mark read" className="flex-shrink-0 p-1 rounded text-ink-4 hover:text-ink hover:bg-surface">
                        <Check className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                );
                return n.link ? (
                  <Link key={n.id} href={n.link} onClick={() => { void onRead(n.id); setOpen(false); }}>{inner}</Link>
                ) : (
                  <div key={n.id}>{inner}</div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
