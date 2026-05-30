/**
 * DB-migration API client.
 *
 * Connections (sources/targets) come from
 *   GET /api/v1/projects/{project_id}/sources
 *   GET /api/v1/projects/{project_id}/targets
 * and a migration run is kicked off via
 *   POST /api/v1/projects/{project_id}/migrations
 *
 * The run itself reuses the agent-workflow machinery, so the returned
 * `workflow_id` (e.g. `mig-...`) is watched with the helpers in
 * `@/lib/workflows/api` (getWorkflowDetail + subscribeToWorkflow). Approval is
 * a human-gate signal against the same agent-workflow endpoints.
 *
 * SC-010: auth rides on the HttpOnly cookie via `credentials: "include"` — no
 * Authorization header anywhere.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface Connection {
  id: string;
  name: string;
  connector_type: string;
  status: string;
}

export interface StartMigrationResult {
  workflow_id: string;
  run_id: string;
  status: string;
  mode: string;
  kind: string;
}

/** Unwrap a list endpoint that may return a bare array or a {items:[]} envelope. */
function unwrapItems<T>(data: unknown): T[] {
  return Array.isArray(data) ? (data as T[]) : (((data as any)?.items as T[]) ?? []);
}

/** Pull a human-readable message off an error response body when present. */
async function detailFrom(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    const detail = (body as any)?.detail;
    if (typeof detail === "string" && detail) return detail;
    if (detail) return JSON.stringify(detail);
  } catch {
    /* non-JSON body — fall through */
  }
  return fallback;
}

export async function listSources(projectId: string): Promise<Connection[]> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/sources`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`sources → ${res.status}`);
  return unwrapItems<Connection>(await res.json());
}

export async function listTargets(projectId: string): Promise<Connection[]> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/targets`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`targets → ${res.status}`);
  return unwrapItems<Connection>(await res.json());
}

export async function startMigration(
  projectId: string,
  body: { source_connection_id: string; target_connection_id?: string },
): Promise<StartMigrationResult> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/migrations`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(await detailFrom(res, `migrations → ${res.status}`));
  }
  return res.json() as Promise<StartMigrationResult>;
}

export async function approveMigration(workflowId: string, notes = ""): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/v1/agent-workflows/${workflowId}/signal-approve`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes }),
    },
  );
  if (!res.ok) throw new Error(await detailFrom(res, `signal-approve → ${res.status}`));
}

export async function rejectMigration(workflowId: string, notes = ""): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/v1/agent-workflows/${workflowId}/signal-reject`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes }),
    },
  );
  if (!res.ok) throw new Error(await detailFrom(res, `signal-reject → ${res.status}`));
}
