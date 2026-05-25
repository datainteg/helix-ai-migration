/**
 * Centralized mock sprint data.
 *
 * Every Sprint page imports from here so swapping to a real API later means
 * editing ONE module (`getSprints()`, `getSprint(id)`, etc.) without touching
 * the page tree.
 *
 * Data shape mirrors `types.ts`. Numbers are realistic for a 6-week migration
 * from Oracle GL to Snowflake; tweak project name to demo different scenarios.
 */

import type {
  AgentExecution,
  BurndownPoint,
  MappingEdge,
  MappingNode,
  MigrationRelease,
  Sprint,
  SprintApproval,
  SprintEpic,
  SprintMilestone,
  SprintRisk,
  SprintTask,
  VelocityPoint,
} from "./types";

// ── Static lists ────────────────────────────────────────────────────

const OWNERS = [
  { id: "u1", name: "Priya Shah",      kind: "human" as const },
  { id: "u2", name: "Daniel Park",     kind: "human" as const },
  { id: "u3", name: "Mei Lin",         kind: "human" as const },
  { id: "u4", name: "Tomás Ribeiro",   kind: "human" as const },
  { id: "u5", name: "Avery Johnson",   kind: "human" as const },
  { id: "a1", name: "Mary",            kind: "agent" as const },
  { id: "a2", name: "John",            kind: "agent" as const },
  { id: "a3", name: "Sally",           kind: "agent" as const },
  { id: "a4", name: "Winston",         kind: "agent" as const },
  { id: "a5", name: "Amelia",          kind: "agent" as const },
  { id: "a6", name: "Paige",           kind: "agent" as const },
];

function ownerById(id: string) {
  return OWNERS.find((o) => o.id === id) ?? null;
}

// ── Burndown helper ─────────────────────────────────────────────────

function makeBurndown(total: number, days: number, actual: number[]): BurndownPoint[] {
  const out: BurndownPoint[] = [];
  const start = new Date("2026-05-04T00:00:00Z");
  for (let i = 0; i < days; i++) {
    const d = new Date(start);
    d.setUTCDate(start.getUTCDate() + i);
    out.push({
      date: d.toISOString().slice(0, 10),
      ideal: Math.round(total - (i / (days - 1)) * total),
      actual: actual[i] ?? total,
    });
  }
  return out;
}

// ── Sprints ─────────────────────────────────────────────────────────

export const PROJECT_ID = "P-1042";  // Oracle GL → Snowflake

const SPRINT_GOALS = [
  "Catalog Oracle GL schema + identify downstream dependencies",
  "Map source/target schemas with type and constraint resolution",
  "Generate Snowflake DDL + Databricks notebooks via Amelia",
  "Run end-to-end validation + reconciliation gates",
  "Cutover plan, dry-run, production deployment",
];

const SPRINT_NAMES = [
  "Source Discovery",
  "Schema Mapping",
  "ETL Conversion",
  "Validation & Recon",
  "Production Cutover",
];

const SPRINT_DATES: Array<[string, string]> = [
  ["2026-04-06", "2026-04-19"],
  ["2026-04-20", "2026-05-03"],
  ["2026-05-04", "2026-05-17"],   // index 2 — ACTIVE
  ["2026-05-18", "2026-05-31"],
  ["2026-06-01", "2026-06-14"],
];

const SPRINT_STATUS: Array<Sprint["status"]> = [
  "completed", "completed", "active", "planning", "planning",
];

const SPRINT_HEALTH: Array<Sprint["health"]> = [
  "on-track", "on-track", "at-risk", "on-track", "on-track",
];

function makeEpics(sprintId: string, idx: number): SprintEpic[] {
  return [
    { id: `${sprintId}-E1`, name: "Core deliverable",        description: "Primary migration deliverable for the sprint",        sprintId, ownerId: "u1", status: idx < 2 ? "done" : idx === 2 ? "in_progress" : "planning", taskCount: 14, doneCount: idx < 2 ? 14 : idx === 2 ? 8 : 0 },
    { id: `${sprintId}-E2`, name: "Validation hardening",    description: "Row-count + checksum + schema parity",                sprintId, ownerId: "u3", status: idx < 2 ? "done" : idx === 2 ? "in_progress" : "planning", taskCount: 9,  doneCount: idx < 2 ? 9  : idx === 2 ? 4 : 0 },
    { id: `${sprintId}-E3`, name: "Reconciliation",          description: "Source vs target reconciliation reports",             sprintId, ownerId: "u4", status: idx < 2 ? "done" : idx === 2 ? "in_progress" : "planning", taskCount: 6,  doneCount: idx < 2 ? 6  : idx === 2 ? 2 : 0 },
  ];
}

