/**
 * Dashboard aggregator client.
 *
 * Single round-trip to GET /api/v1/dashboard/stats. Backend computes counts
 * + real validation pass-rate + recon score in one query path. The previous
 * client-side fan-out is kept inline as a graceful fallback when the new
 * endpoint is not deployed yet (older backends).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface DashboardStats {
  activeProjects: number;
  archivedProjects: number;
  workflowsRunning: number;
  workflowsPending: number;
  workflowsCompleted: number;
  workflowsFailed: number;
  totalWorkflows: number;
  validationPassRate: number | null;
  reconScore: number | null;
  hasAnyData: boolean;
}

interface StatsWire {
  projects: { active: number; archived: number; by_status: Record<string, number> };
  workflows: { running: number; pending: number; completed: number; failed: number; total: number };
  validation: { total_results: number; passed: number; pass_rate: number | null };
  recon: { total_results: number; clean: number; score: number | null };
  has_any_data: boolean;
}

interface ProjectWire { id: string; status?: string }
interface WorkflowWire { workflow_id: string; status: string }

// SC-010: auth rides on the HttpOnly cookie (`credentials: "include"`). The
// `token` params are retained for call-site compatibility but unused.
async function fetchJson<T>(path: string, _token: string | null): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

function fromWire(wire: StatsWire): DashboardStats {
  return {
    activeProjects: wire.projects.active,
    archivedProjects: wire.projects.archived,
    workflowsRunning: wire.workflows.running,
    workflowsPending: wire.workflows.pending,
    workflowsCompleted: wire.workflows.completed,
    workflowsFailed: wire.workflows.failed,
    totalWorkflows: wire.workflows.total,
    validationPassRate: wire.validation.pass_rate,
    reconScore: wire.recon.score,
    hasAnyData: wire.has_any_data,
  };
}

/** Unwrap a list endpoint that may return a bare array or a paginated envelope. */
function unwrapItems<T>(data: unknown): T[] {
  return Array.isArray(data) ? (data as T[]) : (((data as any).items as T[]) ?? []);
}

async function fallbackStats(token: string | null): Promise<DashboardStats> {
  const [rawProjects, rawWorkflows] = await Promise.all([
    fetchJson<unknown>("/api/v1/projects?include_archived=true&limit=200", token),
    fetchJson<unknown>("/api/v1/agent-workflows?limit=200", token),
  ]);
  const projects = unwrapItems<ProjectWire>(rawProjects);
  const workflows = unwrapItems<WorkflowWire>(rawWorkflows);
  const active = projects.filter((p) => p.status !== "archived").length;
  const archived = projects.length - active;
  const counts = workflows.reduce(
    (acc, w) => {
      acc.total += 1;
      const s = (w.status || "").toLowerCase();
      if (s === "running" || s === "started" || s === "in_progress") acc.running += 1;
      else if (s === "pending" || s === "awaiting_approval") acc.pending += 1;
      else if (s === "completed" || s === "approved") acc.completed += 1;
      else if (s === "failed" || s === "rejected" || s === "expired") acc.failed += 1;
      return acc;
    },
    { total: 0, running: 0, pending: 0, completed: 0, failed: 0 },
  );
  return {
    activeProjects: active,
    archivedProjects: archived,
    workflowsRunning: counts.running,
    workflowsPending: counts.pending,
    workflowsCompleted: counts.completed,
    workflowsFailed: counts.failed,
    totalWorkflows: counts.total,
    validationPassRate: null,
    reconScore: null,
    hasAnyData: projects.length > 0 || workflows.length > 0,
  };
}

export async function fetchDashboardStats(token: string | null): Promise<DashboardStats> {
  try {
    const wire = await fetchJson<StatsWire>("/api/v1/dashboard/stats", token);
    return fromWire(wire);
  } catch {
    // 404/legacy backend → fan out manually so older deployments still work.
    return fallbackStats(token);
  }
}

export interface ActivityItem {
  workflow_id: string;
  project_id: string;
  project_name: string | null;
  kind: string;
  status: string;
  created_at: string | null;
}

export function fetchDashboardActivity(token: string | null, limit = 12): Promise<ActivityItem[]> {
  return fetchJson<ActivityItem[]>(`/api/v1/dashboard/activity?limit=${limit}`, token);
}

export interface ValidationBreakdown {
  by_status: Record<string, number>;
  total: number;
}

export function fetchValidationBreakdown(token: string | null): Promise<ValidationBreakdown> {
  return fetchJson<ValidationBreakdown>("/api/v1/dashboard/validation-breakdown", token);
}
