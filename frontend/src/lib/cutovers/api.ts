/**
 * Cutover API client.
 *
 * Wraps the backend's MigrationCutover state machine. State transitions are
 * explicit POSTs; the backend rejects illegal moves with 409.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type CutoverState =
  | "bulk"
  | "tail"
  | "freeze"
  | "diff"
  | "flip"
  | "done"
  | "rolled_back";

export const CUTOVER_STATE_ORDER: CutoverState[] = [
  "bulk", "tail", "freeze", "diff", "flip", "done",
];

export const ALLOWED_NEXT: Record<CutoverState, CutoverState[]> = {
  bulk:        ["tail", "rolled_back"],
  tail:        ["freeze", "rolled_back"],
  freeze:      ["diff", "rolled_back"],
  diff:        ["flip", "rolled_back"],
  flip:        ["done", "rolled_back"],
  done:        [],
  rolled_back: [],
};

export interface Cutover {
  id: string;
  project_id: string;
  workflow_id: string | null;
  source_ref: string;
  target_ref: string;
  state: CutoverState;
  notes: string | null;
  diff_summary: {
    source_count: number;
    target_count: number;
    diff_pct: number;
    sample_size: number;
    sample_hash?: string | null;
  } | null;
  timestamps: Record<CutoverState, string | null>;
  created_at: string | null;
}

export interface CutoverCreateInput {
  source_ref: string;
  target_ref: string;
  workflow_id?: string;
  notes?: string;
}

export interface CutoverDiffInput {
  source_count: number;
  target_count: number;
  diff_pct: number;
  sample_size: number;
  sample_hash?: string;
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

export async function listCutovers(token: string, projectId: string): Promise<Cutover[]> {
  const data = await req<unknown>(`/api/v1/projects/${projectId}/cutovers`, token);
  return Array.isArray(data) ? data : ((data as any).items ?? []);
}

export function createCutover(token: string, projectId: string, data: CutoverCreateInput): Promise<Cutover> {
  return req<Cutover>(`/api/v1/projects/${projectId}/cutovers`, token, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function transitionCutover(token: string, cutoverId: string, targetState: CutoverState, notes?: string): Promise<Cutover> {
  return req<Cutover>(`/api/v1/cutovers/${cutoverId}/transition`, token, {
    method: "POST",
    body: JSON.stringify({ target_state: targetState, notes }),
  });
}

export function recordDiff(token: string, cutoverId: string, data: CutoverDiffInput): Promise<Cutover> {
  return req<Cutover>(`/api/v1/cutovers/${cutoverId}/diff`, token, {
    method: "POST",
    body: JSON.stringify(data),
  });
}
