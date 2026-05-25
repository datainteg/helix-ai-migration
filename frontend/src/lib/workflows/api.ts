/**
 * Workflow API client — backed by `/api/v1/agent-workflows` (org-wide list)
 * and `/api/v1/projects/{project_id}/agent-workflows` (project-scoped).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

async function get<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export function listOrgWorkflowRuns(token: string, limit = 50): Promise<WorkflowRun[]> {
  return get<WorkflowRun[]>(`/api/v1/agent-workflows?limit=${limit}`, token);
}

export function listProjectWorkflowRuns(token: string, projectId: string, limit = 50): Promise<WorkflowRun[]> {
  return get<WorkflowRun[]>(`/api/v1/projects/${projectId}/agent-workflows?limit=${limit}`, token);
}

export function getWorkflowDetail(token: string, workflowId: string): Promise<WorkflowDetail> {
  return get<WorkflowDetail>(`/api/v1/agent-workflows/${workflowId}`, token);
}
