"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Play, ExternalLink } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, StatusBadge, Avatar, Chip, EmptyState, LoadingState, Modal, ErrorBanner } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import {
  listProjectWorkflowRuns,
  getWorkflowDetail,
  subscribeToWorkflow,
  listProjectRequirements,
  startProjectWorkflow,
  createProjectRequirement,
  compileRequirement,
  fieldsForType,
  requestWorkflowRun,
  listRunRequests,
  approveRunRequest,
  rejectRunRequest,
  EMPTY_SPEC,
  type WorkflowRun,
  type WorkflowDetail,
  type WorkflowStep,
  type ProjectRequirement,
  type RequirementSpec,
  type RunRequest,
} from "@/lib/workflows/api";
import { approveMigration, rejectMigration } from "@/lib/migrations/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const AGENT_PHASE: Record<string, { label: string; color: "indigo" | "violet" | "cyan" | "amber" | "green" | "default" }> = {
  project_context: { label: "Setup", color: "default" },
  analyst:          { label: "Analysis", color: "indigo" },
  pm:               { label: "Planning", color: "indigo" },
  ux_designer:      { label: "Planning", color: "indigo" },
  architect:        { label: "Design", color: "violet" },
  architect_stories:{ label: "Design", color: "violet" },
  architect_readiness:{ label: "Design", color: "violet" },
  approval_gate:    { label: "Gate", color: "amber" },
  dev_story:        { label: "Build", color: "cyan" },
  dev:              { label: "Build", color: "cyan" },
  qa:               { label: "Validate", color: "green" },
  code_review:      { label: "Validate", color: "green" },
  tech_writer:      { label: "Docs", color: "default" },
};

