"use client";

/**
 * Custom React Flow node — migration stage chip.
 *
 * Status drives the accent color + side-rail; agent badge sits in the
 * corner; small footer with validation/recon scores + approval state.
 */

import React from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { CheckCircle2, Clock, AlertTriangle, Sparkles, GitMerge, Circle, X } from "lucide-react";

import { AgentIcon } from "@/components/icons";
import type { MappingNode as MNode, MappingNodeStatus } from "@/lib/sprints";

const STATUS_ACCENT: Record<MappingNodeStatus, string> = {
  pending:       "var(--con-ink-5)",
  active:        "var(--con-brand)",
  ai_processing: "#8B5CF6",
  review:        "var(--con-warn)",
  blocked:       "var(--con-err)",
  completed:     "var(--con-ok)",
  failed:        "var(--con-err)",
};

const STATUS_ICON: Record<MappingNodeStatus, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  pending: Circle, active: Clock, ai_processing: Sparkles, review: GitMerge,
  blocked: AlertTriangle, completed: CheckCircle2, failed: X,
};

export function MappingNode({ data }: NodeProps<MNode>) {
  const accent = STATUS_ACCENT[data.status];
  const Icon = STATUS_ICON[data.status];
  return (
    <div
      className="bg-surface border border-hx rounded-[10px] shadow-soft w-[200px] overflow-hidden"
      style={{ boxShadow: `0 0 0 1px var(--con-line), inset 4px 0 0 0 ${accent}` }}
    >
      <Handle type="target" position={Position.Left} style={{ background: accent, border: "none", width: 6, height: 6 }} />
      <div className="px-3 pt-2.5 pb-1.5 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="eyebrow text-[9px]">{data.kind.replace(/_/g, " ")}</div>
          <div className="text-[12.5px] font-semibold text-ink mt-0.5 leading-tight truncate">{data.label}</div>
        </div>
        {data.agent && <AgentIcon name={data.agent} size={20} />}
      </div>
      <div className="px-3 pb-2 flex items-center gap-1.5 text-[10.5px] text-ink-3">
        <Icon className="h-3 w-3" style={{ color: accent }} />
        <span className="capitalize">{data.status.replace(/_/g, " ")}</span>
        {data.artifactCount > 0 && <span className="ml-auto font-mono text-ink-4">📄 {data.artifactCount}</span>}
      </div>
      {(data.validationScore != null || data.reconScore != null || data.riskScore != null) && (
        <div className="px-3 pb-2 pt-1.5 border-t border-hx flex items-center justify-between text-[10px] font-mono text-ink-3">
          {data.validationScore != null && <span>VAL <span className="text-ink-2">{data.validationScore}</span></span>}
          {data.reconScore != null && <span>REC <span className="text-ink-2">{data.reconScore}</span></span>}
          {data.riskScore != null && (
            <span style={{ color: data.riskScore >= 60 ? "var(--con-err)" : data.riskScore >= 40 ? "var(--con-warn)" : "var(--con-ok)" }}>
              RISK <span className="font-bold">{data.riskScore}</span>
            </span>
          )}
        </div>
      )}
      <Handle type="source" position={Position.Right} style={{ background: accent, border: "none", width: 6, height: 6 }} />
    </div>
  );
}
