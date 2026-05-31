/**
 * Artifact API client.
 *
 * Per-project artifact registry (the developer workspace + diff view consume
 * this). Backend: app/api/artifacts.py.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface Artifact {
  id: string;
  filename: string;
  ext?: string;
  file_type?: string;
  project_id?: string;
  content_hash?: string;
  size_bytes?: number;
  storage_path?: string;
  status?: string;
  version?: number;
  created_at?: string | null;
}

// SC-010: auth rides on the HttpOnly cookie (`credentials: "include"`). The
// `token` params are retained for call-site compatibility but unused.
async function get<T>(path: string, _token: string | null): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

/** Unwrap a list endpoint that may return a bare array or a paginated envelope. */
function unwrapItems<T>(data: unknown): T[] {
  return Array.isArray(data) ? (data as T[]) : (((data as any).items as T[]) ?? []);
}

export async function listProjectArtifacts(token: string | null, projectId: string, limit = 100): Promise<Artifact[]> {
  const data = await get<unknown>(`/api/v1/projects/${projectId}/artifacts?limit=${limit}`, token);
  return unwrapItems<Artifact>(data);
}

export async function listOrgArtifacts(token: string | null, limit = 100): Promise<Artifact[]> {
  const data = await get<unknown>(`/api/v1/artifacts?limit=${limit}`, token);
  return unwrapItems<Artifact>(data);
}

export interface ArtifactVersion {
  id: string;
  artifact_id: string;
  version_number: string;
  content_hash: string;
  generated_by_agent?: string | null;
  llm_model?: string | null;
  change_summary?: string | null;
  approval_status: string;
  approved_by?: string | null;
}

export function listArtifactVersions(token: string | null, artifactId: string): Promise<ArtifactVersion[]> {
  return get<ArtifactVersion[]>(`/api/v1/artifacts/${artifactId}/versions`, token);
}

export interface ArtifactContent {
  artifact_id: string;
  version_number: string;
  file_type?: string | null;
  filename?: string | null;
  content_hash?: string | null;
  content: string | null;
  truncated: boolean;
  size_bytes: number;
  note?: string;
}

/** Fetch decoded text content for an artifact (latest, or a specific version). */
export function fetchArtifactContent(token: string | null, artifactId: string, version?: string): Promise<ArtifactContent> {
  const q = version ? `?version=${encodeURIComponent(version)}` : "";
  return get<ArtifactContent>(`/api/v1/artifacts/${artifactId}/content${q}`, token);
}

/** Save an edited artifact as a NEW version (history preserved). */
export async function saveArtifactContent(token: string | null, artifactId: string, content: string, changeSummary?: string): Promise<ArtifactContent> {
  const res = await fetch(`${API_BASE}/api/v1/artifacts/${artifactId}/content`, {
    method: "PUT", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, change_summary: changeSummary }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((d && d.detail) || `Save failed (${res.status})`);
  }
  return res.json() as Promise<ArtifactContent>;
}
