"use client";

/**
 * Sprint kanban board — premium enterprise variant.
 *
 * Columns are migration-specific (Backlog → AI Processing → Validation →
 * Recon → Approved → Completed) rather than the generic Jira "todo/doing/done".
 * Tasks are colored by risk + tagged with their AI agent so a migration lead
 * can spot a stuck row at a glance.
 *
 * Drag-and-drop is intentionally not wired here; the focus is read-mode
 * visualization for stakeholders. The optional `onMove(taskId, target)` hook
 * is the surface where a future DnD library plugs in.
 */

import React from "react";
import { Avatar, Chip } from "@/components/ui";
import { AgentIcon } from "@/components/icons";

import { TASK_STATUS_ACCENT, TASK_STATUS_LABEL } from "./primitives";
import type { Priority, RiskLevel, SprintTask, TaskStatus } from "@/lib/sprints";

const COLUMNS: TaskStatus[] = [
  "backlog", "ready", "in_progress", "ai_processing",
  "human_review", "validation", "recon", "qa",
  "approved", "completed", "blocked",
];

const PRIORITY_TONE: Record<Priority, { bg: string; fg: string }> = {
  P0: { bg: "var(--con-err-soft)", fg: "var(--con-err)" },
  P1: { bg: "var(--con-warn-soft)", fg: "var(--con-warn)" },
  P2: { bg: "var(--con-info-soft)", fg: "var(--con-info)" },
  P3: { bg: "var(--con-bg-2)",      fg: "var(--con-ink-3)" },
};

const RISK_DOT: Record<RiskLevel, string> = {
  low: "var(--con-ok)", med: "var(--con-warn)",
  high: "var(--con-err)", critical: "var(--con-err)",
};

export function SprintKanbanBoard({
  tasks,
  onTaskClick,
}: {
  tasks: SprintTask[];
  onTaskClick?: (task: SprintTask) => void;
}) {
  return (
    <div className="overflow-x-auto pb-3">
      <div className="flex gap-3 min-w-max">
        {COLUMNS.map((col) => {
          const rows = tasks.filter((t) => t.status === col);
          return (
            <div key={col} className="w-[260px] flex-shrink-0">
              <div className="flex items-center justify-between px-2 mb-2">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: TASK_STATUS_ACCENT[col] }} />
                  <span className="text-[11.5px] font-medium text-ink">{TASK_STATUS_LABEL[col]}</span>
                </div>
                <span className="font-mono text-[11px] text-ink-4">{rows.length}</span>
              </div>
              <div className="flex flex-col gap-2 bg-app-2 rounded-[10px] p-2 min-h-[80px]">
                {rows.length === 0 && (
                  <div className="text-[11px] text-ink-5 text-center py-3">No tasks</div>
                )}
                {rows.map((t) => (
                  <TaskCard key={t.id} task={t} onClick={() => onTaskClick?.(t)} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TaskCard({ task, onClick }: { task: SprintTask; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-left bg-surface border border-hx rounded-[8px] p-2.5 hover:shadow-soft transition-shadow"
    >
      <div className="flex items-center justify-between mb-1.5">
        <span
          className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-medium"
          style={{ background: PRIORITY_TONE[task.priority].bg, color: PRIORITY_TONE[task.priority].fg }}
        >
          {task.priority}
        </span>
        <span className="font-mono text-[10px] text-ink-4">{task.id}</span>
      </div>
      <div className="text-[12px] text-ink leading-snug line-clamp-2">{task.title}</div>
      <div className="mt-2 flex items-center gap-1.5">
        {task.aiAgent ? (
          <AgentIcon name={task.aiAgent} size={18} />
        ) : task.owner ? (
          <Avatar name={task.owner.name} size={18} />
        ) : null}
        <span className="text-[10.5px] text-ink-3 truncate">{task.aiAgent ?? task.owner?.name ?? "—"}</span>
        <span className="ml-auto inline-flex items-center gap-1 font-mono text-[10.5px] text-ink-4">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: RISK_DOT[task.riskLevel] }} />
          {task.storyPoints}
        </span>
      </div>
      {(task.validationStatus || task.reconStatus) && (
        <div className="mt-1.5 flex gap-1">
          {task.validationStatus && task.validationStatus !== "pending" && (
            <Chip tone={task.validationStatus === "pass" ? "ok" : task.validationStatus === "warn" ? "warn" : "err"}>val·{task.validationStatus}</Chip>
          )}
          {task.reconStatus && task.reconStatus !== "pending" && (
            <Chip tone={task.reconStatus === "pass" ? "ok" : task.reconStatus === "warn" ? "warn" : "err"}>rec·{task.reconStatus}</Chip>
          )}
        </div>
      )}
    </button>
  );
}
