/**
 * Business sign-off client. Backend: app/api/signoff.py. Auth via HttpOnly cookie.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init, credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((d && (d.detail as string)) || `${path} → ${res.status}`);
  }
  const t = await res.text();
  return (t ? JSON.parse(t) : undefined) as T;
}

export interface Signoff {
  id: string; project_id: string; recon_report_id: string | null;
  recipient_email: string | null; subject: string | null; body: string | null;
  attachment_paths: string[]; status: "draft" | "sent" | "approved" | "rejected";
  sent_at: string | null; approved_at: string | null; created_by_user_id: string | null; created_at: string | null;
}

export const listSignoffs = (projectId: string) => req<Signoff[]>(`/api/v1/projects/${projectId}/signoff`);
export const createSignoffDraft = (projectId: string, reconReportId?: string) =>
  req<Signoff>(`/api/v1/projects/${projectId}/signoff/draft`, { method: "POST", body: JSON.stringify({ recon_report_id: reconReportId || null }) });
export const updateSignoff = (signoffId: string, patch: { recipient_email?: string; subject?: string; body?: string }) =>
  req<Signoff>(`/api/v1/signoff/${signoffId}`, { method: "PATCH", body: JSON.stringify(patch) });
export const sendSignoff = (signoffId: string) =>
  req<Signoff>(`/api/v1/signoff/${signoffId}/send`, { method: "POST" });
export const markSignoffApproved = (signoffId: string, comment?: string) =>
  req<Signoff>(`/api/v1/signoff/${signoffId}/mark-approved`, { method: "POST", body: JSON.stringify({ comment }) });
export const markSignoffRejected = (signoffId: string, comment?: string) =>
  req<Signoff>(`/api/v1/signoff/${signoffId}/mark-rejected`, { method: "POST", body: JSON.stringify({ comment }) });
