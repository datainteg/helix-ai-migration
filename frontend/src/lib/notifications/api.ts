/**
 * Notifications client — bell, list, mark-read, and admin rules.
 *
 * Auth rides on the HttpOnly cookie (`credentials: "include"`). In read-only
 * demo sessions, mark-read POSTs 403 at the middleware — callers treat that as
 * a silent no-op.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export type Severity = "info" | "warning" | "error" | "success";

export interface Notification {
  id: string;
  type: string;
  severity: Severity;
  title: string;
  body: string | null;
  link: string | null;
  read: boolean;
  created_at: string | null;
}

export interface NotificationRule {
  event_type: string;
  enabled: boolean;
  threshold: number | null;
  channels: string; // csv: in_app[,email]
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `${path} → ${res.status}`);
  }
  // 204 / empty bodies
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export function fetchNotifications(unread = false, limit = 50): Promise<Notification[]> {
  return req<Notification[]>(`/api/v1/notifications?unread=${unread}&limit=${limit}`);
}

export function fetchUnreadCount(): Promise<{ count: number }> {
  return req<{ count: number }>(`/api/v1/notifications/unread-count`);
}

/** Mark one read. Returns false silently on a demo 403 instead of throwing. */
export async function markRead(id: string): Promise<boolean> {
  try {
    await req(`/api/v1/notifications/${id}/read`, { method: "POST" });
    return true;
  } catch {
    return false;
  }
}

export async function markAllRead(): Promise<boolean> {
  try {
    await req(`/api/v1/notifications/read-all`, { method: "POST" });
    return true;
  } catch {
    return false;
  }
}

export function fetchRules(): Promise<NotificationRule[]> {
  return req<NotificationRule[]>(`/api/v1/notifications/rules`);
}

export function upsertRule(eventType: string, data: Omit<NotificationRule, "event_type">): Promise<NotificationRule> {
  return req<NotificationRule>(`/api/v1/notifications/rules/${encodeURIComponent(eventType)}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
