"use client";

/**
 * /projects/[id]/sprints — Sprint Dashboard.
 *
 * Landing page for sprint management. Surfaces sprint-level KPIs (top metric
 * strip), the active sprint (progress + health + burndown + velocity), every
 * sprint as a card, and the urgent footer (approvals + risks).
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Download, Plus, X } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, EmptyState, LoadingState, MetricCell } from "@/components/ui";
import { useFocusTrap } from "@/lib/use-focus-trap";
import {
  SprintCard,
  SprintProgressCard,
  SprintHealthCard,
  SprintBurndownChart,
  SprintVelocityChart,
  SprintApprovalCard,
  SprintRiskCard,
} from "@/components/sprints";
import { useAuth } from "@/lib/auth-context";
import {
  createSprint,
  fetchSprints,
  fetchActiveSprint,
  fetchVelocity,
  fetchApprovals,
  fetchRisks,
  fetchBurndown,
  seedSprints,
  type BurndownPoint,
  type NewSprintInput,
  type Sprint,
  type SprintApproval,
  type SprintRisk,
  type VelocityPoint,
} from "@/lib/sprints";

export default function SprintDashboardPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params?.id ?? "");
  const { token } = useAuth();

  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [active, setActive] = useState<Sprint | null>(null);
  const [velocity, setVelocity] = useState<VelocityPoint[]>([]);
  const [approvals, setApprovals] = useState<SprintApproval[]>([]);
  const [risks, setRisks] = useState<SprintRisk[]>([]);
  const [burndown, setBurndown] = useState<BurndownPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [showNewSprint, setShowNewSprint] = useState(false);

  const refetchSprints = useCallback(() => {
    if (!token || !projectId) return;
    Promise.all([
      fetchSprints(token, projectId),
      fetchActiveSprint(token, projectId),
      fetchVelocity(token, projectId),
    ])
      .then(([list, act, vel]) => {
        setSprints(list);
        setActive(act);
        setVelocity(vel);
      })
      .catch(() => {});
  }, [token, projectId]);

  useEffect(() => {
    if (!token || !projectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([
      fetchSprints(token, projectId),
      fetchActiveSprint(token, projectId),
      fetchVelocity(token, projectId),
    ])
      .then(([list, act, vel]) => {
        setSprints(list);
        setActive(act);
        setVelocity(vel);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, projectId]);

  useEffect(() => {
    if (!token || !active) return;
    Promise.all([
      fetchApprovals(token, active.id),
      fetchRisks(token, active.id),
      fetchBurndown(token, active.id),
    ])
      .then(([ap, rk, bd]) => {
        setApprovals(ap);
        setRisks(rk);
        setBurndown(bd);
      })
      .catch(() => {});
  }, [token, active]);

  const completionPct = useMemo(() => {
    if (!active || !active.metrics.storyPointsTotal) return 0;
    return Math.round((active.metrics.storyPointsDone / active.metrics.storyPointsTotal) * 100);
  }, [active]);
  const migrationCoveragePct = useMemo(() => {
    const total = sprints.reduce((acc, s) => acc + s.metrics.tasksTotal, 0);
    const done = sprints.reduce((acc, s) => acc + s.metrics.tasksDone, 0);
    return total ? Math.round((done / total) * 100) : 0;
  }, [sprints]);

  const handleSeed = () => {
    if (!token || !projectId) return;
    setSeeding(true);
    seedSprints(token, projectId)
      .then(() => {
        refetchSprints();
      })
      .catch(() => {})
      .finally(() => setSeeding(false));
  };

  if (loading) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectId}`}
        title="Sprint dashboard"
      >
        <LoadingState />
      </AppShell>
    );
  }

  if (sprints.length === 0 || !active) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectId}`}
        title="Sprint dashboard"
        actions={
          <Button variant="outline" onClick={() => setShowNewSprint(true)}>
            <Plus className="h-4 w-4" /> New sprint
          </Button>
        }
      >
        <Card>
          <EmptyState
            title="No sprints yet"
            description="Run the seed to populate demo sprints, or create one manually."
            action={
              <div className="flex gap-2 justify-center">
                <Button variant="outline" onClick={() => setShowNewSprint(true)}>
                  <Plus className="h-4 w-4" /> New sprint
                </Button>
                <Button variant="primary" loading={seeding} onClick={handleSeed}>
                  Run seed
                </Button>
              </div>
            }
          />
        </Card>
        {showNewSprint && (
          <NewSprintModal
            onClose={() => setShowNewSprint(false)}
            onCreated={() => {
              setShowNewSprint(false);
              refetchSprints();
            }}
            onSubmit={(form) =>
              createSprint(token, projectId, form).then(() => undefined)
            }
          />
        )}
      </AppShell>
    );
  }

  const approvalsPreview = approvals.slice(0, 3);
  const risksPreview = risks.slice(0, 3);

  return (
    <AppShell
      eyebrow={`SPRINTS · ${projectId}`}
      title="Sprint dashboard"
      description="Active sprint progress, multi-sprint roadmap, and operational risk in one view."
      actions={
        <>
          <Button variant="outline">
            <Download className="h-4 w-4" /> Export
          </Button>
          <Button variant="outline" onClick={() => setShowNewSprint(true)}>
            <Plus className="h-4 w-4" /> New sprint
          </Button>
          <Button variant="primary">
            <Plus className="h-4 w-4" /> Start sprint
          </Button>
        </>
      }
    >
      {showNewSprint && (
        <NewSprintModal
          onClose={() => setShowNewSprint(false)}
          onCreated={() => {
            setShowNewSprint(false);
            refetchSprints();
          }}
          onSubmit={(form) =>
            createSprint(token, projectId, form).then(() => undefined)
          }
        />
      )}

      {/* ── Top metric strip ────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 bg-surface border border-hx rounded-[10px] divide-y lg:divide-y-0 lg:divide-x divide-hx mb-6">
        <MetricCell
          big
          label="Sprint completion"
          value={`${completionPct}%`}
          hint={`${active.metrics.storyPointsDone}/${active.metrics.storyPointsTotal} SP`}
        />
        <MetricCell
          big
          label="Migration coverage"
          value={`${migrationCoveragePct}%`}
          hint={`${sprints.length} sprints · 1 portfolio`}
        />
        <MetricCell
          big
          label="Validation coverage"
          value={`${active.metrics.validationCoveragePct}%`}
          hint="Active sprint"
        />
        <MetricCell
          big
          label="Recon coverage"
          value={`${active.metrics.reconCoveragePct}%`}
          hint="Active sprint"
        />
        <MetricCell
          big
          label="AI automation"
          value={`${active.metrics.aiAutomationPct}%`}
          hint="Agent-driven work"
        />
      </div>

      {/* ── Active sprint summary: progress + health ────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <SprintProgressCard sprint={active} />
        <SprintHealthCard sprint={active} />
      </div>

      {/* ── Burndown + Velocity ─────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <Card title="Burndown" eyebrow="ACTIVE SPRINT">
          <SprintBurndownChart data={burndown} />
        </Card>
        <Card title="Velocity" eyebrow="ROLLING 5 SPRINTS">
          <SprintVelocityChart data={velocity} />
        </Card>
      </div>

      {/* ── All sprints grid ────────────────────────────────────── */}
      <div className="mb-6">
        <div className="flex items-end justify-between mb-3">
          <div>
            <div className="eyebrow text-[10px]">PORTFOLIO</div>
            <h2 className="text-[15px] font-semibold text-ink tracking-tight">All sprints</h2>
          </div>
          <span className="font-mono text-[11px] text-ink-4">{sprints.length} total</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {sprints.map((s) => (
            <SprintCard key={s.id} sprint={s} />
          ))}
        </div>
      </div>

      {/* ── Footer: approvals + risks ───────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card
          title="Pending approvals"
          eyebrow="ACTIVE SPRINT"
          actions={<Button variant="outline" size="sm">View all</Button>}
        >
          <div className="space-y-2.5">
            {approvalsPreview.length === 0 ? (
              <p className="text-[12px] text-ink-3">No pending approvals.</p>
            ) : (
              approvalsPreview.map((a) => <SprintApprovalCard key={a.id} approval={a} />)
            )}
          </div>
        </Card>
        <Card
          title="Open risks"
          eyebrow="ACTIVE SPRINT"
          actions={<Button variant="outline" size="sm">View all</Button>}
        >
          <div className="space-y-2.5">
            {risksPreview.length === 0 ? (
              <p className="text-[12px] text-ink-3">No open risks.</p>
            ) : (
              risksPreview.map((r) => <SprintRiskCard key={r.id} risk={r} />)
            )}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

// ── New Sprint Modal ─────────────────────────────────────────────────

function NewSprintModal({
  onClose,
  onCreated,
  onSubmit,
}: {
  onClose: () => void;
  onCreated: () => void;
  onSubmit: (input: NewSprintInput) => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  useFocusTrap(dialogRef, true, onClose);
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [status, setStatus] = useState<"planning" | "active">("planning");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const baseId = useId();
  const nameId = `${baseId}-name`;
  const goalId = `${baseId}-goal`;
  const statusId = `${baseId}-status`;
  const startId = `${baseId}-start`;
  const endId = `${baseId}-end`;

  // Escape close + focus trap owned by useFocusTrap above.

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const payload: NewSprintInput = {
        name: name.trim(),
        status,
        ...(goal.trim() ? { goal: goal.trim() } : {}),
        ...(startDate ? { start_date: startDate } : {}),
        ...(endDate ? { end_date: endDate } : {}),
      };
      await onSubmit(payload);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create sprint");
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-sprint-title"
        tabIndex={-1}
        className="w-full max-w-md outline-none"
      >
        <Card
          eyebrow={
            <div className="flex items-center justify-between gap-2">
              <span>NEW SPRINT</span>
              <button
                type="button"
                onClick={onClose}
                className="text-ink-4 hover:text-ink-2 transition-colors"
                aria-label="Close"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          }
          title={<span id="new-sprint-title">Create a sprint</span>}
        >
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label htmlFor={nameId} className="eyebrow text-[10px] mb-1 block">
                NAME <span aria-hidden className="text-err">*</span>
                <span className="sr-only">(required)</span>
              </label>
              <input
                id={nameId}
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                required
                aria-required
                className="w-full h-8 px-2.5 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring"
                placeholder="Sprint 4 — Validation"
              />
            </div>
            <div>
              <label htmlFor={goalId} className="eyebrow text-[10px] mb-1 block">GOAL</label>
              <textarea
                id={goalId}
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                rows={3}
                className="w-full px-2.5 py-2 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring resize-none"
                placeholder="Optional sprint goal"
              />
            </div>
            <div>
              <label htmlFor={statusId} className="eyebrow text-[10px] mb-1 block">STATUS</label>
              <select
                id={statusId}
                value={status}
                onChange={(e) => setStatus(e.target.value as "planning" | "active")}
                className="w-full h-8 px-2 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring"
              >
                <option value="planning">planning</option>
                <option value="active">active</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label htmlFor={startId} className="eyebrow text-[10px] mb-1 block">START</label>
                <input
                  id={startId}
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full h-8 px-2 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring"
                />
              </div>
              <div>
                <label htmlFor={endId} className="eyebrow text-[10px] mb-1 block">END</label>
                <input
                  id={endId}
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full h-8 px-2 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring"
                />
              </div>
            </div>
            {error && (
              <div role="alert" aria-live="assertive" className="rounded-[8px] border border-hx bg-[var(--con-err-soft)] px-3 py-2 text-[11.5px] text-err">
                {error}
              </div>
            )}
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" loading={saving}>
                Create sprint
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
