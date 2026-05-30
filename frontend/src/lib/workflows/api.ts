/**
 * Workflow API client — backed by `/api/v1/agent-workflows` (org-wide list)
 * and `/api/v1/projects/{project_id}/agent-workflows` (project-scoped).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface WorkflowRun {
  workflow_id: string;
  run_id: string | null;
  status: string;
  mode: string;
  project_id: string;
  requirement_id: string | null;
  created_at: string | null;
}

export interface WorkflowStep {
  agent_name: string;
  step_order: number;
  status: string;
  parsed_output: Record<string, unknown> | null;
  artifact_path: string | null;
  provider_name: string | null;
  model_name: string | null;
  error_message: string | null;
  created_at: string | null;
}

export interface WorkflowDetail extends WorkflowRun {
  steps: WorkflowStep[];
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

export async function listOrgWorkflowRuns(token: string | null, limit = 50): Promise<WorkflowRun[]> {
  const data = await get<unknown>(`/api/v1/agent-workflows?limit=${limit}`, token);
  return unwrapItems<WorkflowRun>(data);
}

export async function listProjectWorkflowRuns(token: string | null, projectId: string, limit = 50): Promise<WorkflowRun[]> {
  const data = await get<unknown>(`/api/v1/projects/${projectId}/agent-workflows?limit=${limit}`, token);
  return unwrapItems<WorkflowRun>(data);
}

export function getWorkflowDetail(token: string | null, workflowId: string): Promise<WorkflowDetail> {
  return get<WorkflowDetail>(`/api/v1/agent-workflows/${workflowId}`, token);
}

export interface WorkflowArtifactContent {
  path: string;
  content: string;
}

/** Read one artifact's raw content (markdown) produced by a workflow step. */
export function getWorkflowArtifact(token: string | null, workflowId: string, path: string): Promise<WorkflowArtifactContent> {
  return get<WorkflowArtifactContent>(`/api/v1/agent-workflows/${workflowId}/artifact-content?path=${encodeURIComponent(path)}`, token);
}

interface SseStepFrame { type: "step"; step: WorkflowStep }
interface SseDoneFrame { type: "done"; status: string }
interface SseTimeoutFrame { type: "timeout" }
type SseFrame = SseStepFrame | SseDoneFrame | SseTimeoutFrame;

/**
 * Live workflow step stream. Mints a 60-second scope=sse ticket then opens
 * EventSource against /agent-workflows/{id}/stream.
 *
 * `onStep` fires for each new step. `onDone` fires once the workflow reaches
 * a terminal state (completed/approved/rejected/failed). `onError` covers
 * ticket-mint failure + transport errors. Returns the EventSource handle so
 * the caller can .close() on unmount.
 */
export async function subscribeToWorkflow(
  _token: string | null,
  workflowId: string,
  onStep: (step: WorkflowStep) => void,
  onDone?: (status: string) => void,
  onError?: (e: Event) => void,
): Promise<EventSource | null> {
  // SC-010: mint the SSE ticket via the HttpOnly cookie (credentials:"include").
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

  const url = `${API_BASE}/api/v1/agent-workflows/${workflowId}/stream?token=${encodeURIComponent(ticket)}`;
  const es = new EventSource(url);
  es.addEventListener("message", (ev) => {
    try {
      const frame = JSON.parse(ev.data) as SseFrame;
      if (frame.type === "step") onStep(frame.step);
      else if (frame.type === "done") {
        onDone?.(frame.status);
        es.close();
      }
    } catch {
      /* ignore malformed frames */
    }
  });
  if (onError) es.addEventListener("error", onError);
  return es;
}
