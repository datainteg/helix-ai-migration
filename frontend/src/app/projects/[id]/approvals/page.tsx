"use client";

/**
 * /projects/[id]/approvals — the approval queue for a project.
 *
 * Two human gates live here:
 *  1) Pre-start run requests — a manager approves/rejects BEFORE a workflow
 *     ever starts (listRunRequests → approveRunRequest / rejectRunRequest).
 *  2) Mid-run approvals — a workflow that paused at `awaiting_approval` needs a
 *     signal to continue or stop (approveMigration / rejectMigration).
 *
 * Both write paths are gated on can("agent:approve"). REAL DATA ONLY — honest
 * EmptyState per section when there's nothing to act on.
 */

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, XCircle, Inbox, PlayCircle, GitPullRequestArrow } from "lucide-react";

import { ProjectShell } from "@/components/layout/ProjectShell";
import { Button, Card, Chip, StatusBadge, EmptyState, ErrorBanner, LoadingState } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import {
  listRunRequests, approveRunRequest, rejectRunRequest,
  listProjectWorkflowRuns, type RunRequest, type WorkflowRun,
} from "@/lib/workflows/api";
import { approveMigration, rejectMigration } from "@/lib/migrations/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

function fmtWhen(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}

function shortId(id: string | null): string {
  return id ? id.slice(0, 8) : "—";
}