export default function ProjectAgentsPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const { token, can } = useAuth();
  const canWrite = can("project:write");
  const [runs, setRuns] = useState<WorkflowRun[] | null>(null);
  const [active, setActive] = useState<WorkflowDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [projectName, setProjectName] = useState("Loading…");
  const [migType, setMigType] = useState("db_to_db");
  const [onHold, setOnHold] = useState(false);
  const [requireApproval, setRequireApproval] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [runModal, setRunModal] = useState(false);
  const [approvalBusy, setApprovalBusy] = useState<"" | "approve" | "reject">("");

  const awaitingApproval = active?.status === "awaiting_approval";
  const decide = async (kind: "approve" | "reject") => {
    if (!active) return;
    setApprovalBusy(kind);
    try {
      await (kind === "approve" ? approveMigration(active.workflow_id) : rejectMigration(active.workflow_id));
      setReloadKey((k) => k + 1);
    } catch {
      // surfaced via the run status not changing; keep the panel responsive
    } finally {
      setApprovalBusy("");
    }
  };

  useRegisterCrumbLabel(String(id), projectName !== "Loading…" ? projectName : undefined);

  // The persistent "Start Workflow" CTA (ProjectShell) links here with ?run=new
  // to open the Run modal directly. Honour it once the page mounts.
  useEffect(() => {
    if (canWrite && !onHold && searchParams.get("run") === "new") setRunModal(true);
  }, [searchParams, canWrite, onHold]);

  // Real project name for the ProjectShell header + breadcrumb.
  useEffect(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/v1/projects/${id}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => { setProjectName(p?.name || "Project"); if (p?.migration_type) setMigType(p.migration_type); setOnHold(!!p?.on_hold); setRequireApproval(p?.require_run_approval ?? true); })
      .catch(() => setProjectName("Project"));
  }, [id]);

  useEffect(() => {
    // SC-010: auth via the HttpOnly cookie; gate on id only.
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    listProjectWorkflowRuns(token, String(id), 20)
      .then(async (rows) => {
        if (cancelled) return;
        setRuns(rows);
        if (rows.length > 0) {
          try {
            const detail = await getWorkflowDetail(token, rows[0].workflow_id);
            if (!cancelled) setActive(detail);
          } catch {
            if (!cancelled) setActive(null);
          }
        }
      })
      .catch(() => { if (!cancelled) setRuns([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token, id, reloadKey]);

  // Live SSE — append-on-step. Only subscribes when the active run is not yet
  // terminal so we don't reopen connections to completed workflows.
  useEffect(() => {
    if (!active) return;
    if (["completed", "approved", "rejected", "failed", "expired"].includes(active.status)) return;
    let es: EventSource | null = null;
    let cancelled = false;
    subscribeToWorkflow(
      token,
      active.workflow_id,
      (step: WorkflowStep) => {
        setActive((prev) => {
          if (!prev || prev.workflow_id !== active.workflow_id) return prev;
          const without = prev.steps.filter((s) => s.step_order !== step.step_order);
          return { ...prev, steps: [...without, step].sort((a, b) => a.step_order - b.step_order) };
        });
      },
      (terminal) => {
        setActive((prev) => prev ? { ...prev, status: terminal } : prev);
      },
    ).then((handle) => {
      if (cancelled) { handle?.close(); return; }
      es = handle;
    });
    return () => {
      cancelled = true;
      es?.close();
    };
  }, [token, active?.workflow_id, active?.status]);

  const flow = active && active.steps.length > 0
    ? active.steps.map((s, idx) => {
        const meta = AGENT_PHASE[s.agent_name] ?? { label: "Step", color: "default" as const };
        return {
          id: `step-${idx}`,
          label: s.agent_name.replace(/_/g, " "),
          phase: meta.label,
          color: meta.color,
          status: s.status,
        };
      })
    : [];
  const hasRuns = (runs?.length ?? 0) > 0;

  return (
    <ProjectShell
      projectId={String(id)}
      projectName={projectName}
      projectStatus={active ? (active.status as any) : "draft"}
      onHold={onHold}
      subtitle="This project's workflow runs — live agent pipeline, execution log, and artifacts."
      actions={
        active ? (
          <Link href={`/agents?run=${encodeURIComponent(active.workflow_id)}`}>
            <Button variant="outline"><ExternalLink className="h-4 w-4" /> View in Agents</Button>
          </Link>
        ) : undefined
      }
    >
      {runModal && (
        <RunWorkflowModal
          projectId={String(id)}
          migType={migType}
          requireApproval={requireApproval}
          onClose={() => setRunModal(false)}
          onStarted={() => { setRunModal(false); setReloadKey((k) => k + 1); }}
        />
      )}
      {loading ? (
        <LoadingState label="Loading workflow runs…" />
      ) : (
        <>
          <div className="grid grid-cols-12 gap-4">
            <Card className="col-span-12 lg:col-span-8" title="Workflow Canvas">
              {flow.length > 0 ? (
                <div className="space-y-3">
                  {flow.map((n) => (
                    <div key={n.id} className="flex items-center gap-3">
                      <FlowNode {...n} />
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No agent runs yet"
                  description={hasRuns
                    ? "This workflow has no recorded steps yet."
                    : "Run a workflow to see per-agent execution state here."}
                />
              )}
            </Card>
            <div className="col-span-12 lg:col-span-4 space-y-4">
              <Card title="Workflow Details">
                <dl className="space-y-3 text-[13px]">
                  <div>
                    <dt className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">Mode</dt>
                    <dd className="mt-0.5 text-ink-2">{active?.mode ?? "BMAD · Auto with gates"}</dd>
                  </div>
                  <div>
                    <dt className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">Status</dt>
                    <dd className="mt-0.5"><StatusBadge status={active?.status ?? "draft"} /></dd>
                  </div>
                  <div>
                    <dt className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">Workflow ID</dt>
                    <dd className="mt-0.5 font-mono text-[11.5px] text-ink-3">{active?.workflow_id ?? "—"}</dd>
                  </div>
                </dl>
              </Card>
              <Card title="Human Approval">
                {awaitingApproval ? (
                  <>
                    <p className="text-[12.5px] text-ink-3">This run is paused for review. Approve to proceed to the execution agents, or reject to stop it.</p>
                    {canWrite ? (
                      <div className="mt-3 flex flex-col gap-2">
                        <Button className="w-full justify-center" loading={approvalBusy === "approve"} disabled={approvalBusy !== ""} onClick={() => decide("approve")}>Approve</Button>
                        <Button variant="danger" className="w-full justify-center" loading={approvalBusy === "reject"} disabled={approvalBusy !== ""} onClick={() => decide("reject")}>Reject</Button>
                      </div>
                    ) : (
                      <p className="mt-2 text-[12px] text-ink-4">You don&apos;t have permission to approve runs.</p>
                    )}
                  </>
                ) : (
                  <p className="text-[12.5px] text-ink-3">
                    No approval pending. The pipeline pauses here for human review after the mapping step — approve / reject controls appear when a run is awaiting sign-off.
                  </p>
                )}
              </Card>
              <RunRequestsPanel
                projectId={String(id)}
                reloadKey={reloadKey}
                canApprove={can("agent:approve")}
                onActioned={() => setReloadKey((k) => k + 1)}
              />
              <Card title="Output Artifacts">
                {active && active.steps.some((s) => s.artifact_path) ? (
                  <ul className="space-y-1.5 text-[12.5px]">
                    {active.steps.filter((s) => s.artifact_path).map((s, i) => (
                      <li key={`art-${i}`} className="flex justify-between text-ink-2 gap-2 min-w-0">
                        <span className="truncate font-mono text-[11.5px]">{s.artifact_path?.split(/[\\/]/).pop()}</span>
                        <Chip tone="indigo">{s.agent_name.replace(/_/g, " ")}</Chip>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[12.5px] text-ink-3">No artifacts yet.</p>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </ProjectShell>
  );
}

function RunRequestsPanel({ projectId, reloadKey, canApprove, onActioned }: {
  projectId: string;
  reloadKey: number;
  canApprove: boolean;
  onActioned: () => void;
}) {
  const [requests, setRequests] = useState<RunRequest[] | null>(null);
  const [err, setErr] = useState("");
  const [busyId, setBusyId] = useState("");

  useEffect(() => {
    let cancelled = false;
    listRunRequests(projectId)
      .then((rows) => { if (!cancelled) setRequests(rows); })
      .catch((e: unknown) => { if (!cancelled) { setRequests([]); setErr(e instanceof Error ? e.message : "Failed to load run requests"); } });
    return () => { cancelled = true; };
  }, [projectId, reloadKey]);

  const act = async (kind: "approve" | "reject", req: RunRequest) => {
    setErr(""); setBusyId(req.id);
    try {
      if (kind === "approve") {
        await approveRunRequest(req.id);
      } else {
        const notes = window.prompt("Reason for rejecting (optional):") ?? undefined;
        await rejectRunRequest(req.id, notes);
      }
      onActioned();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : `Failed to ${kind} request`);
    } finally {
      setBusyId("");
    }
  };

  return (
    <Card title="Run requests">
      {err && <div className="mb-3"><ErrorBanner message={err} onDismiss={() => setErr("")} /></div>}
      {requests === null ? (
        <p className="text-[12.5px] text-ink-3">Loading…</p>
      ) : requests.length === 0 ? (
        <p className="text-[12.5px] text-ink-3">No run requests</p>
      ) : (
        <ul className="space-y-2.5">
          {requests.map((req) => {
            const pending = req.status === "pending";
            return (
              <li key={req.id} className="rounded-[8px] border border-hx bg-surface px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <StatusBadge status={req.status} />
                  <span className="font-mono text-[11px] text-ink-4">{req.created_at ? new Date(req.created_at).toLocaleString() : "—"}</span>
                </div>
                <div className="mt-1.5 text-[11.5px] text-ink-3">
                  Requirement <span className="font-mono text-ink-2">{req.requirement_id.slice(0, 8)}</span>
                </div>
                {req.notes && <p className="mt-1 text-[11.5px] text-ink-3">Notes: {req.notes}</p>}
                {pending && canApprove && (
                  <div className="mt-2 flex gap-2">
                    <Button className="justify-center" loading={busyId === req.id} disabled={busyId !== ""} onClick={() => act("approve", req)}>Approve</Button>
                    <Button variant="danger" className="justify-center" loading={busyId === req.id} disabled={busyId !== ""} onClick={() => act("reject", req)}>Reject</Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function FlowNode({ label, phase, color, status }: { label: string; phase: string; color: "indigo" | "violet" | "cyan" | "amber" | "green" | "default"; status: string }) {
  const palette: Record<typeof color, string> = {
    indigo: "bg-helix-50 text-helix-800 border-helix-200",
    violet: "bg-violet-50 text-violet-800 border-violet-200",
    cyan: "bg-cyan-50 text-cyan-800 border-cyan-200",
    amber: "bg-amber-50 text-amber-800 border-amber-200",
    green: "bg-emerald-50 text-emerald-800 border-emerald-200",
    default: "bg-zinc-50 text-ink-2 border-hx",
  };
  return (
    <div className={`rounded-xl border px-4 py-3 shadow-xs w-full flex items-center justify-between ${palette[color]}`}>
      <div>
        <div className="text-[11px] uppercase tracking-wider opacity-70 font-medium">{phase}</div>
        <div className="text-[14px] font-semibold">{label}</div>
      </div>
      <StatusBadge status={status} />
    </div>
  );
}

function RunWorkflowModal({ projectId, migType, requireApproval, onClose, onStarted }: {
  projectId: string;
  migType: string;
  requireApproval: boolean;
  onClose: () => void;
  onStarted: () => void;
}) {
  const [reqs, setReqs] = useState<ProjectRequirement[] | null>(null);
  const [mode, setMode] = useState<"existing" | "build">("existing");
  const [picked, setPicked] = useState<string>("");
  const [spec, setSpec] = useState<RequirementSpec>(EMPTY_SPEC);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    listProjectRequirements(projectId)
      .then((rs) => { setReqs(rs); if (rs.length) { setPicked(rs[0].id); setMode("existing"); } else { setMode("build"); } })
      .catch(() => { setReqs([]); setMode("build"); });
  }, [projectId]);

  const run = async () => {
    setStarting(true); setErr(""); setOk("");
    try {
      let requirementId = picked;
      if (mode === "build") {
        const text = compileRequirement(migType, spec);
        if (!text || !spec.goal.trim()) { setErr("Describe at least the migration goal."); setStarting(false); return; }
        const created = await createProjectRequirement(projectId, text);
        requirementId = created.id;
      }
      if (!requirementId) { setErr("Select or build a requirement."); setStarting(false); return; }
      if (requireApproval) {
        // Approval gate: file a pending request instead of starting directly.
        await requestWorkflowRun(projectId, requirementId);
        setOk("Run requested — pending manager approval");
        // Brief beat so the user sees the confirmation before close + reload.
        setTimeout(() => onStarted(), 1200);
      } else {
        await startProjectWorkflow(projectId, requirementId);
        onStarted();
      }
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to start workflow");  // surfaces on-hold 409, etc.
    } finally {
      setStarting(false);
    }
  };

  const ta = "px-2.5 py-2 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring resize-y w-full";
  const specFields = fieldsForType(migType);

  return (
    <Modal open onClose={onClose} title="Run migration workflow" width="lg">
      <div className="space-y-4">
        {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
        {ok && (
          <div className="rounded-[8px] border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12.5px] text-emerald-800">
            {ok}
          </div>
        )}
        <p className="text-[12.5px] text-ink-3">
          The pipeline introspects the source, maps types, generates scripts, and reconciles — streaming
          live here. Give it good detail: real migrations span many schemas, tables, types, and rules.
        </p>

        <div className="flex gap-2">
          <button type="button" onClick={() => setMode("existing")} disabled={!reqs?.length}
            className={`px-3 h-8 rounded-md text-[12.5px] border ${mode === "existing" ? "border-[var(--con-brand)] bg-[var(--con-brand-soft)] text-[var(--con-brand)]" : "border-hx-2 bg-surface text-ink-3"} disabled:opacity-50`}>
            Use existing requirement
          </button>
          <button type="button" onClick={() => setMode("build")}
            className={`px-3 h-8 rounded-md text-[12.5px] border ${mode === "build" ? "border-[var(--con-brand)] bg-[var(--con-brand-soft)] text-[var(--con-brand)]" : "border-hx-2 bg-surface text-ink-3"}`}>
            Build a new requirement
          </button>
        </div>

        {mode === "existing" ? (
          reqs?.length ? (
            <label className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Requirement</span>
              <select value={picked} onChange={(e) => setPicked(e.target.value)} className="h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring">
                {reqs.map((r) => <option key={r.id} value={r.id}>{r.source_text.slice(0, 90)}{r.source_text.length > 90 ? "…" : ""} (v{r.version})</option>)}
              </select>
            </label>
          ) : <p className="text-[12.5px] text-ink-4">No saved requirements — build one →</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[46vh] overflow-y-auto pr-1">
            {specFields.map((f) => (
              <label key={f.key} className={`flex flex-col gap-1.5 ${f.full ? "sm:col-span-2" : ""}`}>
                <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">{f.label}</span>
                <textarea rows={2} value={spec[f.key]} onChange={(e) => setSpec((s) => ({ ...s, [f.key]: e.target.value }))} placeholder={f.placeholder} className={ta} />
              </label>
            ))}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={run} loading={starting} disabled={!!ok}><Play className="h-3.5 w-3.5" /> {requireApproval ? "Request run" : (mode === "build" ? "Create & run" : "Start run")}</Button>
        </div>
      </div>
    </Modal>
  );
}
