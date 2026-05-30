"use client";

/**
 * /approval — Human-approval queue.
 *
 * Lists every agent-workflow currently parked at a human-approval gate
 * (status === "awaiting_approval", per the backend's _PENDING bucket in
 * api/dashboard.py) via GET /api/v1/agent-workflows. Approve / Reject post
 * to the real signal-approve / signal-reject endpoints. When nothing is
 * pending it renders a clean empty state — no sample/mock data is shown.
 */

import { useCallback, useEffect, useState } from "react";
import { Check, X, Inbox } from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import {
  listOrgWorkflowRuns,
  type WorkflowRun,
} from "@/lib/workflows/api";
import { approveMigration, rejectMigration } from "@/lib/migrations/api";

import { AppShell } from "@/components/layout";
import {
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  StatusBadge,
} from "@/components/ui";

// Status value used by the backend for a workflow parked at a human gate
// (see app/api/dashboard.py → _PENDING).
const AWAITING_APPROVAL = "awaiting_approval";

export default function ApprovalPage() {
  const { token } = useAuth();
  const [pending, setPending] = useState<WorkflowRun[] | null>(null);
  const [loadError, setLoadError] = useState<string>("");
  const [acting, setActing] = useState<Record<string, "approve" | "reject">>({});

  const load = useCallback(() => {
    if (!token) return;
    let cancelled = false;
    listOrgWorkflowRuns(token, 200)
      .then((runs) => {
        if (cancelled) return;
        setPending(runs.filter((r) => r.status === AWAITING_APPROVAL));
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setPending(null);
        setLoadError(
          (e instanceof Error ? e.message : null) ?? "Failed to load approvals",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => load(), [load]);

  async function decide(run: WorkflowRun, action: "approve" | "reject") {
    setActing((s) => ({ ...s, [run.workflow_id]: action }));
    try {
      if (action === "approve") await approveMigration(run.workflow_id);
      else await rejectMigration(run.workflow_id);
      // Drop the resolved item from the queue.
      setPending((cur) =>
        (cur ?? []).filter((r) => r.workflow_id !== run.workflow_id),
      );
    } catch (e: unknown) {
      setLoadError(
        (e instanceof Error ? e.message : null) ?? `Failed to ${action} workflow`,
      );
    } finally {
      setActing((s) => {
        const next = { ...s };
        delete next[run.workflow_id];
        return next;
      });
    }
  }

  const fmtDate = (iso: string | null) =>
    iso ? new Date(iso).toLocaleString() : "—";

  return (
    <AppShell
      eyebrow="HUMAN APPROVAL GATES"
      title="Pending approvals"
      metric={pending ? `${pending.length} pending` : undefined}
      description="Agent workflows parked at a human-approval gate. Approve to resume the pipeline or reject to halt it."
      crumbs={["Approvals"]}
    >
      <div className="flex flex-col gap-4">
        {loadError && (
          <ErrorBanner message={loadError} onDismiss={() => setLoadError("")} />
        )}

        <Card padding="md" bodyClassName="p-0">
          {pending === null && !loadError ? (
            <div className="text-ink-3 text-[12.5px]" style={{ padding: 18 }}>
              Loading approvals…
            </div>
          ) : !pending || pending.length === 0 ? (
            <EmptyState
              icon={<Inbox className="h-4 w-4" />}
              title="No pending approvals."
              description="When an agent workflow reaches a human-approval gate it will appear here for review."
            />
          ) : (
            <div className="flex flex-col">
              {pending.map((run, i) => {
                const busy = acting[run.workflow_id];
                return (
                  <div
                    key={run.workflow_id}
                    className="flex items-center justify-between"
                    style={{
                      gap: 12,
                      padding: "14px 18px",
                      borderTop: i === 0 ? "none" : "1px solid var(--con-line)",
                    }}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center" style={{ gap: 8 }}>
                        <span
                          className="font-mono text-ink"
                          style={{ fontSize: 12.5, fontWeight: 500 }}
                        >
                          {run.workflow_id}
                        </span>
                        <StatusBadge status={run.status} />
                      </div>
                      <div
                        className="font-mono text-ink-3"
                        style={{ fontSize: 10.5, marginTop: 4 }}
                      >
                        {run.project_id ? `Project ${run.project_id}` : "—"}
                        {run.mode ? ` · ${run.mode}` : ""}
                        {" · "}
                        {fmtDate(run.created_at)}
                      </div>
                    </div>
                    <div className="flex flex-shrink-0" style={{ gap: 6 }}>
                      <Button
                        variant="outline"
                        size="sm"
                        loading={busy === "reject"}
                        disabled={!!busy}
                        onClick={() => decide(run, "reject")}
                      >
                        <X size={11} /> Reject
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        loading={busy === "approve"}
                        disabled={!!busy}
                        onClick={() => decide(run, "approve")}
                      >
                        <Check size={11} /> Approve
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
