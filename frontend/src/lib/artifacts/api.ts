/**
 * Artifact API client.
 *
 * Per-project artifact registry (the developer workspace + diff view consume
 * this). Backend: app/api/artifacts.py.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

async function get<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

/** Unwrap a list endpoint that may return a bare array or a paginated envelope. */
function unwrapItems<T>(data: unknown): T[] {
  return Array.isArray(data) ? (data as T[]) : (((data as any).items as T[]) ?? []);
}

export async function listProjectArtifacts(token: string, projectId: string, limit = 100): Promise<Artifact[]> {
  const data = await get<unknown>(`/api/v1/projects/${projectId}/artifacts?limit=${limit}`, token);
  return unwrapItems<Artifact>(data);
}

export async function listOrgArtifacts(token: string, limit = 100): Promise<Artifact[]> {
  const data = await get<unknown>(`/api/v1/artifacts?limit=${limit}`, token);
  return unwrapItems<Artifact>(data);
}

export function listArtifactVersions(token: string, artifactId: string): Promise<Artifact[]> {
  return get<Artifact[]>(`/api/v1/artifacts/${artifactId}/versions`, token);
}
