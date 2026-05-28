import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const formatNumber = (n: number): string => {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toString();
};

export const formatPercent = (n: number, digits = 1): string =>
  `${n.toFixed(digits)}%`;

export const formatDate = (iso: string): string => {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

export const formatTime = (iso: string): string => {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
};

/**
 * Centralised relative-time formatting (UI-040 / UI-044). Returns a compact
 * English string like "just now", "5m ago", "3h ago", "2d ago", falling back
 * to an absolute date for anything older than a week. Pages previously rolled
 * their own inline variants (e.g. projects/page.tsx) — use this instead.
 */
export const formatRelative = (iso: string): string => {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffMs = Date.now() - then;
  const sec = Math.round(diffMs / 1000);
  if (sec < 45) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 7) return `${day}d ago`;
  return formatDate(iso);
};

export const initials = (name: string): string => {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
};

export type StatusKind =
  | "running"
  | "completed"
  | "queued"
  | "pending"
  | "failed"
  | "healthy"
  | "warning"
  | "critical"
  | "idle"
  | "draft";

export const statusTone = (s: StatusKind | string): { bg: string; fg: string; dot: string } => {
  const k = String(s).toLowerCase();
  if (["running", "in_progress", "active"].includes(k))
    return { bg: "bg-helix-50", fg: "text-helix-700", dot: "bg-helix-500" };
  if (["completed", "passed", "success", "healthy", "done"].includes(k))
    return { bg: "bg-emerald-50", fg: "text-emerald-700", dot: "bg-emerald-500" };
  if (["queued", "pending"].includes(k))
    return { bg: "bg-amber-50", fg: "text-amber-700", dot: "bg-amber-500" };
  if (["failed", "error", "critical"].includes(k))
    return { bg: "bg-red-50", fg: "text-red-700", dot: "bg-red-500" };
  if (["warning", "warn", "at_risk"].includes(k))
    return { bg: "bg-orange-50", fg: "text-orange-700", dot: "bg-orange-500" };
  return { bg: "bg-zinc-100", fg: "text-zinc-700", dot: "bg-zinc-400" };
};
