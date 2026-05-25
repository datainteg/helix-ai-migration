"use client";

/**
 * Sprint UI primitives — small reusable building blocks shared across every
 * Sprint page. Kept in one file to minimize import churn and keep the
 * file-system tree manageable (10 sprint pages each pulling 5+ tiny
 * components from individual files would be noise).
 *
 * Bigger / interactive components live in their own files:
 *  - SprintKanbanBoard.tsx
 *  - SprintBurndownChart.tsx
 *  - SprintVelocityChart.tsx
 *  - SprintDependencyGraph.tsx
 *  - MigrationMappingCanvas.tsx
 */

import React from "react";
import { CheckCircle2, AlertTriangle, Circle, Clock, ShieldAlert, Zap, GitMerge, FileCheck2 } from "lucide-react";

import { Card, Chip, ProgressBar } from "@/components/ui";
import type {
  Sprint, SprintHealth, SprintMilestone, SprintRisk, SprintApproval, TaskStatus, RiskLevel,
} from "@/lib/sprints";

// ── Color helpers ────────────────────────────────────────────────────

const HEALTH_TONE: Record<SprintHealth, "ok" | "warn" | "err" | "info"> = {
  "on-track":  "ok",
  "at-risk":   "warn",
  "off-track": "err",
  "blocked":   "err",
};

const HEALTH_LABEL: Record<SprintHealth, string> = {
  "on-track":  "On track",
  "at-risk":   "At risk",
  "off-track": "Off track",
  "blocked":   "Blocked",
};

const RISK_TONE: Record<RiskLevel, "ok" | "warn" | "err"> = {
  low: "ok", med: "warn", high: "err", critical: "err",
};

export const TASK_STATUS_LABEL: Record<TaskStatus, string> = {
  backlog: "Backlog", ready: "Ready", in_progress: "In progress",
  ai_processing: "AI processing", human_review: "Human review",
  validation: "Validation", recon: "Recon", qa: "QA",
  approved: "Approved", completed: "Completed", blocked: "Blocked",
};

export const TASK_STATUS_ACCENT: Record<TaskStatus, string> = {
  backlog: "var(--con-ink-4)", ready: "var(--con-info)", in_progress: "var(--con-brand)",
  ai_processing: "#8B5CF6", human_review: "var(--con-warn)",
  validation: "var(--con-info)", recon: "var(--con-info)", qa: "var(--con-warn)",
  approved: "var(--con-ok)", completed: "var(--con-ok)", blocked: "var(--con-err)",
};

// ── SprintCard ──────────────────────────────────────────────────────

export function SprintCard({ sprint, onClick }: { sprint: Sprint; onClick?: () => void }) {
  const pct = Math.round((sprint.metrics.storyPointsDone / sprint.metrics.storyPointsTotal) * 100);
  return (
    <button
      onClick={onClick}
      className="text-left w-full bg-surface border border-hx rounded-[10px] p-4 hover:bg-surface-hi transition-colors shadow-xs"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="eyebrow text-[10px] mb-1">SPRINT {sprint.index}</div>
          <div className="text-[14px] font-semibold text-ink truncate">{sprint.name.replace(`Sprint ${sprint.index} — `, "")}</div>
          <div className="text-[11.5px] text-ink-3 mt-1 line-clamp-2">{sprint.goal}</div>
        </div>
        <Chip tone={HEALTH_TONE[sprint.health]} dot>{HEALTH_LABEL[sprint.health]}</Chip>
      </div>
      <ProgressBar value={pct} tone={sprint.health === "on-track" ? "ok" : sprint.health === "at-risk" ? "warn" : "err"} height={4} />
      <div className="mt-2 flex items-center justify-between text-[11px] text-ink-4">
        <span className="font-mono">{sprint.metrics.storyPointsDone}/{sprint.metrics.storyPointsTotal} SP</span>
        <span className="font-mono">{pct}%</span>
      </div>
    </button>
  );
}

// ── SprintProgressCard ──────────────────────────────────────────────

export function SprintProgressCard({ sprint }: { sprint: Sprint }) {
  const pct = Math.round((sprint.metrics.storyPointsDone / sprint.metrics.storyPointsTotal) * 100);
  const days = Math.max(1, Math.ceil((new Date(sprint.endDate).getTime() - Date.now()) / 86_400_000));
  return (
    <Card>
      <div className="eyebrow text-[10px] mb-1">ACTIVE SPRINT PROGRESS</div>
      <div className="flex items-baseline gap-3 mb-3">
        <span className="font-mono tabular-nums text-[32px] font-medium tracking-editorial">{pct}%</span>
        <span className="text-[11.5px] text-ink-3">{sprint.metrics.storyPointsDone}/{sprint.metrics.storyPointsTotal} SP · {days}d remaining</span>
      </div>
      <ProgressBar value={pct} tone="ok" height={6} />
      <div className="grid grid-cols-3 gap-3 mt-4">
        <Metric label="Validation" value={`${sprint.metrics.validationCoveragePct}%`} />
        <Metric label="Recon"      value={`${sprint.metrics.reconCoveragePct}%`} />
        <Metric label="AI auto"    value={`${sprint.metrics.aiAutomationPct}%`} />
      </div>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="eyebrow text-[9.5px]">{label}</div>
      <div className="font-mono tabular-nums text-[18px] font-medium text-ink mt-0.5">{value}</div>
    </div>
  );
}

