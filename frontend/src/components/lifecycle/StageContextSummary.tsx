"use client";

import { FileText } from "lucide-react";
import type { MigrationStage, MigrationArtifact } from "@/lib/lifecycle/api";
import { agentLabel, STAGE_OBJECTIVE } from "./labels";

interface Props {
  stage: MigrationStage;
  approvedArtifacts: MigrationArtifact[];   // approved artifacts that feed this stage's prompt
}

// "Input context summary" panel — what the agent is working from.
export function StageContextSummary({ stage, approvedArtifacts }: Props) {
  const upstream = approvedArtifacts.filter((a) => a.stage_id !== stage.id);
  return (
    <div className="space-y-3 text-[13px]">
      <div>
        <div className="text-[11px] uppercase tracking-wide text-ink-3">Objective</div>
        <p className="mt-1 text-ink-2">{STAGE_OBJECTIVE[stage.stage_key] || "—"}</p>
      </div>
      <div>
        <div className="text-[11px] uppercase tracking-wide text-ink-3">Assigned agent</div>
        <p className="mt-1 text-ink-2">{agentLabel(stage.assigned_agent)}</p>
      </div>
      <div>
        <div className="text-[11px] uppercase tracking-wide text-ink-3">Context from approved artifacts</div>
        {upstream.length === 0 ? (
          <p className="mt-1 text-ink-3">No upstream approved artifacts yet.</p>
        ) : (
          <ul className="mt-1.5 space-y-1">
            {upstream.map((a) => (
              <li key={a.id} className="flex items-center gap-2 text-ink-2">
                <FileText className="h-3.5 w-3.5 text-ink-3" />
                <span className="truncate">{a.title}</span>
                <span className="text-[11px] text-ink-3">· {a.artifact_type}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
