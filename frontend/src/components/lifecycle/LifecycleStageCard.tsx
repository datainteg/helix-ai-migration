"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MigrationStage } from "@/lib/lifecycle/api";
import { StageStatusBadge } from "./StageStatusBadge";
import { agentLabel, isAgentRunnable, nextActionHint } from "./labels";

interface Props {
  stage: MigrationStage;
  projectKey: string;     // slug or id, for the detail link
  isCurrent?: boolean;
}

// Left accent colour mirrors the spec status palette.
const ACCENT: Record<string, string> = {
  approved: "bg-[var(--con-ok)]", completed: "bg-[var(--con-ok)]",
  under_review: "bg-[var(--con-warn)]", edit_requested: "bg-[var(--con-warn)]",
  rejected: "bg-[var(--con-err)]", failed: "bg-[var(--con-err)]",
  running: "bg-[var(--con-brand)]", resubmitted: "bg-[var(--con-brand)]", generated: "bg-[var(--con-brand)]",
};

export function LifecycleStageCard({ stage, projectKey, isCurrent }: Props) {
  const runnable = isAgentRunnable(stage.assigned_agent);
  const accent = ACCENT[stage.status] || (stage.is_optional ? "bg-hx-2" : "bg-hx");
  return (
    <Link
      href={`/projects/${projectKey}/lifecycle/${stage.stage_key}`}
      className={cn(
        "group relative flex items-stretch gap-3 rounded-[10px] border bg-app-2/40 pr-3 transition-colors hover:bg-app-2",
        isCurrent ? "border-helix-400 ring-1 ring-helix-300" : "border-hx",
      )}
    >
      <span className={cn("w-1 rounded-l-[10px]", accent)} aria-hidden />
      <div className="flex-1 py-3">
        <div className="flex items-center gap-2">
          <span className="text-[10px] tabular-nums text-ink-3">#{stage.stage_order}</span>
          <span className="text-[13.5px] font-medium text-ink-1">{stage.stage_name}</span>
          {stage.is_optional && <span className="text-[10px] uppercase tracking-wide text-ink-3">optional</span>}
          {isCurrent && <span className="text-[10px] font-medium text-helix-700">· current</span>}
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <StageStatusBadge status={stage.status} />
          <span className="text-[12px] text-ink-3">{agentLabel(stage.assigned_agent)}</span>
        </div>
        <p className="mt-1.5 text-[12px] text-ink-3">{nextActionHint(stage.status, runnable)}</p>
      </div>
      <ChevronRight className="h-4 w-4 self-center text-ink-3 transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}
