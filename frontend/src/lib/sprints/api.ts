/**
 * Sprint Management API client.
 *
 * Each function maps 1:1 to a backend endpoint under /api/v1/...sprints.
 * Backend response shapes use snake_case (Python convention) — adapters
 * here normalize to the camelCase TS types in `types.ts` so pages don't
 * need to know about the wire format.
 *
 * All requests inject the Authorization header from the supplied token.
 * Pages get the token from `useAuth()`.
 *
 * Empty array is the default on a failed/unauthorized request — pages
 * already render an EmptyState when the list is empty.
 */

import type {
  AgentExecution, BurndownPoint, MappingEdge, MappingNode,
  MigrationRelease, Sprint, SprintApproval, SprintRisk,
  SprintTask, VelocityPoint,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// SC-010: auth now rides on the HttpOnly `helix_token` cookie (sent via
// `credentials: "include"`), not an Authorization header. The `token` params
// below are retained for call-site compatibility but are no longer used to
// build a header.
async function req<T>(
  path: string,
  _token: string | null,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ── Backend wire shapes (snake_case) ────────────────────────────────

interface WireSprint {
  id: string;
  project_id: string;
  index: number;
  name: string;
  goal: string | null;
  status: Sprint["status"];
  health: Sprint["health"];
  start_date: string | null;
  end_date: string | null;
  metrics: Sprint["metrics"] | null;
  milestones: Sprint["milestones"] | null;
}

interface WireTask {
  id: string;
  sprint_id: string;
  title: string;
  type: SprintTask["type"];
  status: SprintTask["status"];
  priority: SprintTask["priority"];
  owner_id: string | null;
  owner_name: string | null;
  owner_kind: "human" | "agent";
  ai_agent: string | null;
  epic_id: string | null;
  risk_level: SprintTask["riskLevel"];
  story_points: number;
  estimated_hours: number;
  actual_hours: number | null;
  validation_status: SprintTask["validationStatus"];
  recon_status: SprintTask["reconStatus"];
  dependency_ids: string[];
  artifact_ids: string[];
  blocked_reason: string | null;
}

interface WireRisk {
  id: string;
  sprint_id: string;
  title: string;
  category: SprintRisk["category"];
  level: SprintRisk["level"];
  description: string | null;
  mitigation: string | null;
  status: SprintRisk["status"];
  ai_confidence: number | null;
  owner_id: string | null;
}

interface WireApproval {
  id: string;
  sprint_id: string;
  task_id: string | null;
  kind: SprintApproval["kind"];
  title: string;
  requested_by: string;
  approvers: string[];
  status: SprintApproval["status"];
  decided_at: string | null;
  decided_by: string | null;
}

interface WireRelease {
  id: string;
  project_id: string;
  name: string;
  sprint_ids: string[];
  stage: MigrationRelease["stage"];
  target_environment: MigrationRelease["targetEnvironment"];
  scheduled_for: string | null;
  validation_score: number;
  recon_score: number;
  rollback_ready: boolean;
  checklist: MigrationRelease["checklist"];
}

interface WireNode {
  id: string;
  kind: MappingNode["kind"];
  label: string;
  owner_id: string | null;
  agent: string | null;
  status: MappingNode["status"];
  validation_score: number | null;
  recon_score: number | null;
  risk_score: number | null;
  approval_status: MappingNode["approvalStatus"];
  artifact_count: number;
  position_x: number;
  position_y: number;
}

interface WireEdge {
  id: string;
  source_id: string;
  target_id: string;
  status: MappingEdge["status"];
  label: string | null;
}

interface WireExecution {
  id: string;
  agent_code: string;
  task_id: string | null;
  status: AgentExecution["status"];
  started_at: string;
  duration_ms: number | null;
  retries: number;
  mode: AgentExecution["mode"];
  log: string | null;
}

interface WireVelocity { sprint_label: string; planned: number; delivered: number }
interface WireBurndown { date: string; ideal: number; actual: number }

// ── Adapters ────────────────────────────────────────────────────────

const sprintFromWire = (w: WireSprint): Sprint => ({
  id: w.id,
  projectId: w.project_id,
  index: w.index,
  name: w.name,
  goal: w.goal ?? "",
  status: w.status,
  health: w.health,
  startDate: w.start_date ?? "",
  endDate: w.end_date ?? "",
  metrics: w.metrics ?? {
    storyPointsTotal: 0, storyPointsDone: 0, tasksTotal: 0, tasksDone: 0,
    validationCoveragePct: 0, reconCoveragePct: 0, aiAutomationPct: 0,
    humanApprovalsPending: 0, openRisks: 0, criticalIssues: 0, velocity: 0,
  },
  milestones: w.milestones ?? [],
  burndown: [],   // populated by getBurndown
  epics: [],      // not yet modeled in backend
});

const taskFromWire = (w: WireTask): SprintTask => ({
  id: w.id,
  title: w.title,
  type: w.type,
  status: w.status,
  priority: w.priority,
  owner: w.owner_name
    ? { id: w.owner_id ?? w.owner_name, name: w.owner_name, kind: w.owner_kind }
    : null,
  aiAgent: w.ai_agent,
  epicId: w.epic_id,
  sprintId: w.sprint_id,
  riskLevel: w.risk_level,
  storyPoints: w.story_points,
  estimatedHours: w.estimated_hours,
  actualHours: w.actual_hours,
  validationStatus: w.validation_status,
  reconStatus: w.recon_status,
  dependencyIds: w.dependency_ids ?? [],
  artifactIds: w.artifact_ids ?? [],
  createdAt: "",
  updatedAt: "",
  blockedReason: w.blocked_reason ?? undefined,
});

const riskFromWire = (w: WireRisk): SprintRisk => ({
  id: w.id,
  title: w.title,
  category: w.category,
  level: w.level,
  sprintId: w.sprint_id,
  ownerId: w.owner_id ?? "",
  description: w.description ?? "",
  mitigation: w.mitigation ?? "",
  status: w.status,
  aiConfidence: w.ai_confidence,
  createdAt: "",
});

const approvalFromWire = (w: WireApproval): SprintApproval => ({
  id: w.id,
  sprintId: w.sprint_id,
  taskId: w.task_id,
  kind: w.kind,
  title: w.title,
  requestedBy: w.requested_by,
  requestedAt: "",
  approvers: w.approvers ?? [],
  status: w.status,
});

const releaseFromWire = (w: WireRelease): MigrationRelease => ({
  id: w.id,
  name: w.name,
  projectId: w.project_id,
  sprintIds: w.sprint_ids ?? [],
  stage: w.stage,
  targetEnvironment: w.target_environment,
  scheduledFor: w.scheduled_for ?? "",
  validationScore: w.validation_score,
  reconScore: w.recon_score,
  rollbackReady: w.rollback_ready,
  checklist: w.checklist ?? [],
});

const nodeFromWire = (w: WireNode): MappingNode => ({
  id: w.id,
  kind: w.kind,
  label: w.label,
  ownerId: w.owner_id,
  agent: w.agent,
  status: w.status,
  validationScore: w.validation_score,
  reconScore: w.recon_score,
  riskScore: w.risk_score,
  approvalStatus: w.approval_status,
  artifactCount: w.artifact_count,
  position: { x: w.position_x, y: w.position_y },
});

const edgeFromWire = (w: WireEdge): MappingEdge => ({
  id: w.id,
  source: w.source_id,
  target: w.target_id,
  status: w.status,
  label: w.label ?? undefined,
});

const executionFromWire = (w: WireExecution): AgentExecution => ({
  id: w.id,
  agentCode: w.agent_code,
  taskId: w.task_id ?? "",
  status: w.status,
  startedAt: w.started_at,
  durationMs: w.duration_ms,
  retries: w.retries,
  mode: w.mode,
  log: w.log ?? "",
});

const velocityFromWire = (w: WireVelocity): VelocityPoint => ({
  sprintLabel: w.sprint_label,
  planned: w.planned,
  delivered: w.delivered,
});

const burndownFromWire = (w: WireBurndown): BurndownPoint => ({
  date: w.date,
  ideal: w.ideal,
  actual: w.actual,
});

// ── Public fetchers ────────────────────────────────────────────────

export async function fetchSprints(token: string | null, projectId: string): Promise<Sprint[]> {
  const data = await req<unknown>(`/projects/${projectId}/sprints`, token);
  const rows: WireSprint[] = Array.isArray(data) ? data : ((data as any).items ?? []);
  return rows.map(sprintFromWire);
}

export async function fetchActiveSprint(token: string | null, projectId: string): Promise<Sprint | null> {
  const row = await req<WireSprint | null>(`/projects/${projectId}/sprints/active`, token);
  return row ? sprintFromWire(row) : null;
}

export async function fetchSprint(token: string | null, sprintId: string): Promise<Sprint> {
  const row = await req<WireSprint>(`/sprints/${sprintId}`, token);
  return sprintFromWire(row);
}

export async function fetchTasks(token: string | null, sprintId: string): Promise<SprintTask[]> {
  const data = await req<unknown>(`/sprints/${sprintId}/tasks`, token);
  const rows: WireTask[] = Array.isArray(data) ? data : ((data as any).items ?? []);
  return rows.map(taskFromWire);
}

export async function fetchRisks(token: string | null, sprintId: string): Promise<SprintRisk[]> {
  const rows = await req<WireRisk[]>(`/sprints/${sprintId}/risks`, token);
  return rows.map(riskFromWire);
}

export async function fetchApprovals(token: string | null, sprintId: string): Promise<SprintApproval[]> {
  const rows = await req<WireApproval[]>(`/sprints/${sprintId}/approvals`, token);
  return rows.map(approvalFromWire);
}

export async function fetchReleases(token: string | null, projectId: string): Promise<MigrationRelease[]> {
  const rows = await req<WireRelease[]>(`/projects/${projectId}/sprints/releases`, token);
  return rows.map(releaseFromWire);
}

export async function fetchMapping(token: string | null, projectId: string): Promise<{ nodes: MappingNode[]; edges: MappingEdge[] }> {
  const data = await req<{ nodes: WireNode[]; edges: WireEdge[] }>(`/projects/${projectId}/sprints/mapping`, token);
  return { nodes: data.nodes.map(nodeFromWire), edges: data.edges.map(edgeFromWire) };
}

export async function fetchExecutions(token: string | null, projectId: string): Promise<AgentExecution[]> {
  const rows = await req<WireExecution[]>(`/projects/${projectId}/sprints/executions`, token);
  return rows.map(executionFromWire);
}

export async function fetchVelocity(token: string | null, projectId: string): Promise<VelocityPoint[]> {
  const rows = await req<WireVelocity[]>(`/projects/${projectId}/sprints/velocity`, token);
  return rows.map(velocityFromWire);
}

export async function fetchBurndown(token: string | null, sprintId: string): Promise<BurndownPoint[]> {
  const rows = await req<WireBurndown[]>(`/sprints/${sprintId}/burndown`, token);
  return rows.map(burndownFromWire);
}

// ── Mutations ──────────────────────────────────────────────────────

export async function patchTaskStatus(token: string | null, taskId: string, status: SprintTask["status"]): Promise<void> {
  await req(`/sprint-tasks/${taskId}`, token, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function decideApproval(token: string | null, approvalId: string, decision: "approved" | "rejected"): Promise<void> {
  await req(`/sprint-approvals/${approvalId}/decide`, token, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}

export async function seedSprints(token: string | null, projectId: string): Promise<{ sprints_created: number }> {
  return req(`/projects/${projectId}/sprints/seed`, token, { method: "POST" });
}

// ── Create paths ─────────────────────────────────────────────────────

export interface NewSprintInput {
  name: string;
  goal?: string;
  status?: Sprint["status"];
  health?: Sprint["health"];
  start_date?: string;
  end_date?: string;
}

export async function createSprint(
  token: string | null,
  projectId: string,
  input: NewSprintInput,
): Promise<Sprint> {
  const row = await req<WireSprint>(`/projects/${projectId}/sprints`, token, {
    method: "POST",
    body: JSON.stringify(input),
  });
  return sprintFromWire(row);
}

export interface NewTaskInput {
  title: string;
  type: SprintTask["type"];
  status?: SprintTask["status"];
  priority?: SprintTask["priority"];
  owner_name?: string;
  owner_kind?: "human" | "agent";
  ai_agent?: string;
  risk_level?: SprintTask["riskLevel"];
  story_points?: number;
  estimated_hours?: number;
}

export async function createTask(
  token: string | null,
  sprintId: string,
  input: NewTaskInput,
): Promise<SprintTask> {
  const row = await req<WireTask>(`/sprints/${sprintId}/tasks`, token, {
    method: "POST",
    body: JSON.stringify(input),
  });
  return taskFromWire(row);
}

// ── SSE execution stream ────────────────────────────────────────────

/**
 * Subscribe to /projects/{id}/sprints/executions/stream as an EventSource.
 *
 * EventSource cannot send custom headers, so the URL must carry auth in the
 * query string. To avoid leaking a full-power bearer token into web-server
 * and proxy logs, we trade the bearer for a 60-second scope=sse ticket from
 * POST /auth/sse-ticket and use that ticket only.
 *
 * Returns a promise that resolves to the EventSource handle (or null on a
 * ticket-mint failure). Caller is responsible for `.close()`.
 *
 * SC-010: the SSE-ticket mint authenticates via the HttpOnly cookie
 * (`credentials: "include"`) instead of a bearer header; it still returns the
 * short-TTL ticket in the body for the EventSource URL. The `_token` param is
 * retained for call-site compatibility but unused.
 */
export async function subscribeToExecutions(
  _token: string | null,
  projectId: string,
  onSnapshot: (rows: AgentExecution[]) => void,
  onError?: (e: Event) => void,
): Promise<EventSource | null> {
  let ticket: string;
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/sse-ticket`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) {
      onError?.(new Event("ticket_failed"));
      return null;
    }
    ticket = (await res.json()).ticket as string;
  } catch (e) {
    onError?.(e as Event);
    return null;
  }

  const url = `${API_BASE}/api/v1/projects/${projectId}/sprints/executions/stream?token=${encodeURIComponent(ticket)}`;
  const es = new EventSource(url);
  es.addEventListener("message", (ev) => {
    try {
      const payload = JSON.parse(ev.data) as
        | { type: "snapshot"; rows: WireExecution[]; new_count: number }
        | { type: "timeout" };
      if (payload.type === "snapshot") {
        onSnapshot(payload.rows.map(executionFromWire));
      }
    } catch {
      /* ignore malformed frames — server keeps streaming */
    }
  });
  if (onError) es.addEventListener("error", onError);
  return es;
}