// ── SprintHealthCard ────────────────────────────────────────────────

export function SprintHealthCard({ sprint }: { sprint: Sprint }) {
  const items: Array<{ label: string; value: string; tone: "ok" | "warn" | "err"; icon: React.ReactNode }> = [
    { label: "Open risks",      value: String(sprint.metrics.openRisks),          tone: sprint.metrics.openRisks > 0 ? "warn" : "ok",     icon: <ShieldAlert className="h-3.5 w-3.5" /> },
    { label: "Critical issues", value: String(sprint.metrics.criticalIssues),     tone: sprint.metrics.criticalIssues > 0 ? "err" : "ok", icon: <AlertTriangle className="h-3.5 w-3.5" /> },
    { label: "Pending approvals", value: String(sprint.metrics.humanApprovalsPending), tone: sprint.metrics.humanApprovalsPending > 0 ? "warn" : "ok", icon: <FileCheck2 className="h-3.5 w-3.5" /> },
    { label: "Velocity",        value: String(sprint.metrics.velocity) + " SP",   tone: "ok", icon: <Zap className="h-3.5 w-3.5" /> },
  ];
  return (
    <Card title="Sprint health" eyebrow="LIVE SIGNALS">
      <div className="grid grid-cols-2 gap-3">
        {items.map((it) => (
          <div key={it.label} className="bg-app-2 rounded-[8px] px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-ink-4">
              {it.icon}
              <span className="text-[10.5px] uppercase tracking-[0.08em] font-mono">{it.label}</span>
            </div>
            <div className={`font-mono tabular-nums text-[18px] mt-0.5 ${it.tone === "ok" ? "text-ok" : it.tone === "warn" ? "text-warn" : "text-err"}`}>{it.value}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── SprintMilestoneCard ─────────────────────────────────────────────

export function SprintMilestoneCard({ milestone }: { milestone: SprintMilestone }) {
  const Icon = milestone.status === "done" ? CheckCircle2 : milestone.status === "in_progress" ? Clock : Circle;
  const tone = milestone.status === "done" ? "var(--con-ok)" : milestone.status === "in_progress" ? "var(--con-brand)" : "var(--con-ink-4)";
  return (
    <div className="flex items-start gap-2.5 py-2">
      <Icon className="h-3.5 w-3.5 mt-0.5" style={{ color: tone }} />
      <div className="flex-1 min-w-0">
        <div className="text-[12.5px] font-medium text-ink">{milestone.label}</div>
        <div className="text-[10.5px] text-ink-4 font-mono mt-0.5">{milestone.kind.toUpperCase()} · {milestone.date}</div>
      </div>
    </div>
  );
}

// ── SprintRiskCard ──────────────────────────────────────────────────

export function SprintRiskCard({ risk }: { risk: SprintRisk }) {
  return (
    <Card>
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 grid place-items-center h-9 w-9 rounded-[8px] bg-[var(--con-err-soft)] text-err">
          <ShieldAlert className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Chip tone={RISK_TONE[risk.level]} dot mono>{risk.level.toUpperCase()}</Chip>
            <Chip tone="default" mono>{risk.category}</Chip>
            {risk.aiConfidence != null && <span className="text-[10.5px] text-ink-4 font-mono ml-auto">AI {risk.aiConfidence}%</span>}
          </div>
          <div className="text-[13px] font-semibold text-ink">{risk.title}</div>
          <p className="text-[11.5px] text-ink-3 mt-1 leading-relaxed">{risk.description}</p>
          <div className="mt-2 text-[11.5px] text-ink-2">
            <span className="text-ink-4 font-mono uppercase text-[10px] mr-1.5">Mitigation</span>
            {risk.mitigation}
          </div>
        </div>
      </div>
    </Card>
  );
}

// ── SprintApprovalCard ──────────────────────────────────────────────

export function SprintApprovalCard({ approval, onApprove, onReject }: {
  approval: SprintApproval;
  onApprove?: () => void;
  onReject?: () => void;
}) {
  return (
    <div className="bg-surface border border-hx rounded-[10px] p-4 shadow-xs">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <GitMerge className="h-3.5 w-3.5 text-[var(--con-warn)]" />
            <span className="text-[10.5px] uppercase tracking-[0.08em] font-mono text-ink-4">{approval.kind.replace("_", " ")}</span>
          </div>
          <div className="text-[13px] font-semibold text-ink">{approval.title}</div>
          <div className="text-[11px] text-ink-4 mt-1 font-mono">
            By {approval.requestedBy} · {new Date(approval.requestedAt).toLocaleString()}
          </div>
          <div className="text-[11px] text-ink-3 mt-1">
            Approvers: <span className="font-medium text-ink-2">{approval.approvers.join(", ")}</span>
          </div>
        </div>
        <Chip tone={approval.status === "pending" ? "warn" : approval.status === "approved" ? "ok" : "err"} dot pulse={approval.status === "pending"}>
          {approval.status}
        </Chip>
      </div>
      {approval.status === "pending" && (
        <div className="mt-3 flex gap-2">
          <button onClick={onReject} className="px-3 h-7 text-[11.5px] font-medium rounded-md border border-hx text-err hover:bg-[var(--con-err-soft)]">Reject</button>
          <button onClick={onApprove} className="px-3 h-7 text-[11.5px] font-medium rounded-md bg-ink text-white hover:bg-zinc-800">Approve</button>
        </div>
      )}
    </div>
  );
}
