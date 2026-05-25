"use client";

/**
 * Sprint kanban board — premium enterprise variant.
 *
 * Columns are migration-specific (Backlog → AI Processing → Validation →
 * Recon → Approved → Completed) rather than the generic Jira "todo/doing/done".
 * Tasks are colored by risk + tagged with their AI agent so a migration lead
 * can spot a stuck row at a glance.
 *
 * Drag-and-drop is wired via @dnd-kit/core. Cards are draggable, columns are
 * droppable. The parent owns the task list and `onMove(taskId, newStatus)`
 * applies the optimistic update + PATCH call. If the parent omits `onMove`,
 * the board falls back to read-only mode (cards remain clickable, no drag
 * handles are activated).
 */

import React from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";

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
  onMove,
}: {
  tasks: SprintTask[];
  onTaskClick?: (task: SprintTask) => void;
  onMove?: (taskId: string, newStatus: TaskStatus) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
  );
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const activeTask = activeId ? tasks.find((t) => t.id === activeId) ?? null : null;

  const handleStart = (e: DragStartEvent) => {
    setActiveId(String(e.active.id));
  };

  const handleEnd = (e: DragEndEvent) => {
    setActiveId(null);
    const { active, over } = e;
    if (!over || !onMove) return;
    const taskId = String(active.id);
    const overId = String(over.id);
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return;
    // Only handle column drops; other droppables can be added later.
    if (!COLUMNS.includes(overId as TaskStatus)) return;
    const newStatus = overId as TaskStatus;
    if (task.status === newStatus) return;
    onMove(taskId, newStatus);
  };

  const board = (
    <div className="overflow-x-auto pb-3">
      <div className="flex gap-3 min-w-max">
        {COLUMNS.map((col) => {
          const rows = tasks.filter((t) => t.status === col);
          return (
            <KanbanColumn
              key={col}
              status={col}
              count={rows.length}
              dndEnabled={Boolean(onMove)}
            >
              {rows.length === 0 && (
                <div className="text-[11px] text-ink-5 text-center py-3">No tasks</div>
              )}
              {rows.map((t) => (
                <TaskCard
                  key={t.id}
                  task={t}
                  draggable={Boolean(onMove)}
                  onClick={() => onTaskClick?.(t)}
                />
              ))}
            </KanbanColumn>
          );
        })}
      </div>
    </div>
  );

  if (!onMove) {
    return board;
  }

  return (
    <DndContext sensors={sensors} onDragStart={handleStart} onDragEnd={handleEnd}>
      {board}
      <DragOverlay>
        {activeTask ? <TaskCard task={activeTask} dragOverlay /> : null}
      </DragOverlay>
    </DndContext>
  );
}

function KanbanColumn({
  status,
  count,
  dndEnabled,
  children,
}: {
  status: TaskStatus;
  count: number;
  dndEnabled: boolean;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status, disabled: !dndEnabled });
  return (
    <div className="w-[260px] flex-shrink-0">
      <div className="flex items-center justify-between px-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: TASK_STATUS_ACCENT[status] }} />
          <span className="text-[11.5px] font-medium text-ink">{TASK_STATUS_LABEL[status]}</span>
        </div>
        <span className="font-mono text-[11px] text-ink-4">{count}</span>
      </div>
      <div
        ref={setNodeRef}
        className={`flex flex-col gap-2 bg-app-2 rounded-[10px] p-2 min-h-[80px] transition-colors ${
          isOver ? "ring-1 ring-[var(--con-brand)] bg-[var(--con-brand-soft,var(--con-bg-2))]" : ""
        }`}
      >
        {children}
      </div>
    </div>
  );
}

function TaskCard({
  task,
  onClick,
  draggable = false,
  dragOverlay = false,
}: {
  task: SprintTask;
  onClick?: () => void;
  draggable?: boolean;
  dragOverlay?: boolean;
}) {
  const drag = useDraggable({ id: task.id, disabled: !draggable });
  const style: React.CSSProperties = drag.transform
    ? {
        transform: `translate3d(${drag.transform.x}px, ${drag.transform.y}px, 0)`,
        opacity: drag.isDragging && !dragOverlay ? 0.4 : 1,
      }
    : {};

  const body = (
    <>
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
    </>
  );

  if (dragOverlay) {
    return (
      <div className="bg-surface border border-hx rounded-[8px] p-2.5 shadow-soft cursor-grabbing w-[244px]">
        {body}
      </div>
    );
  }

  if (draggable) {
    return (
      <div
        ref={drag.setNodeRef}
        style={style}
        className="bg-surface border border-hx rounded-[8px] p-2.5 hover:shadow-soft transition-shadow"
      >
        <div
          {...drag.listeners}
          {...drag.attributes}
          className="cursor-grab active:cursor-grabbing"
          onClick={(e) => {
            // Drag listeners swallow pointer events; treat a quiet pointerup as a click.
            if (!drag.isDragging) onClick?.();
            e.stopPropagation();
          }}
          role="button"
          tabIndex={0}
        >
          {body}
        </div>
      </div>
    );
  }

  return (
    <button
      onClick={onClick}
      className="text-left bg-surface border border-hx rounded-[8px] p-2.5 hover:shadow-soft transition-shadow"
    >
      {body}
    </button>
  );
}
