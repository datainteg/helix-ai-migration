"use client";

import type { MigrationStage } from "@/lib/lifecycle/api";
import { StageStatusBadge } from "./StageStatusBadge";

function fmt(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return isNaN(d.getTime()) ? ts : d.toLocaleString();
}

// Approval / status panel for a stage.
export function StageApprovalPanel({ stage }: { stage: MigrationStage }) {
  const rows: Array<[string, React.ReactNode]> = [
    ["Status", <StageStatusBadge key="s" status={stage.status} />],
    ["Started", fmt(stage.started_at)],
    ["Generated", fmt(stage.generated_at)],
    ["Submitted for review", fmt(stage.submitted_for_review_at)],
    ["Approved", fmt(stage.approved_at)],
  ];
  if (stage.rejected_at) rows.push(["Rejected", fmt(stage.rejected_at)]);
  return (
    <dl className="space-y-2 text-[13px]">
      {rows.map(([k, v]) => (
        <div key={k} className="flex items-center justify-between gap-3">
          <dt className="text-ink-3">{k}</dt>
          <dd className="text-ink-1">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
