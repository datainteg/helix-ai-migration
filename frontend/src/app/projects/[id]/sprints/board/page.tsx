"use client";

/**
 * /projects/[id]/sprints/board — Sprint Planning Board.
 *
 * Premium kanban with a sprint selector pill bar above and a collapsible
 * task detail panel on the right.
 */

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import {
  Sparkles,
  AlertTriangle,
  Link2,
  Clock,
  Plus,
  X,
} from "lucide-react";

import { AppShell } from "@/components/layout";
import {
  Button,
  Card,
  Chip,
  Tabs,
  Avatar,
  EmptyState,
} from "@/components/ui";
import { AgentIcon } from "@/components/icons";
import {
  SprintKanbanBoard,
  TASK_STATUS_ACCENT,
  TASK_STATUS_LABEL,
} from "@/components/sprints";
import {
  getSprints,
  getTasksForSprint,
  getActiveSprint,
  PROJECT_ID,
  type SprintTask,
} from "@/lib/sprints";

const RISK_TONE = { low: "ok", med: "warn", high: "err", critical: "err" } as const;
const VAL_TONE = { pass: "ok", warn: "warn", fail: "err", pending: "default" } as const;

export default function SprintBoardPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params?.id ?? PROJECT_ID);

  const sprints = getSprints();
  const active = getActiveSprint();
  const [selectedSprintId, setSelectedSprintId] = useState<string>(active.id);
  const [selectedTask, setSelectedTask] = useState<SprintTask | null>(null);

  const tabs = useMemo(
    () => sprints.map((s) => ({ id: s.id, label: s.name, count: s.metrics.tasksTotal })),
    [sprints]
  );
  const tasks = useMemo(() => getTasksForSprint(selectedSprintId), [selectedSprintId]);

  const handleTaskClick = (task: SprintTask) => setSelectedTask(task);

  return (
    <AppShell
      eyebrow={`SPRINTS · ${projectId}`}
      title="Sprint planning board"
      description="Migration-specific kanban with agent assignments, validation and recon signals."
      crumbs={["Projects", projectId, "Sprints", "Board"]}
      actions={
        <>
          <Button variant="outline">
            <Plus className="h-4 w-4" /> New task
          </Button>
          <Button variant="primary">
            <Sparkles className="h-4 w-4" /> Auto-assign agents
          </Button>
        </>
      }
    >
      {/* ── Sprint selector ─────────────────────────────────────── */}
      <div className="mb-4 overflow-x-auto">
        <Tabs
          tabs={tabs}
          value={selectedSprintId}
          onChange={setSelectedSprintId}
          variant="pill"
        />
      </div>

      {/* ── Board + detail panel ────────────────────────────────── */}
      <div className="grid grid-cols-12 gap-4">
        <div className={selectedTask ? "col-span-12 xl:col-span-9" : "col-span-12"}>
          <Card padding="sm" bodyClassName="p-0">
            <div className="p-3">
              <SprintKanbanBoard tasks={tasks} onTaskClick={handleTaskClick} />
            </div>
          </Card>
        </div>

        {selectedTask && (
          <div className="col-span-12 xl:col-span-3">
            <TaskDetailPanel
              task={selectedTask}
              tasks={tasks}
              onClose={() => setSelectedTask(null)}
            />
          </div>
        )}
      </div>

      {!selectedTask && (
        <div className="mt-4">
          <Card>
            <EmptyState
              icon={<Sparkles className="h-4 w-4" />}
              title="Select a task to inspect"
              description="Click any card on the board to open the task detail panel."
            />
          </Card>
        </div>
      )}
    </AppShell>
  );
}

// ── Task Detail Panel ────────────────────────────────────────────

