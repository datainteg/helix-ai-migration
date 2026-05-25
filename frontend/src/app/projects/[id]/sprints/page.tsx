"use client";

/**
 * /projects/[id]/sprints — Sprint Dashboard.
 *
 * Landing page for sprint management. Surfaces sprint-level KPIs (top metric
 * strip), the active sprint (progress + health + burndown + velocity), every
 * sprint as a card, and the urgent footer (approvals + risks).
 */

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { Download, Plus } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, MetricCell } from "@/components/ui";
import {
  SprintCard,
  SprintProgressCard,
  SprintHealthCard,
  SprintBurndownChart,
  SprintVelocityChart,
  SprintApprovalCard,
  SprintRiskCard,
} from "@/components/sprints";
import {
  getSprints,
  getActiveSprint,
  getVelocity,
  getApprovalsForSprint,
  getRisksForSprint,
  PROJECT_ID,
} from "@/lib/sprints";

export default function SprintDashboardPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params?.id ?? PROJECT_ID);

  const active = getActiveSprint();
  const sprints = getSprints();
  const velocity = getVelocity();
  const approvals = getApprovalsForSprint(active.id).slice(0, 3);
  const risks = getRisksForSprint(active.id).slice(0, 3);

  const completionPct = useMemo(
    () => Math.round((active.metrics.storyPointsDone / active.metrics.storyPointsTotal) * 100),
    [active]
  );
  const migrationCoveragePct = useMemo(() => {
    const total = sprints.reduce((acc, s) => acc + s.metrics.tasksTotal, 0);
    const done = sprints.reduce((acc, s) => acc + s.metrics.tasksDone, 0);
    return total ? Math.round((done / total) * 100) : 0;
  }, [sprints]);

  return (
    <AppShell
      eyebrow={`SPRINTS · ${projectId}`}
      title="Sprint dashboard"
      description="Active sprint progress, multi-sprint roadmap, and operational risk in one view."
      crumbs={["Projects", projectId, "Sprints", "Dashboard"]}
      actions={
        <>
          <Button variant="outline">
            <Download className="h-4 w-4" /> Export
          </Button>
          <Button variant="primary">
            <Plus className="h-4 w-4" /> Start sprint
          </Button>
        </>
      }
    >
      {/* ── Top metric strip ────────────────────────────────────── */}
      <div className="grid grid-cols-5 bg-surface border border-hx rounded-[10px] divide-x divide-hx mb-6">
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
          <SprintBurndownChart data={active.burndown} />
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
            {approvals.length === 0 ? (
              <p className="text-[12px] text-ink-3">No pending approvals.</p>
            ) : (
              approvals.map((a) => <SprintApprovalCard key={a.id} approval={a} />)
            )}
          </div>
        </Card>
        <Card
          title="Open risks"
          eyebrow="ACTIVE SPRINT"
          actions={<Button variant="outline" size="sm">View all</Button>}
        >
          <div className="space-y-2.5">
            {risks.length === 0 ? (
              <p className="text-[12px] text-ink-3">No open risks.</p>
            ) : (
              risks.map((r) => <SprintRiskCard key={r.id} risk={r} />)
            )}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
