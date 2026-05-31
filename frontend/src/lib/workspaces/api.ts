/**
 * Developer workspace + generated-code API client.
 * Backend: app/api/workspaces.py. Auth via HttpOnly cookie.
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

export interface Workspace {
  id: string; project_id: string; sprint_id: string | null;
  workspace_alias: string | null; status: string; workspace_type: string;
  container_name: string | null; workspace_url: string | null;
  storage_path: string | null; created_by_user_id: string | null; created_at: string | null;
}

export interface GeneratedCode {
  id: string; project_id: string; sprint_id: string | null; stage_id: string | null;
  artifact_id: string | null; file_name: string; file_type: string | null; language: string | null;
  content: string | null; status: "draft" | "reviewed" | "approved" | "rejected";
  generated_by_agent: string | null; reviewed_by_user_id: string | null; created_at: string | null;
}

// Workspaces
export const listWorkspaces = (projectId: string) =>
  req<Workspace[]>(`/api/v1/projects/${projectId}/workspaces`);
export const createWorkspace = (projectId: string, workspace_type = "artifact_only", sprint_id?: string) =>
  req<Workspace>(`/api/v1/projects/${projectId}/workspaces`, { method: "POST", body: JSON.stringify({ workspace_type, sprint_id }) });
export const startWorkspace = (workspaceId: string) =>
  req<Workspace>(`/api/v1/workspaces/${workspaceId}/start`, { method: "POST" });
export const stopWorkspace = (workspaceId: string) =>
  req<Workspace>(`/api/v1/workspaces/${workspaceId}/stop`, { method: "POST" });
export const syncWorkspace = (workspaceId: string) =>
  req<{ workspace_id: string; generated_code_count: number; by_status: Record<string, number> }>(`/api/v1/workspaces/${workspaceId}/sync-artifacts`, { method: "POST" });

// Generated code
export const listGeneratedCode = (projectId: string) =>
  req<GeneratedCode[]>(`/api/v1/projects/${projectId}/generated-code`);
export const generateCode = (projectId: string, instructions?: string, sprint_id?: string) =>
  req<{ created: number; files: GeneratedCode[] }>(`/api/v1/projects/${projectId}/generated-code/generate`, {
    method: "POST", body: JSON.stringify({ instructions: instructions || null, sprint_id: sprint_id || null }),
  });
export const createGeneratedCode = (projectId: string, data: Partial<GeneratedCode>) =>
  req<GeneratedCode>(`/api/v1/projects/${projectId}/generated-code`, { method: "POST", body: JSON.stringify(data) });
export const reviewGeneratedCode = (codeId: string, decision: "reviewed" | "rejected") =>
  req<GeneratedCode>(`/api/v1/generated-code/${codeId}/review`, { method: "POST", body: JSON.stringify({ decision }) });
export const approveGeneratedCode = (codeId: string) =>
  req<GeneratedCode>(`/api/v1/generated-code/${codeId}/approve`, { method: "POST" });