function makeMilestones(sprintId: string, dates: [string, string], idx: number): SprintMilestone[] {
  const mid = new Date(dates[0]);
  mid.setUTCDate(mid.getUTCDate() + 7);
  const midISO = mid.toISOString().slice(0, 10);
  const done = idx < 2;
  const active = idx === 2;
  return [
    { id: `${sprintId}-M1`, label: "Sprint kickoff",      date: dates[0], kind: "discovery",  status: done ? "done" : active ? "done"        : "pending" },
    { id: `${sprintId}-M2`, label: "Mid-sprint review",   date: midISO,   kind: "mapping",    status: done ? "done" : active ? "in_progress" : "pending" },
    { id: `${sprintId}-M3`, label: "Sprint demo",         date: dates[1], kind: "validation", status: done ? "done" : "pending" },
  ];
}

export const SPRINTS: Sprint[] = SPRINT_NAMES.map((name, i) => {
  const id = `S-${i + 1}`;
  const total = 60 + i * 5;
  const doneSP = SPRINT_STATUS[i] === "completed" ? total : i === 2 ? 38 : 0;
  return {
    id,
    projectId: PROJECT_ID,
    name: `Sprint ${i + 1} — ${name}`,
    index: i + 1,
    goal: SPRINT_GOALS[i],
    status: SPRINT_STATUS[i],
    health: SPRINT_HEALTH[i],
    startDate: `${SPRINT_DATES[i][0]}T00:00:00Z`,
    endDate:   `${SPRINT_DATES[i][1]}T00:00:00Z`,
    metrics: {
      storyPointsTotal: total,
      storyPointsDone: doneSP,
      tasksTotal: 29,
      tasksDone: SPRINT_STATUS[i] === "completed" ? 29 : i === 2 ? 18 : 0,
      validationCoveragePct: SPRINT_STATUS[i] === "completed" ? 96 : i === 2 ? 64 : 0,
      reconCoveragePct:      SPRINT_STATUS[i] === "completed" ? 98 : i === 2 ? 58 : 0,
      aiAutomationPct: 71,
      humanApprovalsPending: i === 2 ? 4 : 0,
      openRisks: i === 2 ? 3 : 0,
      criticalIssues: i === 2 ? 1 : 0,
      velocity: 56 + i * 3,
    },
    milestones: makeMilestones(id, SPRINT_DATES[i], i),
    burndown: i === 2
      ? makeBurndown(total, 14, [70, 67, 64, 62, 58, 54, 51, 48, 44, 41, 38, 36, 34, 32])
      : makeBurndown(total, 14, Array.from({ length: 14 }, (_, k) => Math.max(0, total - Math.round((k / 13) * total)))),
    epics: makeEpics(id, i),
  };
});

export const ACTIVE_SPRINT = SPRINTS[2];

// ── Tasks ───────────────────────────────────────────────────────────

const TASK_TEMPLATES: Array<{ title: string; type: SprintTask["type"]; agent: string | null }> = [
  { title: "Profile GL_LEDGER source rows",        type: "data_profiling", agent: "Mary" },
  { title: "Map GL_TRANS → trans_fact schema",     type: "schema_mapping", agent: "Winston" },
  { title: "Convert MERGE PL/SQL → Snowflake SQL", type: "migration",      agent: "Amelia" },
  { title: "Generate validation rules",            type: "validation",     agent: "Mary" },
  { title: "Build recon notebook",                 type: "notebook",       agent: "Amelia" },
  { title: "Reconcile sample run",                 type: "recon",          agent: null },
  { title: "Adversarial code review (migrate.py)", type: "code_review",    agent: "Amelia" },
  { title: "Approve cutover plan",                 type: "qa",             agent: null },
];

const TASK_STATUSES: Array<SprintTask["status"]> = [
  "completed", "completed", "in_progress", "ai_processing",
  "human_review", "validation", "recon", "blocked",
];

