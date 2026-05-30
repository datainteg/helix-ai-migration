/**
 * Projects admin actions client — owner picker, update owner/status,
 * soft-delete, and admin-only force (hard) delete. Auth via cookie.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface OrgMember {
  user_id: string;
  name: string | null;
  email: string | null;
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((d && d.detail) || `${path} → ${res.status}`);
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export function fetchProjectMembers(): Promise<OrgMember[]> {
  return req<OrgMember[]>(`/api/v1/projects/members`);
}

export function updateProject(id: string, patch: { owner_id?: string; status?: string }) {
  return req(`/api/v1/projects/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export function archiveProject(id: string) {
  return req(`/api/v1/projects/${id}/archive`, { method: "PATCH" });
}

/** Soft delete (status=deleted). project:write. */
export function deleteProject(id: string) {
  return req<void>(`/api/v1/projects/${id}`, { method: "DELETE" });
}

/** Admin-only hard delete — permanently removes the project + all children. */
export function forceDeleteProject(id: string) {
  return req<void>(`/api/v1/projects/${id}/force`, { method: "DELETE" });
}
