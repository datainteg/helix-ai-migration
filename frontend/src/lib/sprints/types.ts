/**
 * Sprint Management — type system.
 *
 * Hierarchy: Program → Migration Portfolio → Project → Sprint → Epic → Story
 *            → Task → AgentTask / ValidationTask / ReconTask.
 *
 * Premium-tier feature; today the data lives in `mock.ts`. Future API
 * endpoints (POST /sprints, GET /sprints/{id}/board, ...) should match these
 * shapes 1:1 so swapping the source of truth is a single file change.
 */

export type SprintStatus =
  | "planning"
  | "active"
  | "review"
  | "completed"
  | "cancelled";

export type SprintHealth = "on-track" | "at-risk" | "off-track" | "blocked";

export type TaskStatus =
  | "backlog"
  | "ready"
  | "in_progress"
  | "ai_processing"
  | "human_review"
  | "validation"
  | "recon"
  | "qa"
  | "approved"
  | "completed"
  | "blocked";

export type TaskType =
  | "migration"
  | "validation"
  | "recon"
  | "code_review"
  | "notebook"
  | "schema_mapping"
  | "data_profiling"
  | "qa";

export type Priority = "P0" | "P1" | "P2" | "P3";

export type RiskLevel = "low" | "med" | "high" | "critical";

export type Environment = "dev" | "staging" | "prod";

export interface Owner {
  id: string;
  name: string;
  kind: "human" | "agent";
}

export interface SprintMilestone {
  id: string;
  label: string;
  date: string;           // ISO
  kind: "discovery" | "mapping" | "conversion" | "validation" | "recon" | "release";
  status: "pending" | "in_progress" | "done";
}

export interface SprintMetrics {
  storyPointsTotal: number;
  storyPointsDone: number;
  tasksTotal: number;
  tasksDone: number;
  validationCoveragePct: number;   // 0–100
  reconCoveragePct: number;        // 0–100
  aiAutomationPct: number;         // 0–100 share of work done by agents
  humanApprovalsPending: number;
  openRisks: number;
  criticalIssues: number;
  velocity: number;                // story points / sprint (rolling)
}

export interface SprintTask {
  id: string;
  title: string;
  type: TaskType;
  status: TaskStatus;
  priority: Priority;
  owner: Owner | null;
  aiAgent: string | null;          // BMAD agent code or display name
  epicId: string | null;
  sprintId: string;
  riskLevel: RiskLevel;
  storyPoints: number;
  estimatedHours: number;
  actualHours: number | null;
  validationStatus?: "pass" | "warn" | "fail" | "pending";
  reconStatus?: "pass" | "warn" | "fail" | "pending";
  dependencyIds: string[];
  artifactIds: string[];
  createdAt: string;
  updatedAt: string;
  blockedReason?: string;
}

export interface SprintEpic {
  id: string;
  name: string;
  description: string;
  sprintId: string;
  ownerId: string;
  status: "planning" | "in_progress" | "done";
  taskCount: number;
  doneCount: number;
}

export interface Sprint {
  id: string;
  projectId: string;
  name: string;                    // e.g. "Sprint 3 — ETL Conversion"
  index: number;                   // 1, 2, 3, …
  goal: string;
  status: SprintStatus;
  health: SprintHealth;
  startDate: string;               // ISO
  endDate: string;                 // ISO
  metrics: SprintMetrics;
  milestones: SprintMilestone[];
  burndown: BurndownPoint[];
  epics: SprintEpic[];
}

export interface BurndownPoint {
  date: string;                    // ISO date
  ideal: number;                   // ideal remaining story points
  actual: number;                  // actual remaining
}

export interface VelocityPoint {
  sprintLabel: string;             // "S1", "S2", …
  planned: number;
  delivered: number;
}

// ── Mapping canvas ──────────────────────────────────────────────────

export type MappingNodeKind =
  | "requirement_intake"
  | "source_discovery"
  | "schema_mapping"
  | "etl_conversion"
  | "notebook_generation"
  | "validation"
  | "recon"
  | "qa"
  | "uat"
  | "production_approval"
  | "release_deployment";

export type MappingNodeStatus =
  | "pending"
  | "active"
  | "ai_processing"
  | "review"
  | "blocked"
  | "completed"
  | "failed";

export interface MappingNode {
  id: string;
  kind: MappingNodeKind;
  label: string;
  ownerId: string | null;
  agent: string | null;            // BMAD agent code
  status: MappingNodeStatus;
  validationScore: number | null;  // 0–100
  reconScore: number | null;
  riskScore: number | null;
  approvalStatus: "pending" | "approved" | "rejected" | "not_required";
  artifactCount: number;
  position: { x: number; y: number };
}

export interface MappingEdge {
  id: string;
  source: string;
  target: string;
  status: "pending" | "active" | "completed" | "blocked";
  label?: string;
}

// ── Release management ─────────────────────────────────────────────

export type ReleaseStage =
  | "planned"
  | "validation"
  | "recon"
  | "uat_ready"
  | "approved"
  | "production_ready"
  | "released";

export interface MigrationRelease {
  id: string;
  name: string;                    // "Release 2026.05.27"
  projectId: string;
  sprintIds: string[];
  stage: ReleaseStage;
  targetEnvironment: Environment;
  scheduledFor: string;            // ISO
  validationScore: number;
  reconScore: number;
  rollbackReady: boolean;
  checklist: ReleaseChecklistItem[];
}

export interface ReleaseChecklistItem {
  id: string;
  label: string;
  done: boolean;
  owner: string;
}

// ── Risks ──────────────────────────────────────────────────────────

export type RiskCategory =
  | "data"
  | "validation"
  | "recon"
  | "deployment"
  | "compliance"
  | "security";

export interface SprintRisk {
  id: string;
  title: string;
  category: RiskCategory;
  level: RiskLevel;
  sprintId: string;
  ownerId: string;
  description: string;
  mitigation: string;
  status: "open" | "mitigating" | "accepted" | "closed";
  aiConfidence: number | null;     // 0–100
  createdAt: string;
}

// ── Approvals ─────────────────────────────────────────────────────

export interface SprintApproval {
  id: string;
  sprintId: string;
  taskId: string | null;
  kind: "milestone" | "release" | "code_review" | "validation_override";
  title: string;
  requestedBy: string;
  requestedAt: string;
  approvers: string[];
  status: "pending" | "approved" | "rejected" | "expired";
}

// ── Execution view ────────────────────────────────────────────────

export interface AgentExecution {
  id: string;
  agentCode: string;               // bmad-agent-dev, …
  taskId: string;
  status: "running" | "succeeded" | "failed" | "retrying" | "queued" | "cancelled";
  startedAt: string;
  durationMs: number | null;
  retries: number;
  mode: "llm" | "mock";
  log: string;
}
