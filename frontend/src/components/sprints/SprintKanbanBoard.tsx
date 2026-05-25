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
 *
 * Accessibility:
 *   - KeyboardSensor activates DnD with Space/Enter on the focused card,
 *     arrow keys move the drag cursor between columns, Escape cancels.
 *   - Each card also exposes a "Move to…" menu so keyboard-only users can
 *     pick the destination column directly (no spatial reasoning required).
 *   - Drag start, over, end, and cancel announcements feed a polite aria-live
 *     region so screen readers narrate every move.
 */

import React, { useState } from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";

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
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
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

  // Screen-reader announcements for every DnD lifecycle event. dnd-kit pipes
  // each string into the LiveRegion it renders inside DndContext.
  const labelFor = (id: string | number) => {
    const t = tasks.find((x) => x.id === String(id));
    return t ? `${t.id}: ${t.title}` : String(id);
  };
  const columnFor = (id: string | number) => TASK_STATUS_LABEL[String(id) as TaskStatus] ?? String(id);
  const announcements: Announcements = {
    onDragStart({ active }) {
      return `Picked up task ${labelFor(active.id)}. Use arrow keys to move it, Space or Enter to drop it, Escape to cancel.`;
    },
    onDragOver({ active, over }) {
      if (over) return `Task ${labelFor(active.id)} is over column ${columnFor(over.id)}.`;
      return `Task ${labelFor(active.id)} is no longer over a column.`;
    },
    onDragEnd({ active, over }) {
      if (over) return `Task ${labelFor(active.id)} dropped on column ${columnFor(over.id)}.`;
      return `Task ${labelFor(active.id)} dropped; no destination column.`;
    },
    onDragCancel({ active }) {
      return `Move cancelled for task ${labelFor(active.id)}.`;
    },
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
                  onMove={onMove}
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
    <DndContext
      sensors={sensors}
      accessibility={{ announcements }}
      onDragStart={handleStart}
      onDragEnd={handleEnd}
    >
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
          <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: TASK_STATUS_ACCENT[status] }} />
          <span className="text-[11.5px] font-medium text-ink">{TASK_STATUS_LABEL[status]}</span>
        </div>
        <span className="font-mono text-[11px] text-ink-4">{count}</span>
      </div>
      <div
        ref={setNodeRef}
        aria-label={`${TASK_STATUS_LABEL[status]} column, ${count} task${count === 1 ? "" : "s"}`}
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
  onMove,
}: {
  task: SprintTask;
  onClick?: () => void;
  draggable?: boolean;
  dragOverlay?: boolean;
  onMove?: (taskId: string, newStatus: TaskStatus) => void;
}) {
  const drag = useDraggable({ id: task.id, disabled: !draggable });
  const [menuOpen, setMenuOpen] = useState(false);
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
          <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: RISK_DOT[task.riskLevel] }} />
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
    const ariaLabel = `Task ${task.id}: ${task.title}. Priority ${task.priority}. Status ${TASK_STATUS_LABEL[task.status]}. Press Space or Enter to start dragging.`;
    return (
      <div
        ref={drag.setNodeRef}
        style={style}
        className="bg-surface border border-hx rounded-[8px] p-2.5 hover:shadow-soft transition-shadow relative"
      >
        <div
          {...drag.listeners}
          {...drag.attributes}
          aria-label={ariaLabel}
          aria-roledescription="draggable task card"
          className="cursor-grab active:cursor-grabbing focus-ring rounded-[6px]"
          onClick={(e) => {
            // Drag listeners swallow pointer events; treat a quiet pointerup as a click.
            if (!drag.isDragging) onClick?.();
            e.stopPropagation();
          }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            // Space/Enter without an active drag = activate the card click.
            // dnd-kit's KeyboardSensor takes over once dragging starts.
            if ((e.key === "Enter") && !drag.isDragging) {
              e.preventDefault();
              onClick?.();
            }
          }}
        >
          {body}
        </div>
        {/* Keyboard-only fallback: explicit "Move to..." menu so SR users
            don't have to estimate spatial column distances. Triggers the
            same onMove path the drag end uses. */}
        {onMove && (
          <div className="absolute top-1.5 right-1.5">
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label={`Move task ${task.id} to a different column`}
              onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
              className="grid place-items-center h-6 w-6 rounded text-ink-4 hover:text-ink-2 hover:bg-app-2 opacity-0 focus:opacity-100 group-hover:opacity-100 transition-opacity"
              style={{ opacity: menuOpen ? 1 : undefined }}
            >
              <span aria-hidden className="text-[14px] leading-none">…</span>
            </button>
            {menuOpen && (
              <div
                role="menu"
                aria-label={`Move ${task.id} to`}
                className="absolute right-0 mt-1 w-44 bg-surface border border-hx rounded-md shadow-md py-1 z-20"
              >
                {COLUMNS.filter((c) => c !== task.status).map((c) => (
                  <button
                    key={c}
                    role="menuitem"
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onMove(task.id, c);
                      setMenuOpen(false);
                    }}
                    className="w-full text-left px-2.5 py-1.5 text-[12px] text-ink-2 hover:bg-app-2 focus-ring"
                  >
                    {TASK_STATUS_LABEL[c]}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <button
      onClick={onClick}
      className="text-left bg-surface border border-hx rounded-[8px] p-2.5 hover:shadow-soft transition-shadow focus-ring"
    >
      {body}
    </button>
  );
}
