"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Chip, ProgressBar } from "@/components/ui";
import type { MigrationStage, StageTransition } from "@/lib/lifecycle/api";
import { STAGE_STATUS_META } from "./StageStatusBadge";
import { isAgentRunnable } from "./labels";

const DONE = ["approved", "completed", "skipped"];

// HXM-NNNNNN alias chip.
export function ProjectAliasBadge({ alias }: { alias: string | null | undefined }) {
  if (!alias) return null;
  return <span className="rounded-md bg-app-2 px-2 py-0.5 font-mono text-[12px] text-helix-700">{alias}</span>;
}

export function LifecycleProgressBar({ percent }: { percent: number }) {
  return (
    <div>
      <div className="flex items-center justify-between text-[11px] text-ink-3"><span>Lifecycle progress</span><span className="tabular-nums">{percent}%</span></div>
      <div className="mt-1"><ProgressBar value={percent} tone="brand" height={6} /></div>
    </div>
  );
}

// Row of small dots, one per stage, coloured by status.
export function StageMiniStatus({ stages, currentStageKey }: { stages: MigrationStage[]; currentStageKey?: string | null }) {
  const tone: Record<string, string> = {
    ok: "bg-[var(--con-ok)]", warn: "bg-[var(--con-warn)]", err: "bg-[var(--con-err)]",
    info: "bg-[var(--con-brand)]", zinc: "bg-hx-2", default: "bg-hx-2", brand: "bg-[var(--con-brand)]",
  };
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {stages.map((s) => {
        const meta = STAGE_STATUS_META[s.status];
        return (
          <span key={s.id} title={`${s.stage_name}: ${meta?.label || s.status}`}
            className={cn("h-2.5 w-2.5 rounded-full", tone[meta?.tone || "default"] || "bg-hx-2",
              s.stage_key === currentStageKey && "ring-2 ring-helix-300")} />
        );
      })}
    </div>
  );
}

// Derive the single most useful next action from the current stage.
export function computeNextBestAction(stages: MigrationStage[], projectKey: string): { label: string; href: string } | null {
  const current = stages.find((s) => !DONE.includes(s.status) && !(s.is_optional && s.status === "not_started"));
  if (!current) return null;
  const name = current.stage_name;
  const lc = `/projects/${projectKey}/lifecycle/${current.stage_key}`;
  const SPECIAL: Record<string, { href: string; verbs: Partial<Record<string, string>> }> = {
    SPRINT_GENERATION: { href: `/projects/${projectKey}/sprints`, verbs: { not_started: "Generate Sprint Plan" } },
    VALIDATION: { href: `/projects/${projectKey}/validation/evidence`, verbs: { not_started: "Upload Validation Evidence", running: "Upload Validation Evidence" } },
    RECONCILIATION: { href: `/projects/${projectKey}/recon/reports`, verbs: { not_started: "Generate Recon Report" } },
    SIGN_OFF: { href: `/projects/${projectKey}/signoff`, verbs: { not_started: "Send Sign-off Email", generated: "Send Sign-off Email", under_review: "Send Sign-off Email" } },
  };
  const sp = SPECIAL[current.stage_key];
  if (sp && sp.verbs[current.status]) return { label: sp.verbs[current.status]!, href: sp.href };

  switch (current.status) {
    case "not_started":
      return { label: isAgentRunnable(current.assigned_agent) ? `Run ${name} Agent` : `Start ${name}`, href: lc };
    case "running": return { label: `${name} is running…`, href: lc };
    case "generated":
    case "under_review":
    case "resubmitted": return { label: `Review & approve ${name}`, href: lc };
    case "edit_requested": return { label: `Address changes for ${name}`, href: lc };
    case "rejected": return { label: `Re-run ${name}`, href: lc };
    case "failed": return { label: `Retry ${name}`, href: lc };
    default: return { label: `Open ${name}`, href: lc };
  }
}

export function NextBestActionCard({ stages, projectKey }: { stages: MigrationStage[]; projectKey: string }) {
  const action = computeNextBestAction(stages, projectKey);
  if (!action) {
    return <div className="rounded-md border border-[var(--con-ok)]/40 bg-[var(--con-ok)]/10 px-3 py-2.5 text-[13px] text-ink-1">All lifecycle stages complete 🎉</div>;
  }
  return (
    <Link href={action.href} className="group flex items-center justify-between rounded-md border border-helix-300 bg-helix-50/40 px-3 py-2.5 transition-colors hover:bg-helix-50">
      <div>
        <div className="text-[11px] uppercase tracking-wide text-helix-700">Next best action</div>
        <div className="text-[13.5px] font-medium text-ink-1">{action.label}</div>
      </div>
      <ArrowRight className="h-4 w-4 text-helix-700 transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

// Unified vertical timeline from the lifecycle transition log.
export function MigrationTimeline({ transitions, max }: { transitions: StageTransition[]; max?: number }) {
  const rows = max ? transitions.slice(0, max) : transitions;
  if (rows.length === 0) return <p className="text-[12.5px] text-ink-3">No lifecycle activity yet.</p>;
  return (
    <ol className="relative space-y-3 pl-4">
      <span className="absolute left-[5px] top-1 bottom-1 w-px bg-hx" aria-hidden />
      {rows.map((t) => (
        <li key={t.id} className="relative">
          <span className="absolute -left-[11px] top-1.5 h-2 w-2 rounded-full border-2 border-app bg-hx-2" aria-hidden />
          <div className="flex items-center gap-2 text-[12.5px]">
            <Chip tone="zinc" mono>{t.action}</Chip>
            <span className="text-ink-2">{t.from_status ? `${t.from_status} → ` : ""}{t.to_status}</span>
            <span className="text-[11px] text-ink-3">· {t.actor_type}</span>
          </div>
          {t.comment && <p className="mt-0.5 text-[11.5px] text-ink-3">{t.comment}</p>}
          <span className="text-[11px] text-ink-3">{t.created_at?.slice(0, 19)?.replace("T", " ")}</span>
        </li>
      ))}
    </ol>
  );
}
