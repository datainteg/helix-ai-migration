/**
 * Schema-drift watcher client.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface SchemaSnapshot {
  id: string;
  project_id: string;
  source_ref: string;
  table_count: number;
  column_count: number;
  taken_at: string | null;
  created_at: string | null;
}

export interface SchemaDrift {
  baseline_id: string | null;
  baseline_taken_at?: string;
  latest_id: string | null;
  latest_taken_at?: string;
  added_tables: string[];
  removed_tables: string[];
  column_changes: {
    schema: string;
    table: string;
    added_columns: string[];
    removed_columns: string[];
    type_changes: { column: string; from: string | null; to: string | null }[];
  }[];
  drift_detected: boolean;
  note?: string;
}

export interface SnapshotPayload {
  schemas: string[];
  tables: {
    schema_name: string;
    table_name: string;
    columns: { name: string; data_type: string; is_nullable?: boolean }[];
  }[];
}

async function req<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `${path} → ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function listSnapshots(token: string, projectId: string, sourceRef: string): Promise<SchemaSnapshot[]> {
  return req<SchemaSnapshot[]>(
    `/api/v1/projects/${projectId}/sources/${encodeURIComponent(sourceRef)}/schema-snapshots`,
    token,
  );
}

export function takeSnapshot(token: string, projectId: string, sourceRef: string, data: SnapshotPayload): Promise<SchemaSnapshot> {
  return req<SchemaSnapshot>(
    `/api/v1/projects/${projectId}/sources/${encodeURIComponent(sourceRef)}/schema-snapshots`,
    token,
    { method: "POST", body: JSON.stringify(data) },
  );
}

export function computeDrift(token: string, projectId: string, sourceRef: string): Promise<SchemaDrift> {
  return req<SchemaDrift>(
    `/api/v1/projects/${projectId}/sources/${encodeURIComponent(sourceRef)}/drift`,
    token,
  );
}
