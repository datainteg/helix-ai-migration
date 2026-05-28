"use client";

/**
 * /projects/[id]/sprints/board — Sprint Planning Board.
 *
 * Premium kanban with a sprint selector pill bar above and a collapsible
 * task detail panel on the right.
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useFocusTrap } from "@/lib/use-focus-trap";
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
  LoadingState,
} from "@/components/ui";
import { AgentIcon } from "@/components/icons";
import {
  SprintKanbanBoard,
  TASK_STATUS_ACCENT,
  TASK_STATUS_LABEL,
} from "@/components/sprints";
import { useAuth } from "@/lib/auth-context";
import {
  createTask,
  fetchSprints,
  fetchActiveSprint,
  fetchTasks,
  patchTaskStatus,
  seedSprints,
  type NewTaskInput,
  type Sprint,
  type SprintTask,
  type TaskStatus,
} from "@/lib/sprints";

const RISK_TONE = { low: "ok", med: "warn", high: "err", critical: "err" } as const;
const VAL_TONE = { pass: "ok", warn: "warn", fail: "err", pending: "default" } as const;

export default function SprintBoardPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params?.id ?? "");
  const { token } = useAuth();

  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [active, setActive] = useState<Sprint | null>(null);
  const [selectedSprintId, setSelectedSprintId] = useState<string>("");
  const [tasks, setTasks] = useState<SprintTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<SprintTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [showNewTask, setShowNewTask] = useState(false);
  const [moveError, setMoveError] = useState<string | null>(null);

  const refetchTasks = useCallback(() => {
    if (!token || !selectedSprintId) return;
    fetchTasks(token, selectedSprintId)
      .then(setTasks)
      .catch(() => setTasks([]));
  }, [token, selectedSprintId]);

  const handleMove = useCallback(
    (taskId: string, newStatus: TaskStatus) => {
      if (!token) return;
      let snapshot: SprintTask[] = [];
      setTasks((curr) => {
        snapshot = curr;
        return curr.map((t) =>
          t.id === taskId ? { ...t, status: newStatus } : t,
        );
      });
      patchTaskStatus(token, taskId, newStatus).catch((err) => {
        setTasks(snapshot);
        setMoveError(
          err instanceof Error ? err.message : "Failed to move task",
        );
        setTimeout(() => setMoveError(null), 4000);
      });
    },
    [token],
  );

  useEffect(() => {
    if (!token || !projectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([
      fetchSprints(token, projectId),
      fetchActiveSprint(token, projectId),
    ])
      .then(([list, act]) => {
        setSprints(list);
        setActive(act);
        setSelectedSprintId(act?.id ?? list[0]?.id ?? "");
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, projectId]);

  useEffect(() => {
    if (!token || !selectedSprintId) {
      setTasks([]);
      return;
    }
    fetchTasks(token, selectedSprintId)
      .then(setTasks)
      .catch(() => setTasks([]));
  }, [token, selectedSprintId]);

  const tabs = useMemo(
    () => sprints.map((s) => ({ id: s.id, label: s.name, count: s.metrics.tasksTotal })),
    [sprints]
  );

  const handleTaskClick = (task: SprintTask) => setSelectedTask(task);

  const handleSeed = () => {
    if (!token || !projectId) return;
    setSeeding(true);
    seedSprints(token, projectId)
      .then(() => {
        if (typeof window !== "undefined") window.location.reload();
      })
      .catch(() => setSeeding(false));
  };

  if (loading) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectId}`}
        title="Sprint planning board"
        crumbs={["Projects", projectId, "Sprints", "Board"]}
      >
        <LoadingState />
      </AppShell>
    );
  }

  if (sprints.length === 0 || !active) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectId}`}
        title="Sprint planning board"
        crumbs={["Projects", projectId, "Sprints", "Board"]}
      >
        <Card>
          <EmptyState
            title="No active sprint"
            description="Start a sprint or run the seed to populate demo data."
            action={
              <Button variant="primary" loading={seeding} onClick={handleSeed}>
                Run seed
              </Button>
            }
          />
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell
      eyebrow={`SPRINTS · ${projectId}`}
      title="Sprint planning board"
      description="Migration-specific kanban with agent assignments, validation and recon signals."
      crumbs={["Projects", projectId, "Sprints", "Board"]}
      actions={
        <>
          <Button
            variant="outline"
            onClick={() => setShowNewTask(true)}
            disabled={!selectedSprintId}
          >
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

      {moveError && (
        <div className="mb-3 rounded-[8px] border border-hx bg-[var(--con-err-soft)] px-3 py-2 text-[12px] text-err">
          {moveError}
        </div>
      )}

      {/* ── Board + detail panel ────────────────────────────────── */}
      <div className="grid grid-cols-12 gap-4">
        <div className={selectedTask ? "col-span-12 xl:col-span-9" : "col-span-12"}>
          <Card padding="sm" bodyClassName="p-0">
            <div className="p-3">
              <SprintKanbanBoard
                tasks={tasks}
                onTaskClick={handleTaskClick}
                onMove={handleMove}
              />
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

      {showNewTask && selectedSprintId && (
        <NewTaskModal
          onClose={() => setShowNewTask(false)}
          onCreated={() => {
            setShowNewTask(false);
            refetchTasks();
          }}
          onSubmit={(form) =>
            createTask(token, selectedSprintId, form).then(() => undefined)
          }
        />
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
                <span className="ml-1 text-[10.5px] text-ink-3 font-mono">AGENT</span>
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

// ── New Task Modal ───────────────────────────────────────────────

const TASK_TYPES: SprintTask["type"][] = [
  "migration", "validation", "recon", "code_review",
  "notebook", "schema_mapping", "data_profiling", "qa",
];

const PRIORITIES: SprintTask["priority"][] = ["P0", "P1", "P2", "P3"];

const AI_AGENTS = ["", "Mary", "John", "Sally", "Winston", "Amelia", "Paige"];

const RISK_LEVELS: SprintTask["riskLevel"][] = ["low", "med", "high", "critical"];

function NewTaskModal({
  onClose,
  onCreated,
  onSubmit,
}: {
  onClose: () => void;
  onCreated: () => void;
  onSubmit: (input: NewTaskInput) => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  useFocusTrap(dialogRef, true, onClose);
  const [title, setTitle] = useState("");
  const [type, setType] = useState<SprintTask["type"]>("migration");
  const [priority, setPriority] = useState<SprintTask["priority"]>("P2");
  const [storyPoints, setStoryPoints] = useState<number>(3);
  const [ownerName, setOwnerName] = useState("");
  const [aiAgent, setAiAgent] = useState<string>("");
  const [riskLevel, setRiskLevel] = useState<SprintTask["riskLevel"]>("low");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const baseId = useId();
  const titleFieldId = `${baseId}-title`;
  const typeId = `${baseId}-type`;
  const priorityId = `${baseId}-priority`;
  const storyPointsId = `${baseId}-pts`;
  const riskId = `${baseId}-risk`;
  const ownerId = `${baseId}-owner`;
  const agentId = `${baseId}-agent`;

  // Escape close is owned by useFocusTrap above — no per-modal listener.

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const payload: NewTaskInput = {
        title: title.trim(),
        type,
        priority,
        story_points: Number.isFinite(storyPoints) ? storyPoints : 3,
        risk_level: riskLevel,
        ...(ownerName.trim() ? { owner_name: ownerName.trim() } : {}),
        ...(aiAgent ? { ai_agent: aiAgent } : {}),
      };
      await onSubmit(payload);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create task");
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-task-title"
        tabIndex={-1}
        className="w-full max-w-md outline-none"
      >
        <Card
          eyebrow={
            <div className="flex items-center justify-between gap-2">
              <span id="new-task-title">NEW TASK</span>
              <button
                type="button"
                onClick={onClose}
                className="text-ink-4 hover:text-ink-2 transition-colors"
                aria-label="Close"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          }
          title="Create a task"
        >
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label htmlFor={titleFieldId} className="eyebrow text-[10px] mb-1 block">
                TITLE <span aria-hidden className="text-err">*</span>
                <span className="sr-only">(required)</span>
              </label>
              <input
                id={titleFieldId}
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                autoFocus
                required
                aria-required
                className="w-full h-8 px-2.5 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring"
                placeholder="Convert customer DDL to Snowflake"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label htmlFor={typeId} className="eyebrow text-[10px] mb-1 block">TYPE</label>
                <select
                  id={typeId}
                  value={type}
                  onChange={(e) => setType(e.target.value as SprintTask["type"])}
                  className="w-full h-8 px-2 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring"
                >
                  {TASK_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={priorityId} className="eyebrow text-[10px] mb-1 block">PRIORITY</label>
                <select
                  id={priorityId}
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as SprintTask["priority"])}
                  className="w-full h-8 px-2 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring"
                >
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label htmlFor={storyPointsId} className="eyebrow text-[10px] mb-1 block">STORY POINTS</label>
                <input
                  id={storyPointsId}
                  type="number"
                  min={0}
                  max={100}
                  value={storyPoints}
                  onChange={(e) => setStoryPoints(Number(e.target.value))}
                  className="w-full h-8 px-2.5 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring"
                />
              </div>
              <div>
                <label htmlFor={riskId} className="eyebrow text-[10px] mb-1 block">RISK</label>
                <select
                  id={riskId}
                  value={riskLevel}
                  onChange={(e) => setRiskLevel(e.target.value as SprintTask["riskLevel"])}
                  className="w-full h-8 px-2 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring"
                >
                  {RISK_LEVELS.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label htmlFor={ownerId} className="eyebrow text-[10px] mb-1 block">OWNER (optional)</label>
              <input
                id={ownerId}
                type="text"
                value={ownerName}
                onChange={(e) => setOwnerName(e.target.value)}
                className="w-full h-8 px-2.5 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring"
                placeholder="e.g. Alex Chen"
              />
            </div>
            <div>
              <label htmlFor={agentId} className="eyebrow text-[10px] mb-1 block">AI AGENT</label>
              <select
                id={agentId}
                value={aiAgent}
                onChange={(e) => setAiAgent(e.target.value)}
                className="w-full h-8 px-2 text-[12.5px] rounded-[8px] border border-hx bg-surface text-ink focus-ring"
              >
                {AI_AGENTS.map((a) => (
                  <option key={a || "none"} value={a}>
                    {a || "— none —"}
                  </option>
                ))}
              </select>
            </div>
            {error && (
              <div role="alert" aria-live="assertive" className="rounded-[8px] border border-hx bg-[var(--con-err-soft)] px-3 py-2 text-[11.5px] text-err">
                {error}
              </div>
            )}
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" loading={saving}>
                Create task
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
