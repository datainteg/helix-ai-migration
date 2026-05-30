"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Play } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, StatusBadge, LoadingState } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import {
  getWorkflowDetail,
  subscribeToWorkflow,
  type WorkflowDetail,
  type WorkflowStep,
} from "@/lib/workflows/api";
import {
  listSources,
  listTargets,
  startMigration,
  approveMigration,
  rejectMigration,
  type Connection,
} from "@/lib/migrations/api";

// The four migration agents, in run order, with display labels.
const NODE_ORDER = ["schema_analyst", "type_mapper", "script_generator", "reconciler"] as const;
const AGENT_LABEL: Record<string, string> = {
  schema_analyst: "Schema Analyst",
  type_mapper: "Type Mapper",
  script_generator: "Script Generator",
  reconciler: "Reconciler",
};

const TERMINAL = ["completed", "approved", "rejected", "failed", "expired"];
const RUNNING_STATUSES = ["running", "started", "in_progress"];

/** Defensive read of a reconciler's verified percentage from parsed output. */
function verifiedPctOf(step: WorkflowStep | undefined): number | null {
  if (!step) return null;
  const parsed =
    (step.parsed_output as Record<string, unknown> | null) ??
    ((step as any).parsed_output_json as Record<string, unknown> | null) ??
    null;
  if (!parsed) return null;
  const raw = (parsed as any).verified_pct;
  const n = typeof raw === "string" ? Number(raw) : raw;
  return typeof n === "number" && !Number.isNaN(n) ? n : null;
}