export const TASKS: SprintTask[] = TASK_TEMPLATES.flatMap((t, idx) => {
  const baseId = `T-${1000 + idx}`;
  return [0, 1, 2].map((suffix) => ({
    id: `${baseId}.${suffix}`,
    title: `${t.title} (${suffix === 0 ? "Schema A" : suffix === 1 ? "Schema B" : "Schema C"})`,
    type: t.type,
    status: TASK_STATUSES[(idx + suffix) % TASK_STATUSES.length],
    priority: (["P0", "P1", "P2", "P3"] as const)[idx % 4],
    owner: ownerById(t.agent ? OWNERS.find((o) => o.name === t.agent)?.id ?? "u1" : `u${(idx % 5) + 1}`),
    aiAgent: t.agent,
    epicId: `${ACTIVE_SPRINT.id}-E${(idx % 3) + 1}`,
    sprintId: ACTIVE_SPRINT.id,
    riskLevel: idx === 7 ? "critical" : idx % 4 === 0 ? "high" : idx % 2 === 0 ? "med" : "low",
    storyPoints: [1, 2, 3, 5, 8][idx % 5],
    estimatedHours: 8 + idx,
    actualHours: TASK_STATUSES[(idx + suffix) % TASK_STATUSES.length] === "completed" ? 7 + idx : null,
    validationStatus: ["pass", "warn", "pending", "fail"][idx % 4] as SprintTask["validationStatus"],
    reconStatus:      ["pending", "pass", "warn", "pending"][idx % 4] as SprintTask["reconStatus"],
    dependencyIds: suffix > 0 ? [`${baseId}.${suffix - 1}`] : [],
    artifactIds: [`art-${idx}`, `art-${idx}-spec`],
    createdAt: "2026-05-04T09:00:00Z",
    updatedAt: "2026-05-21T14:32:00Z",
    blockedReason: TASK_STATUSES[(idx + suffix) % TASK_STATUSES.length] === "blocked" ? "Awaiting target Snowflake warehouse provisioning" : undefined,
  }));
});

// ── Mapping canvas ──────────────────────────────────────────────────

export const MAPPING_NODES: MappingNode[] = [
  { id: "n1",  kind: "requirement_intake",   label: "Requirement Intake",   ownerId: "u1", agent: "Mary",    status: "completed",     validationScore: 100, reconScore: null, riskScore: 12, approvalStatus: "approved",     artifactCount: 1, position: { x: 40,   y: 240 } },
  { id: "n2",  kind: "source_discovery",     label: "Source Discovery",     ownerId: "u2", agent: "Mary",    status: "completed",     validationScore: 96,  reconScore: null, riskScore: 18, approvalStatus: "approved",     artifactCount: 4, position: { x: 240,  y: 120 } },
  { id: "n3",  kind: "schema_mapping",       label: "Schema Mapping",       ownerId: "u4", agent: "Winston", status: "completed",     validationScore: 92,  reconScore: null, riskScore: 22, approvalStatus: "approved",     artifactCount: 7, position: { x: 240,  y: 360 } },
  { id: "n4",  kind: "etl_conversion",       label: "ETL Conversion",       ownerId: "u3", agent: "Amelia",  status: "ai_processing", validationScore: null, reconScore: null, riskScore: 48, approvalStatus: "not_required", artifactCount: 12, position: { x: 460,  y: 240 } },
  { id: "n5",  kind: "notebook_generation",  label: "Notebook Generation",  ownerId: "u3", agent: "Amelia",  status: "active",        validationScore: null, reconScore: null, riskScore: 34, approvalStatus: "not_required", artifactCount: 5, position: { x: 680,  y: 120 } },
  { id: "n6",  kind: "validation",           label: "Validation",           ownerId: "u3", agent: "Mary",    status: "review",        validationScore: 64,   reconScore: null, riskScore: 56, approvalStatus: "pending",      artifactCount: 8, position: { x: 680,  y: 360 } },
  { id: "n7",  kind: "recon",                label: "Reconciliation",       ownerId: "u4", agent: null,      status: "pending",       validationScore: null, reconScore: null, riskScore: 41, approvalStatus: "pending",      artifactCount: 0, position: { x: 900,  y: 240 } },
  { id: "n8",  kind: "qa",                   label: "QA Sign-off",          ownerId: "u5", agent: "Amelia",  status: "pending",       validationScore: null, reconScore: null, riskScore: 30, approvalStatus: "pending",      artifactCount: 0, position: { x: 1120, y: 120 } },
  { id: "n9",  kind: "uat",                  label: "UAT",                  ownerId: "u5", agent: null,      status: "pending",       validationScore: null, reconScore: null, riskScore: 28, approvalStatus: "pending",      artifactCount: 0, position: { x: 1120, y: 360 } },
  { id: "n10", kind: "production_approval",  label: "Production Approval",  ownerId: "u1", agent: null,      status: "pending",       validationScore: null, reconScore: null, riskScore: 24, approvalStatus: "pending",      artifactCount: 0, position: { x: 1340, y: 240 } },
  { id: "n11", kind: "release_deployment",   label: "Release Deployment",   ownerId: "u2", agent: null,      status: "pending",       validationScore: null, reconScore: null, riskScore: 22, approvalStatus: "pending",      artifactCount: 0, position: { x: 1560, y: 240 } },
];

