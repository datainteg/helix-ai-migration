/**
 * Dashboard aggregator — pulls real counts from existing endpoints.
 *
 * No new backend endpoint required. The numbers come from:
 *   GET /projects                        → activeProjects, archivedProjects
 *   GET /agent-workflows                 → workflow rollups (pending/failed/completed)
 *
 * Validation pass-rate + recon score need cross-project aggregation that the
 * current API surface doesn't expose; those fields are returned as null so
 * the UI can show "—" rather than a fabricated number.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

interface ProjectWire {
  id: string;
  status?: string;
}

interface WorkflowWire {
  workflow_id: string;
  status: string;
}

async function fetchJson<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export async function fetchDashboardStats(token: string): Promise<DashboardStats> {
  const [projects, workflows] = await Promise.all([
    fetchJson<ProjectWire[]>("/api/v1/projects?include_archived=true&limit=200", token),
    fetchJson<WorkflowWire[]>("/api/v1/agent-workflows?limit=200", token),
  ]);

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
