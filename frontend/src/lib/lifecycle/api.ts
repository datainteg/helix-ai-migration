/**
 * Stage-gated lifecycle + migration-artifact API client.
 *
 * Backend: app/api/lifecycle.py, app/api/lifecycle_artifacts.py,
 * app/api/stage_agents.py. Auth rides on the HttpOnly cookie
 * (`credentials: "include"`); no Authorization header is set in JS.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((d && (d.detail as string)) || `${path} → ${res.status}`);
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

// ── Types (mirror the backend serializers) ───────────────────────────
export type StageStatus =
  | "not_started" | "running" | "generated" | "under_review" | "edit_requested"
  | "resubmitted" | "approved" | "rejected" | "completed" | "failed" | "skipped";

export interface MigrationStage {
  id: string;
  project_id: string;
  stage_key: string;
  stage_name: string;
  stage_order: number;
  status: StageStatus;
  assigned_agent: string | null;
  is_optional: boolean;
  current_artifact_id: string | null;
  started_at: string | null;
  generated_at: string | null;
  submitted_for_review_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  completed_at: string | null;
}

export interface MigrationArtifact {
  id: string;
  project_id: string;
  stage_id: string | null;
  artifact_type: string;
  title: string;
  description: string | null;
  current_version_id: string | null;
  status: string;
  created_by_agent: string | null;
  created_by_user_id: string | null;
  approved_by_user_id: string | null;
  approved_at: string | null;
  created_at: string | null;
}

export interface MigrationArtifactVersion {
  id: string;
  artifact_id: string;
  version_number: number;
  content_markdown: string | null;
  content_json: unknown | null;
  change_summary: string | null;
  created_by_type: string;
  created_by_agent: string | null;
  created_by_user_id: string | null;
  source_version_id: string | null;
  created_at: string | null;
}

export interface ArtifactComment {
  id: string;
  artifact_id: string;
  artifact_version_id: string | null;
  user_id: string | null;
  comment: string;
  created_at: string | null;
}

export interface VersionCompare {
  artifact_id: string;
  from_version: number;
  to_version: number;
  from_content: string;
  to_content: string;
  diff: string;
  added_lines: number;
  removed_lines: number;
}

export interface StageAgentRun {
  stage_key: string;
  artifact_id: string;
  version_id: string | null;
  status: string;
  agent: string;
  mode: string;
}

export interface ContinueResult {
  completed: boolean;
  next_stage: string | null;
  auto_ran: boolean;
  run?: StageAgentRun;
  stage?: { stage_key: string; status: string; assigned_agent: string | null };
}

// ── Lifecycle (stages) ───────────────────────────────────────────────
export const getLifecycle = (projectId: string) =>
  req<MigrationStage[]>(`/api/v1/projects/${projectId}/lifecycle`);

export const getCurrentStage = (projectId: string) =>
  req<MigrationStage | null>(`/api/v1/projects/${projectId}/lifecycle/current`);

export interface StageTransition {
  id: string; stage_id: string; from_status: string | null; to_status: string;
  action: string; actor_type: string; actor_id: string | null; comment: string | null; created_at: string | null;
}
export const getStageTransitions = (projectId: string) =>
  req<StageTransition[]>(`/api/v1/projects/${projectId}/lifecycle/transitions`);

export const initializeLifecycle = (projectId: string) =>
  req<MigrationStage[]>(`/api/v1/projects/${projectId}/lifecycle/initialize`, { method: "POST" });

const stagePost = <T = MigrationStage>(projectId: string, stageKey: string, action: string, body?: unknown) =>
  req<T>(`/api/v1/projects/${projectId}/lifecycle/${stageKey}/${action}`, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });

export const startStage = (projectId: string, stageKey: string) => stagePost(projectId, stageKey, "start");
export const submitStageForReview = (projectId: string, stageKey: string, artifactId?: string) =>
  stagePost(projectId, stageKey, "submit-review", { artifact_id: artifactId });
export const approveStage = (projectId: string, stageKey: string, comment?: string) =>
  stagePost(projectId, stageKey, "approve", { comment });
export const rejectStage = (projectId: string, stageKey: string, comment: string) =>
  stagePost(projectId, stageKey, "reject", { comment });
export const requestStageChanges = (projectId: string, stageKey: string, comment: string) =>
  stagePost(projectId, stageKey, "request-changes", { comment });
export const resubmitStage = (projectId: string, stageKey: string, artifactVersionId?: string) =>
  stagePost(projectId, stageKey, "resubmit", { artifact_version_id: artifactVersionId });
export const skipStage = (projectId: string, stageKey: string, reason: string) =>
  stagePost(projectId, stageKey, "skip", { reason });
export const advanceLifecycle = (projectId: string) =>
  req<MigrationStage | null>(`/api/v1/projects/${projectId}/lifecycle/advance`, { method: "POST" });

// ── Stage agent execution ────────────────────────────────────────────
export const runStageAgent = (projectId: string, stageKey: string, instructions?: string) =>
  req<StageAgentRun>(`/api/v1/projects/${projectId}/stages/${stageKey}/run-agent`, {
    method: "POST", body: JSON.stringify({ instructions: instructions || null }),
  });
export const regenerateStageAgent = (projectId: string, stageKey: string, instructions?: string) =>
  req<StageAgentRun>(`/api/v1/projects/${projectId}/stages/${stageKey}/regenerate`, {
    method: "POST", body: JSON.stringify({ instructions: instructions || null }),
  });
export const continueAfterApproval = (projectId: string, stageKey: string) =>
  req<ContinueResult>(`/api/v1/projects/${projectId}/stages/${stageKey}/continue-after-approval`, { method: "POST" });

// ── Migration artifacts (markdown-in-DB) ─────────────────────────────
export const listMigrationArtifacts = (projectId: string) =>
  req<MigrationArtifact[]>(`/api/v1/projects/${projectId}/migration-artifacts`);
export const getMigrationArtifact = (artifactId: string) =>
  req<MigrationArtifact>(`/api/v1/migration-artifacts/${artifactId}`);
export const getArtifactVersions = (artifactId: string) =>
  req<MigrationArtifactVersion[]>(`/api/v1/migration-artifacts/${artifactId}/versions`);
export const createArtifactVersion = (artifactId: string, contentMarkdown: string, changeSummary?: string, baseVersionId?: string) =>
  req<MigrationArtifactVersion>(`/api/v1/migration-artifacts/${artifactId}/versions`, {
    method: "POST",
    body: JSON.stringify({ content_markdown: contentMarkdown, change_summary: changeSummary, base_version_id: baseVersionId }),
  });
export const submitArtifactForReview = (artifactId: string, versionId?: string) =>
  req<MigrationArtifact>(`/api/v1/migration-artifacts/${artifactId}/submit-review`, {
    method: "POST", body: JSON.stringify({ version_id: versionId }),
  });
export const approveArtifact = (artifactId: string, versionId?: string, comment?: string) =>
  req<MigrationArtifact>(`/api/v1/migration-artifacts/${artifactId}/approve`, {
    method: "POST", body: JSON.stringify({ version_id: versionId, comment }),
  });
export const rejectArtifact = (artifactId: string, comment: string, versionId?: string) =>
  req<MigrationArtifact>(`/api/v1/migration-artifacts/${artifactId}/reject`, {
    method: "POST", body: JSON.stringify({ version_id: versionId, comment }),
  });
export const requestArtifactChanges = (artifactId: string, comment: string, versionId?: string) =>
  req<MigrationArtifact>(`/api/v1/migration-artifacts/${artifactId}/request-changes`, {
    method: "POST", body: JSON.stringify({ version_id: versionId, comment }),
  });
export const listArtifactComments = (artifactId: string) =>
  req<ArtifactComment[]>(`/api/v1/migration-artifacts/${artifactId}/comments`);
export const addArtifactComment = (artifactId: string, comment: string, versionId?: string) =>
  req<ArtifactComment>(`/api/v1/migration-artifacts/${artifactId}/comments`, {
    method: "POST", body: JSON.stringify({ comment, version_id: versionId }),
  });
export const compareVersions = (artifactId: string, fromVersion: number, toVersion: number) =>
  req<VersionCompare>(`/api/v1/migration-artifacts/${artifactId}/compare?from_version=${fromVersion}&to_version=${toVersion}`);