export default function ProjectApprovalsPage() {
  const { id } = useParams<{ id: string }>();
  const { token, can } = useAuth();
  const canApprove = can("agent:approve");

  const [projectName, setProjectName] = useState("Project");
  const [projectStatus, setProjectStatus] = useState("draft");
  const [onHold, setOnHold] = useState(false);

  const [requests, setRequests] = useState<RunRequest[] | null>(null);
  const [runs, setRuns] = useState<WorkflowRun[] | null>(null);
  const [reqErr, setReqErr] = useState("");
  const [runErr, setRunErr] = useState("");
  const [busyId, setBusyId] = useState("");

  useRegisterCrumbLabel(String(id), projectName !== "Project" ? projectName : undefined);

  // Real project header for the shell + breadcrumb.
  useEffect(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/v1/projects/${id}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => {
        setProjectName(p?.name || "Project");
        if (p?.status) setProjectStatus(p.status);
        setOnHold(!!p?.on_hold);
      })
      .catch(() => setProjectName("Project"));
  }, [id]);

  const loadRequests = useCallback(() => {
    if (!id) return;
    setReqErr("");
    listRunRequests(String(id))
      .then((rs) => setRequests(rs ?? []))
      .catch((e: unknown) => { setRequests([]); setReqErr(e instanceof Error ? e.message : "Failed to load run requests"); });
  }, [id]);

  const loadRuns = useCallback(() => {
    if (!id) return;
    setRunErr("");
    listProjectWorkflowRuns(token, String(id))
      .then((rs) => setRuns(rs ?? []))
      .catch((e: unknown) => { setRuns([]); setRunErr(e instanceof Error ? e.message : "Failed to load workflow runs"); });
  }, [id, token]);

  useEffect(() => { loadRequests(); }, [loadRequests]);
  useEffect(() => { loadRuns(); }, [loadRuns]);

  // --- Pre-start run-request actions ---
  const onApproveRequest = async (r: RunRequest) => {
    setBusyId(r.id); setReqErr("");
    try { await approveRunRequest(r.id); loadRequests(); loadRuns(); }
    catch (e: unknown) { setReqErr(e instanceof Error ? e.message : "Approve failed"); }
    finally { setBusyId(""); }
  };
  const onRejectRequest = async (r: RunRequest) => {
    const notes = window.prompt("Reason for rejecting this run request (optional):") ?? undefined;
    setBusyId(r.id); setReqErr("");
    try { await rejectRunRequest(r.id, notes); loadRequests(); }
    catch (e: unknown) { setReqErr(e instanceof Error ? e.message : "Reject failed"); }
    finally { setBusyId(""); }
  };

  // --- Mid-run signal actions ---
  const onApproveRun = async (run: WorkflowRun) => {
    setBusyId(run.workflow_id); setRunErr("");
    try { await approveMigration(run.workflow_id); loadRuns(); }
    catch (e: unknown) { setRunErr(e instanceof Error ? e.message : "Approve failed"); }
    finally { setBusyId(""); }
  };
  const onRejectRun = async (run: WorkflowRun) => {
    const notes = window.prompt("Reason for rejecting this run (optional):") ?? "";
    setBusyId(run.workflow_id); setRunErr("");
    try { await rejectMigration(run.workflow_id, notes); loadRuns(); }
    catch (e: unknown) { setRunErr(e instanceof Error ? e.message : "Reject failed"); }
    finally { setBusyId(""); }
  };

  const pendingRequests = (requests ?? []).filter((r) => r.status.toLowerCase() === "pending");
  const historyRequests = (requests ?? []).filter((r) => r.status.toLowerCase() !== "pending");
  const awaitingRuns = (runs ?? []).filter((r) => r.status.toLowerCase() === "awaiting_approval");

  return (
    <ProjectShell
      projectId={String(id)}
      projectName={projectName}
      projectStatus={projectStatus as any}
      onHold={onHold}
      subtitle="Human gates: approve run requests before they start, and signal workflows paused mid-run."
    >
      <div className="flex flex-col gap-4">
        {/* 1) Pre-start run requests */}
        <Card
          title={<span className="flex items-center gap-2"><GitPullRequestArrow className="h-4 w-4 text-[var(--con-brand)]" /> Pre-start run requests</span>}
          description="Requests to start a workflow. A manager approves (which starts it) or rejects with notes."
        >
          {reqErr && <div className="mb-3"><ErrorBanner message={reqErr} onDismiss={() => setReqErr("")} /></div>}
          {requests === null ? (
            <LoadingState label="Loading run requests…" />
          ) : pendingRequests.length === 0 && historyRequests.length === 0 ? (
            <EmptyState
              icon={<Inbox className="h-4 w-4" />}
              title="No run requests"
              description="When someone requests a workflow run for this project, it appears here for approval."
            />
          ) : (
            <div className="flex flex-col gap-4">
              {pendingRequests.length > 0 && (
                <div className="flex flex-col gap-3">
                  {pendingRequests.map((r) => (
                    <div key={r.id} className="rounded-[10px] border border-hx p-3">
                      <div className="flex items-center gap-2.5">
                        <div className="flex-1 min-w-0">
                          <div className="text-[13px] font-medium text-ink truncate">
                            Requirement <span className="font-mono text-[12px] text-ink-2">{shortId(r.requirement_id)}</span>
                          </div>
                          <div className="text-[11px] text-ink-4 font-mono">
                            req {shortId(r.id)} · by {shortId(r.requested_by)} · {fmtWhen(r.created_at)}
                          </div>
                        </div>
                        <StatusBadge status={r.status} />
                      </div>
                      {canApprove ? (
                        <div className="mt-2.5 flex gap-2">
                          <Button size="sm" loading={busyId === r.id} onClick={() => onApproveRequest(r)}>
                            <CheckCircle2 className="h-3.5 w-3.5" /> Approve
                          </Button>
                          <Button size="sm" variant="outline" loading={busyId === r.id} onClick={() => onRejectRequest(r)}>
                            <XCircle className="h-3.5 w-3.5" /> Reject
                          </Button>
                        </div>
                      ) : (
                        <p className="mt-2 text-[11.5px] text-ink-4">You don&apos;t have permission to approve run requests.</p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {historyRequests.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider font-mono text-ink-4 mb-2">History</div>
                  <div className="flex flex-col gap-2">
                    {historyRequests.map((r) => (
                      <div key={r.id} className="rounded-[10px] border border-hx p-3">
                        <div className="flex items-center gap-2.5">
                          <div className="flex-1 min-w-0">
                            <div className="text-[12.5px] text-ink-2 truncate">
                              Requirement <span className="font-mono text-[12px]">{shortId(r.requirement_id)}</span>
                            </div>
                            <div className="text-[11px] text-ink-4 font-mono">
                              req {shortId(r.id)} · by {shortId(r.requested_by)} · {fmtWhen(r.created_at)}
                              {r.workflow_id ? <> · wf {shortId(r.workflow_id)}</> : null}
                            </div>
                          </div>
                          <StatusBadge status={r.status} />
                        </div>
                        {r.notes && (
                          <div className="mt-2 text-[12px] text-ink-3 border-l-2 border-hx pl-2.5">{r.notes}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* 2) Mid-run approvals */}
        <Card
          title={<span className="flex items-center gap-2"><PlayCircle className="h-4 w-4 text-[var(--con-brand)]" /> Mid-run approvals</span>}
          description="Workflows paused at a human gate, waiting for an approve/reject signal to continue."
        >
          {runErr && <div className="mb-3"><ErrorBanner message={runErr} onDismiss={() => setRunErr("")} /></div>}
          {runs === null ? (
            <LoadingState label="Loading workflow runs…" />
          ) : awaitingRuns.length === 0 ? (
            <EmptyState
              icon={<Inbox className="h-4 w-4" />}
              title="Nothing awaiting approval"
              description="No workflow on this project is currently paused waiting for a decision."
            />
          ) : (
            <div className="flex flex-col gap-3">
              {awaitingRuns.map((run) => (
                <div key={run.workflow_id} className="rounded-[10px] border border-hx p-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex-1 min-w-0">
                      <div className="text-[13px] font-medium text-ink truncate">
                        Workflow <span className="font-mono text-[12px] text-ink-2">{shortId(run.workflow_id)}</span>
                      </div>
                      <div className="text-[11px] text-ink-4 font-mono">
                        {run.mode ? <>{run.mode} · </> : null}
                        {run.requirement_id ? <>req {shortId(run.requirement_id)} · </> : null}
                        {fmtWhen(run.created_at)}
                      </div>
                    </div>
                    <StatusBadge status={run.status} />
                  </div>
                  {canApprove ? (
                    <div className="mt-2.5 flex gap-2">
                      <Button size="sm" loading={busyId === run.workflow_id} onClick={() => onApproveRun(run)}>
                        <CheckCircle2 className="h-3.5 w-3.5" /> Approve
                      </Button>
                      <Button size="sm" variant="outline" loading={busyId === run.workflow_id} onClick={() => onRejectRun(run)}>
                        <XCircle className="h-3.5 w-3.5" /> Reject
                      </Button>
                    </div>
                  ) : (
                    <p className="mt-2 text-[11.5px] text-ink-4">You don&apos;t have permission to signal this workflow.</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </ProjectShell>
  );
}