export default function ProjectMigrationPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();

  // Connection config
  const [sources, setSources] = useState<Connection[] | null>(null);
  const [targets, setTargets] = useState<Connection[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");

  // Run state
  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WorkflowDetail | null>(null);
  const [starting, setStarting] = useState(false);
  const [actionPending, setActionPending] = useState(false);

  // 1. Load source + target connections on mount.
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([listSources(String(id)), listTargets(String(id))])
      .then(([src, tgt]) => {
        if (cancelled) return;
        setSources(src);
        setTargets(tgt);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setSources([]);
          setTargets([]);
          setError(e instanceof Error ? e.message : "Failed to load connections.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  // 3. Seed run detail when a workflow becomes active.
  useEffect(() => {
    if (!activeWorkflowId) return;
    let cancelled = false;
    getWorkflowDetail(token, activeWorkflowId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch(() => {
        /* stream may still seed steps; keep going */
      });
    return () => {
      cancelled = true;
    };
  }, [token, activeWorkflowId]);

  // 3/7. Live stream: append steps (dedupe by step_order, sort), stop at terminal.
  useEffect(() => {
    if (!activeWorkflowId) return;
    if (detail && TERMINAL.includes(detail.status)) return;
    let es: EventSource | null = null;
    let cancelled = false;
    subscribeToWorkflow(
      token,
      activeWorkflowId,
      (step: WorkflowStep) => {
        setDetail((prev) => {
          if (!prev || prev.workflow_id !== activeWorkflowId) return prev;
          const without = prev.steps.filter((s) => s.step_order !== step.step_order);
          return { ...prev, steps: [...without, step].sort((a, b) => a.step_order - b.step_order) };
        });
      },
      (terminal) => {
        setDetail((prev) => (prev ? { ...prev, status: terminal } : prev));
      },
    ).then((handle) => {
      if (cancelled) {
        handle?.close();
        return;
      }
      es = handle;
    });
    return () => {
      cancelled = true;
      es?.close();
    };
  }, [token, activeWorkflowId, detail?.status]);

  async function onGenerate() {
    if (!sourceId) return;
    setStarting(true);
    setError(null);
    try {
      const res = await startMigration(String(id), {
        source_connection_id: sourceId,
        target_connection_id: targetId || undefined,
      });
      setDetail(null);
      setActiveWorkflowId(res.workflow_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start migration.");
    } finally {
      setStarting(false);
    }
  }

  async function onApprove() {
    if (!activeWorkflowId) return;
    setActionPending(true);
    setError(null);
    try {
      await approveMigration(activeWorkflowId);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Approval failed.");
    } finally {
      setActionPending(false);
    }
  }

  async function onReject() {
    if (!activeWorkflowId) return;
    setActionPending(true);
    setError(null);
    try {
      await rejectMigration(activeWorkflowId);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Reject failed.");
    } finally {
      setActionPending(false);
    }
  }

  const steps = detail?.steps ?? [];
  const stepByAgent = new Map<string, WorkflowStep>();
  for (const s of steps) {
    if (!stepByAgent.has(s.agent_name)) stepByAgent.set(s.agent_name, s);
  }

  const noSources = (sources?.length ?? 0) === 0;
  const runInFlight = !!activeWorkflowId && !!detail && !TERMINAL.includes(detail.status);
  const isTerminal = !!detail && TERMINAL.includes(detail.status);

  // 4. Approval gate: explicit awaiting status, or "waiting + still early" heuristic.
  const status = detail?.status ?? "";
  const waitingByStatus =
    status === "awaiting_approval" || status === "awaiting" || status === "pending";
  const showGate =
    !!activeWorkflowId &&
    !isTerminal &&
    (status === "awaiting_approval" ||
      (waitingByStatus && steps.length < 3));

  // 6. Reconciliation result.
  const verifiedPct = verifiedPctOf(stepByAgent.get("reconciler"));

  // 5. Artifacts.
  const artifacts = steps.filter((s) => !!s.artifact_path);

  return (
    <ProjectShell
      projectId={String(id)}
      projectName="Untitled project"
      projectStatus={detail ? (detail.status as string) : "draft"}
      subtitle="Generate, review, and run an AI-assisted database migration."
    >
      {loading ? (
        <LoadingState label="Loading connections…" />
      ) : (
        <div className="grid grid-cols-12 gap-4">
          {/* Configure */}
          <Card className="col-span-12 lg:col-span-5" title="Configure">
            <div className="space-y-4">
              <div>
                <label className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">
                  Source connection
                </label>
                {noSources ? (
                  <p className="mt-1 text-[12.5px] text-ink-3">
                    No source connection —{" "}
                    <Link href="/connectors" className="text-helix-700 hover:underline">
                      add one in Connectors
                    </Link>
                    .
                  </p>
                ) : (
                  <select
                    value={sourceId}
                    onChange={(e) => setSourceId(e.target.value)}
                    disabled={runInFlight}
                    className="mt-1 w-full rounded-[8px] border border-hx-2 bg-surface px-3 py-2 text-[13px] text-ink-2 focus-ring disabled:opacity-50"
                  >
                    <option value="">Select a source…</option>
                    {sources!.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} · {c.connector_type}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div>
                <label className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">
                  Target connection <span className="text-ink-4 normal-case">(optional)</span>
                </label>
                <select
                  value={targetId}
                  onChange={(e) => setTargetId(e.target.value)}
                  disabled={runInFlight}
                  className="mt-1 w-full rounded-[8px] border border-hx-2 bg-surface px-3 py-2 text-[13px] text-ink-2 focus-ring disabled:opacity-50"
                >
                  <option value="">— none —</option>
                  {(targets ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} · {c.connector_type}
                    </option>
                  ))}
                </select>
              </div>

              <Button
                variant="primary"
                onClick={onGenerate}
                loading={starting}
                disabled={noSources || !sourceId || runInFlight || starting}
                className="w-full justify-center"
              >
                <Play className="h-4 w-4" /> Generate Migration
              </Button>

              {error && (
                <div className="rounded-[8px] border border-hx-2 bg-err-soft px-3 py-2 text-[12.5px] text-err">
                  {error}
                </div>
              )}
            </div>
          </Card>

          {/* Run */}
          <div className="col-span-12 lg:col-span-7 space-y-4">
            <Card
              title="Migration Run"
              actions={detail ? <StatusBadge status={detail.status} /> : undefined}
            >
              {!activeWorkflowId ? (
                <p className="text-[12.5px] text-ink-3">
                  No run yet. Choose a source connection and click Generate Migration.
                </p>
              ) : (
                <div className="space-y-2.5">
                  {NODE_ORDER.map((agent) => {
                    const step = stepByAgent.get(agent);
                    const running = step ? RUNNING_STATUSES.includes(step.status) : false;
                    return (
                      <div
                        key={agent}
                        className="flex items-center justify-between rounded-xl border border-hx bg-surface px-4 py-3 shadow-xs"
                      >
                        <div className="min-w-0">
                          <div className="text-[14px] font-semibold text-ink-2">
                            {AGENT_LABEL[agent]}
                          </div>
                          {running && (
                            <div className="mt-0.5 flex items-center gap-1.5 text-[11.5px] text-ink-3">
                              <svg
                                className="motion-safe:animate-spin h-3 w-3"
                                fill="none"
                                viewBox="0 0 24 24"
                                aria-hidden
                              >
                                <circle
                                  className="opacity-25"
                                  cx="12"
                                  cy="12"
                                  r="10"
                                  stroke="currentColor"
                                  strokeWidth="4"
                                />
                                <path
                                  className="opacity-75"
                                  fill="currentColor"
                                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                                />
                              </svg>
                              running…
                            </div>
                          )}
                          {step?.error_message && (
                            <div className="mt-0.5 text-[11.5px] text-err">{step.error_message}</div>
                          )}
                        </div>
                        <StatusBadge status={step?.status ?? "pending"} />
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>

            {/* 4. Approval gate */}
            {showGate && (
              <Card title="Human Approval">
                <p className="text-[12.5px] text-ink-3">
                  Review the generated migration plan before the script runs.
                </p>
                <div className="mt-3 flex gap-2">
                  <Button
                    variant="primary"
                    onClick={onApprove}
                    loading={actionPending}
                    disabled={actionPending}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="danger"
                    onClick={onReject}
                    loading={actionPending}
                    disabled={actionPending}
                  >
                    Reject
                  </Button>
                </div>
              </Card>
            )}

            {/* 6. Reconciliation result */}
            {verifiedPct !== null && (
              <Card title="Reconciliation">
                <div className="flex items-baseline gap-2">
                  <span className="text-[28px] font-semibold text-ink">
                    Verified: {verifiedPct}%
                  </span>
                </div>
              </Card>
            )}

            {/* 5. Artifacts */}
            {activeWorkflowId && (
              <Card title="Output Artifacts">
                {artifacts.length > 0 ? (
                  <ul className="space-y-1.5 text-[12.5px]">
                    {artifacts.map((s, i) => (
                      <li
                        key={`art-${i}`}
                        className="flex items-center justify-between gap-2 text-ink-2 min-w-0"
                      >
                        <span className="text-ink-3">
                          {AGENT_LABEL[s.agent_name] ?? s.agent_name.replace(/_/g, " ")}
                        </span>
                        <span className="truncate font-mono text-[11.5px]">
                          {s.artifact_path?.split(/[\\/]/).pop()}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[12.5px] text-ink-3">No artifacts yet.</p>
                )}
              </Card>
            )}

            {/* 7. Terminal banner */}
            {isTerminal && detail && (
              <Card title="Result">
                <div className="flex items-center gap-2 text-[13px] text-ink-2">
                  <StatusBadge status={detail.status} />
                  <span>
                    {detail.status === "completed" || detail.status === "approved"
                      ? "Migration run finished."
                      : detail.status === "rejected"
                      ? "Migration was rejected."
                      : detail.status === "expired"
                      ? "Migration run expired."
                      : "Migration run failed."}
                  </span>
                </div>
              </Card>
            )}
          </div>
        </div>
      )}
    </ProjectShell>
  );
}