function TaskDetailPanel({
  task,
  tasks,
  onClose,
}: {
  task: SprintTask;
  tasks: SprintTask[];
  onClose: () => void;
}) {
  const dependencies = task.dependencyIds
    .map((id) => tasks.find((t) => t.id === id))
    .filter((t): t is SprintTask => Boolean(t));

  return (
    <Card
      eyebrow={
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono">{task.id}</span>
          <button
            type="button"
            onClick={onClose}
            className="text-ink-4 hover:text-ink-2 transition-colors"
            aria-label="Close panel"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: TASK_STATUS_ACCENT[task.status] }}
            />
            <span className="text-[11.5px] text-ink-3">
              {TASK_STATUS_LABEL[task.status]}
            </span>
          </div>
          <div className="text-[14px] font-semibold text-ink leading-snug">
            {task.title}
          </div>
        </div>

        {/* Owner */}
        <div>
          <div className="eyebrow text-[10px] mb-1.5">OWNER</div>
          <div className="flex items-center gap-2">
            {task.aiAgent ? (
              <AgentIcon name={task.aiAgent} size={22} />
            ) : task.owner ? (
              <Avatar name={task.owner.name} size={22} />
            ) : null}
            <div className="text-[12.5px] text-ink-2">
              {task.aiAgent ?? task.owner?.name ?? "Unassigned"}
              {task.aiAgent && (
                <span className="ml-1 text-[10.5px] text-ink-4 font-mono">AGENT</span>
              )}
            </div>
          </div>
        </div>

        {/* Priority + Story Points + Risk */}
        <div className="grid grid-cols-3 gap-2">
          <Stat label="Priority">
            <Chip tone={task.priority === "P0" ? "err" : task.priority === "P1" ? "warn" : "info"} mono>
              {task.priority}
            </Chip>
          </Stat>
          <Stat label="Points">
            <span className="font-mono text-[14px] tabular-nums text-ink">
              {task.storyPoints}
            </span>
          </Stat>
          <Stat label="Risk">
            <Chip tone={RISK_TONE[task.riskLevel]} dot>
              {task.riskLevel}
            </Chip>
          </Stat>
        </div>

        {/* Validation + Recon */}
        <div>
          <div className="eyebrow text-[10px] mb-1.5">VALIDATION & RECON</div>
          <div className="flex flex-wrap gap-1.5">
            {task.validationStatus && (
              <Chip tone={VAL_TONE[task.validationStatus]}>
                val · {task.validationStatus}
              </Chip>
            )}
            {task.reconStatus && (
              <Chip tone={VAL_TONE[task.reconStatus]}>
                rec · {task.reconStatus}
              </Chip>
            )}
          </div>
        </div>

        {/* Dependencies */}
        <div>
          <div className="eyebrow text-[10px] mb-1.5">DEPENDENCIES</div>
          {dependencies.length === 0 ? (
            <p className="text-[11.5px] text-ink-4">No upstream dependencies.</p>
          ) : (
            <ul className="space-y-1.5">
              {dependencies.map((dep) => (
                <li
                  key={dep.id}
                  className="flex items-start gap-1.5 text-[11.5px] text-ink-2"
                >
                  <Link2 className="h-3 w-3 mt-0.5 text-ink-4" />
                  <div className="min-w-0">
                    <div className="font-mono text-[10.5px] text-ink-4">{dep.id}</div>
                    <div className="truncate">{dep.title}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Estimated hours */}
        <div>
          <div className="eyebrow text-[10px] mb-1.5">EFFORT</div>
          <div className="flex items-center gap-3 text-[11.5px] text-ink-2">
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3 text-ink-4" />
              <span className="font-mono">{task.estimatedHours}h</span> est
            </span>
            {task.actualHours != null && (
              <span className="font-mono text-ink-3">{task.actualHours}h actual</span>
            )}
          </div>
        </div>

        {/* Blocked reason */}
        {task.status === "blocked" && task.blockedReason && (
          <div className="rounded-[8px] border border-hx bg-[var(--con-err-soft)] p-2.5">
            <div className="flex items-start gap-1.5 text-[11.5px] text-err">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
              <div>
                <div className="font-medium">Blocked</div>
                <div className="text-[11px] text-ink-2 mt-0.5">
                  {task.blockedReason}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <Button size="sm" variant="outline" className="flex-1 justify-center">
            Reassign
          </Button>
          <Button size="sm" variant="primary" className="flex-1 justify-center">
            Open task
          </Button>
        </div>
      </div>
    </Card>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-app-2 rounded-[8px] px-2.5 py-2">
      <div className="eyebrow text-[9.5px]">{label}</div>
      <div className="mt-1">{children}</div>
    </div>
  );
}