export const MAPPING_EDGES: MappingEdge[] = [
  { id: "e1",  source: "n1", target: "n2",  status: "completed" },
  { id: "e2",  source: "n1", target: "n3",  status: "completed" },
  { id: "e3",  source: "n2", target: "n4",  status: "completed" },
  { id: "e4",  source: "n3", target: "n4",  status: "completed" },
  { id: "e5",  source: "n4", target: "n5",  status: "active"    },
  { id: "e6",  source: "n4", target: "n6",  status: "active"    },
  { id: "e7",  source: "n5", target: "n7",  status: "pending"   },
  { id: "e8",  source: "n6", target: "n7",  status: "blocked", label: "validation < 80%" },
  { id: "e9",  source: "n7", target: "n8",  status: "pending"   },
  { id: "e10", source: "n7", target: "n9",  status: "pending"   },
  { id: "e11", source: "n8", target: "n10", status: "pending"   },
  { id: "e12", source: "n9", target: "n10", status: "pending"   },
  { id: "e13", source: "n10", target: "n11", status: "pending"  },
];

// ── Velocity, releases, risks, approvals, executions ───────────────

export const VELOCITY: VelocityPoint[] = [
  { sprintLabel: "S1", planned: 60, delivered: 58 },
  { sprintLabel: "S2", planned: 65, delivered: 67 },
  { sprintLabel: "S3", planned: 70, delivered: 38 },   // current — partial
  { sprintLabel: "S4", planned: 75, delivered: 0 },
  { sprintLabel: "S5", planned: 80, delivered: 0 },
];

export const RELEASES: MigrationRelease[] = [
  {
    id: "REL-2026-05-27",
    name: "Release 2026.05.27 — GL Core Cutover",
    projectId: PROJECT_ID,
    sprintIds: ["S-3", "S-4"],
    stage: "validation",
    targetEnvironment: "prod",
    scheduledFor: "2026-05-27T18:00:00Z",
    validationScore: 64,
    reconScore: 58,
    rollbackReady: true,
    checklist: [
      { id: "c1", label: "All P0 tasks completed",        done: true,  owner: "Priya Shah" },
      { id: "c2", label: "Validation ≥ 95%",              done: false, owner: "Mei Lin" },
      { id: "c3", label: "Recon parity ≥ 99%",            done: false, owner: "Tomás Ribeiro" },
      { id: "c4", label: "Rollback playbook sign-off",    done: true,  owner: "Avery Johnson" },
      { id: "c5", label: "DBA on-call confirmed",         done: false, owner: "Daniel Park" },
      { id: "c6", label: "Stakeholder go/no-go meeting",  done: false, owner: "Priya Shah" },
    ],
  },
  {
    id: "REL-2026-06-10",
    name: "Release 2026.06.10 — Reporting Layer",
    projectId: PROJECT_ID,
    sprintIds: ["S-5"],
    stage: "planned",
    targetEnvironment: "staging",
    scheduledFor: "2026-06-10T18:00:00Z",
    validationScore: 0,
    reconScore: 0,
    rollbackReady: false,
    checklist: [],
  },
];

export const RISKS: SprintRisk[] = [
  { id: "R-1", title: "Validation coverage trending below threshold", category: "validation", level: "high",     sprintId: "S-3", ownerId: "u3", description: "GL_TRANS validations are flaky on null timestamps — 6/47 rules failing.", mitigation: "Tighten coalesce + add fallback to source createdAt.", status: "mitigating", aiConfidence: 71, createdAt: "2026-05-15T09:00:00Z" },
  { id: "R-2", title: "Snowflake warehouse provisioning delay",       category: "deployment", level: "critical", sprintId: "S-3", ownerId: "u2", description: "Procurement has not signed off on the X-LARGE SKU for prod recon runs.",       mitigation: "Run with LARGE + extend recon window by 2h.",         status: "open",       aiConfidence: null, createdAt: "2026-05-20T11:30:00Z" },
  { id: "R-3", title: "PII column not classified in source",          category: "compliance", level: "med",      sprintId: "S-3", ownerId: "u5", description: "customer_email_alt found unclassified in GL_AUDIT.",                              mitigation: "Run profiler with regex pack; tag + mask.",           status: "mitigating", aiConfidence: 88,   createdAt: "2026-05-18T16:12:00Z" },
];

