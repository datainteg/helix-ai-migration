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

export interface ProjectRequirement {
  id: string;
  source_text: string;
  status: string;
  version: string;
  created_at: string | null;
}

export function listProjectRequirements(projectId: string): Promise<ProjectRequirement[]> {
  return get<ProjectRequirement[]>(`/api/v1/projects/${projectId}/requirements`, null);
}

/** Create a migration requirement (the rich prompt the pipeline plans from). */
export async function createProjectRequirement(projectId: string, sourceText: string): Promise<ProjectRequirement> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/requirements`, {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_text: sourceText }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((d && d.detail) || `Create failed (${res.status})`);
  }
  return res.json() as Promise<ProjectRequirement>;
}

/** Compile a structured requirement spec into the rich prompt text the agents
 * plan from. Multi-schema/multi-table migrations need this depth. The fields
 * shown depend on the project's migration_type (see TYPE_FIELDS). */
export interface RequirementSpec {
  goal: string;
  scope: string;          // schemas/tables include/exclude
  typeRules: string;      // type-mapping preferences
  constraints: string;    // keys/indexes/constraints handling
  data: string;           // data vs schema-only, volume, PII
  transforms: string;     // renames/splits/denorm
  objects: string;        // views/procs/sequences/triggers
  conventions: string;    // target naming/partitioning
  // type-specific (optional — only some types show these)
  validation: string;        // validation/recon rules + tolerances
  fileFormat: string;        // CSV/Parquet/JSON, delimiter, encoding, compression
  fileHeaderMapping: string; // header row + file-field → column mapping
  targetTable: string;       // destination table(s)/schema for the load
  sourceQuery: string;       // SQL / table selection to extract
  outputLayout: string;      // export file naming / partitioning / one-file-per-table
}

export const EMPTY_SPEC: RequirementSpec = {
  goal: "", scope: "", typeRules: "", constraints: "", data: "", transforms: "",
  objects: "", conventions: "", validation: "", fileFormat: "", fileHeaderMapping: "",
  targetTable: "", sourceQuery: "", outputLayout: "",
};

export interface ReqFieldMeta {
  key: keyof RequirementSpec;
  label: string;        // form label
  heading: string;      // compiled-prompt section heading
  placeholder: string;
  full?: boolean;       // span both columns in the form grid
}

/** Single source of truth for every requirement field (form label, compiled
 * heading, placeholder). TYPE_FIELDS selects which appear per migration type. */
export const FIELD_META: Record<keyof RequirementSpec, ReqFieldMeta> = {
  goal:        { key: "goal", label: "Migration goal *", heading: "Migration goal", full: true, placeholder: "e.g. Migrate the Sales OLTP DB from PostgreSQL 15 to Snowflake (staging)." },
  scope:       { key: "scope", label: "Scope — schemas/tables", heading: "Scope (schemas / tables to include or exclude)", placeholder: "Include: sales.*, hr.employees. Exclude: audit_logs." },
  typeRules:   { key: "typeRules", label: "Type-mapping rules", heading: "Type-mapping rules", placeholder: "jsonb → VARIANT; numeric(38,x) preserved; timestamptz → TIMESTAMP_TZ." },
  constraints: { key: "constraints", label: "Constraints, keys & indexes", heading: "Constraints, keys & indexes", placeholder: "Preserve PK/FK as constraints; recreate unique indexes." },
  data:        { key: "data", label: "Data handling", heading: "Data handling (volume, batching, PII)", placeholder: "Migrate data (~2M rows), batch 50k; no PII masking in staging." },
  transforms:  { key: "transforms", label: "Transformations", heading: "Transformations (rename / split / denormalize)", placeholder: "Rename legacy_id → id; split full_name into first/last." },
  objects:     { key: "objects", label: "Special objects", heading: "Special objects (views / procedures / sequences / triggers)", placeholder: "Migrate views; document stored procs (manual port)." },
  conventions: { key: "conventions", label: "Target conventions", heading: "Target conventions (naming / partitioning / clustering)", placeholder: "snake_case; cluster orders by order_date." },
  validation:  { key: "validation", label: "Validation & reconciliation", heading: "Validation & reconciliation rules", placeholder: "Row-count + checksum per table; numeric tolerance 0; flag mismatches." },
  fileFormat:  { key: "fileFormat", label: "File format", heading: "File format", placeholder: "CSV, comma-delimited, UTF-8, gzip; or Parquet (snappy)." },
  fileHeaderMapping: { key: "fileHeaderMapping", label: "File → column mapping", heading: "File-to-column mapping", placeholder: "Header row present; map \"cust_id\"→customer_id, \"dob\"→birth_date (DATE)." },
  targetTable: { key: "targetTable", label: "Target table(s)", heading: "Target table(s)", placeholder: "Load into analytics.customers; create if absent." },
  sourceQuery: { key: "sourceQuery", label: "Source query / extract", heading: "Source query / extract", placeholder: "SELECT * FROM sales.orders WHERE order_date >= '2024-01-01'; or: all tables in sales.*" },
  outputLayout:{ key: "outputLayout", label: "Output layout", heading: "Output layout", placeholder: "One file per table; partition by order_date; path s3://bucket/export/{table}/." },
};

/** Which fields each migration type shows, in display order. Unknown types fall
 * back to db_to_db. Mirrors the backend migration_types taxonomy. */
export const TYPE_FIELDS: Record<string, (keyof RequirementSpec)[]> = {
  db_to_db:    ["goal", "scope", "typeRules", "constraints", "data", "transforms", "objects", "conventions", "validation"],
  file_to_db:  ["goal", "fileFormat", "fileHeaderMapping", "scope", "typeRules", "targetTable", "data", "transforms", "validation"],
  db_to_file:  ["goal", "scope", "sourceQuery", "fileFormat", "outputLayout", "data", "validation"],
  schema_only: ["goal", "scope", "typeRules", "constraints", "objects", "conventions"],
  data_only:   ["goal", "scope", "sourceQuery", "data", "transforms", "targetTable", "validation"],
};

export function fieldsForType(migrationType: string | undefined): ReqFieldMeta[] {
  const keys = TYPE_FIELDS[migrationType ?? "db_to_db"] ?? TYPE_FIELDS.db_to_db;
  return keys.map((k) => FIELD_META[k]);
}

export function compileRequirement(migrationType: string, s: RequirementSpec): string {
  const keys = TYPE_FIELDS[migrationType] ?? TYPE_FIELDS.db_to_db;
  const out: string[] = [];
  for (const k of keys) {
    const v = (s[k] ?? "").trim();
    if (!v) continue;
    const m = FIELD_META[k];
    // goal is the H1 title; every other section is H2 — contract unchanged.
    out.push(k === "goal" ? `# ${m.heading}\n${v}\n` : `## ${m.heading}\n${v}\n`);
  }
  return out.join("\n").trim();
}

export interface StartWorkflowResult { workflow_id: string; run_id: string; status: string; mode: string; }

/** Start a BMAD workflow for a project requirement. Throws on 409 (project on
 * hold) / 404 (no requirement) with the backend detail message. */
export async function startProjectWorkflow(projectId: string, requirementId: string): Promise<StartWorkflowResult> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/agent-workflows`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirement_id: requirementId }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((d && d.detail) || `Start failed (${res.status})`);
  }
  return res.json() as Promise<StartWorkflowResult>;
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
