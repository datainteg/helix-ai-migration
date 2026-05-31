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

/** Restore an archived/soft-deleted project back to draft. project:write. */
export function restoreProject(id: string) {
  return req(`/api/v1/projects/${id}/restore`, { method: "PATCH" });
}

/** Soft delete (status=deleted). project:write. */
export function deleteProject(id: string) {
  return req<void>(`/api/v1/projects/${id}`, { method: "DELETE" });
}

/** Admin-only hard delete — permanently removes the project + all children. */
export function forceDeleteProject(id: string) {
  return req<void>(`/api/v1/projects/${id}/force`, { method: "DELETE" });
}

/** Put a project on hold or set it live; a comment (reason) is required. */
export function setProjectHold(id: string, onHold: boolean, comment: string) {
  return req(`/api/v1/projects/${id}/hold`, { method: "POST", body: JSON.stringify({ on_hold: onHold, comment }) });
}

export interface ProjectComment {
  id: string;
  author_id: string | null;
  author_name: string | null;
  kind: "comment" | "hold" | "live";
  body: string;
  created_at: string | null;
}

export function fetchProjectComments(id: string): Promise<ProjectComment[]> {
  return req<ProjectComment[]>(`/api/v1/projects/${id}/comments`);
}

export function addProjectComment(id: string, body: string): Promise<ProjectComment> {
  return req<ProjectComment>(`/api/v1/projects/${id}/comments`, { method: "POST", body: JSON.stringify({ body }) });
}

export interface ChatTurn { role: "user" | "assistant"; content: string; }

/** Ask the project-aware orchestrator agent about THIS project. */
export function askProject(projectId: string, message: string, history: ChatTurn[]): Promise<{ answer: string }> {
  return req<{ answer: string }>(`/api/v1/assistant/ask-project`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, message, history }),
  });
}