export const APPROVALS: SprintApproval[] = [
  { id: "AP-1", sprintId: "S-3", taskId: "T-1004.0", kind: "milestone",          title: "Approve mid-sprint review",     requestedBy: "Priya Shah", requestedAt: "2026-05-21T10:00:00Z", approvers: ["Avery Johnson"], status: "pending" },
  { id: "AP-2", sprintId: "S-3", taskId: "T-1006.1", kind: "code_review",        title: "Adversarial review for migrate.py", requestedBy: "Amelia",     requestedAt: "2026-05-22T13:45:00Z", approvers: ["Mei Lin"],       status: "pending" },
  { id: "AP-3", sprintId: "S-3", taskId: null,       kind: "release",            title: "Release 2026.05.27 go/no-go",   requestedBy: "Priya Shah", requestedAt: "2026-05-23T09:00:00Z", approvers: ["Avery Johnson", "Daniel Park"], status: "pending" },
  { id: "AP-4", sprintId: "S-3", taskId: "T-1003.2", kind: "validation_override", title: "Override 3 minor validation warnings", requestedBy: "Mei Lin", requestedAt: "2026-05-22T16:20:00Z", approvers: ["Avery Johnson"], status: "pending" },
];

export const EXECUTIONS: AgentExecution[] = [
  { id: "EX-1", agentCode: "bmad-agent-dev",      taskId: "T-1002.0", status: "running",    startedAt: "2026-05-25T10:14:00Z", durationMs: null,    retries: 0, mode: "llm",  log: "Generating MERGE statement for GL_TRANS … phase 3/5" },
  { id: "EX-2", agentCode: "bmad-agent-analyst",  taskId: "T-1000.1", status: "succeeded",  startedAt: "2026-05-25T09:58:00Z", durationMs: 184_000, retries: 0, mode: "llm",  log: "Profiled 412 columns, 17 anomalies flagged" },
  { id: "EX-3", agentCode: "bmad-agent-architect", taskId: "T-1001.1", status: "succeeded", startedAt: "2026-05-25T09:31:00Z", durationMs:  92_000, retries: 0, mode: "llm",  log: "Mapped trans_fact with 4 type coercions" },
  { id: "EX-4", agentCode: "bmad-agent-dev",      taskId: "T-1004.2", status: "retrying",   startedAt: "2026-05-25T10:02:00Z", durationMs: null,    retries: 2, mode: "llm",  log: "Notebook gen failed — retry 2/3 with smaller context" },
  { id: "EX-5", agentCode: "bmad-agent-dev",      taskId: "T-1006.0", status: "queued",     startedAt: "2026-05-25T10:20:00Z", durationMs: null,    retries: 0, mode: "mock", log: "Awaiting upstream code-review artifact" },
  { id: "EX-6", agentCode: "bmad-agent-tech-writer", taskId: "T-1003.0", status: "failed",   startedAt: "2026-05-25T08:11:00Z", durationMs:  41_000, retries: 3, mode: "llm",  log: "Rate-limited by Anthropic after 3 retries" },
];

// ── Accessors ───────────────────────────────────────────────────────

export function getSprints(): Sprint[] { return SPRINTS; }
export function getSprint(id: string): Sprint | undefined { return SPRINTS.find((s) => s.id === id); }
export function getTasksForSprint(sprintId: string): SprintTask[] { return TASKS.filter((t) => t.sprintId === sprintId); }
export function getMappingGraph(): { nodes: MappingNode[]; edges: MappingEdge[] } { return { nodes: MAPPING_NODES, edges: MAPPING_EDGES }; }
export function getRisksForSprint(sprintId: string): SprintRisk[] { return RISKS.filter((r) => r.sprintId === sprintId); }
export function getApprovalsForSprint(sprintId: string): SprintApproval[] { return APPROVALS.filter((a) => a.sprintId === sprintId); }
export function getExecutions(): AgentExecution[] { return EXECUTIONS; }
export function getReleases(): MigrationRelease[] { return RELEASES; }
export function getVelocity(): VelocityPoint[] { return VELOCITY; }
export function getActiveSprint(): Sprint { return ACTIVE_SPRINT; }
