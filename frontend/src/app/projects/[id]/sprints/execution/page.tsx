"use client";

/**
 * /projects/[id]/sprints/execution — Sprint Execution View.
 *
 * Live execution dashboard for agent runs. Surfaces: counts strip, active
 * runs, failed queue (with retry), and blocked workflows from sprint tasks.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { RefreshCw, Pause, AlertTriangle, RotateCw } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, Chip, EmptyState, LoadingState, MetricCell } from "@/components/ui";
import { AgentIcon } from "@/components/icons";
import { useAuth } from "@/lib/auth-context";
import {
  fetchActiveSprint,
  fetchTasks,
  seedSprints,
  subscribeToExecutions,
  type AgentExecution,
  type Sprint,
  type SprintTask,
} from "@/lib/sprints";

const STATUS_TONE = {
  running:    { bg: "var(--con-info-soft)", fg: "var(--con-info)" },
  succeeded:  { bg: "var(--con-ok-soft)",   fg: "var(--con-ok)" },
  failed:     { bg: "var(--con-err-soft)",  fg: "var(--con-err)" },
  retrying:   { bg: "var(--con-warn-soft)", fg: "var(--con-warn)" },
  queued:     { bg: "var(--con-bg-2)",      fg: "var(--con-ink-3)" },
  cancelled:  { bg: "var(--con-bg-2)",      fg: "var(--con-ink-3)" },
} satisfies Record<AgentExecution["status"], { bg: string; fg: string }>;

const STATUS_LABEL: Record<AgentExecution["status"], string> = {
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  retrying: "Retrying",
  queued: "Queued",
  cancelled: "Cancelled",
};

function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}m ${r}s`;
}

function formatStarted(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function SprintExecutionPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params?.id ?? "");
  const { token } = useAuth();

  const [executions, setExecutions] = useState<AgentExecution[]>([]);
  const [active, setActive] = useState<Sprint | null>(null);
  const [tasks, setTasks] = useState<SprintTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [streamLive, setStreamLive] = useState(false);

  // Active sprint lookup is a one-shot fetch (independent of the SSE stream).
  const loadActive = useCallback(() => {
    if (!token || !projectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchActiveSprint(token, projectId)
      .then((act) => setActive(act))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, projectId]);

  useEffect(() => {
    loadActive();
  }, [loadActive]);

  // SSE execution stream — replaces the prior single-fetch.
  useEffect(() => {
    if (!token || !projectId) {
      setStreamLive(false);
      return;
    }
    let es: EventSource | null = null;
    let cancelled = false;
    subscribeToExecutions(
      token,
      projectId,
      (rows) => {
        setExecutions(rows);
        setStreamLive(true);
      },
      () => {
        setStreamLive(false);
      },
    ).then((handle) => {
      if (cancelled) {
        handle?.close();
        return;
      }
      es = handle;
      if (!handle) setStreamLive(false);
    });
    return () => {
      cancelled = true;
      es?.close();
      setStreamLive(false);
    };
  }, [token, projectId]);

  useEffect(() => {
    if (!token || !active) {
      setTasks([]);
      return;
    }
    fetchTasks(token, active.id)
      .then(setTasks)
      .catch(() => setTasks([]));
  }, [token, active]);

  const counts = useMemo(() => {
    return {
      running:   executions.filter((e) => e.status === "running" || e.status === "queued").length,
      succeeded: executions.filter((e) => e.status === "succeeded").length,
      failed:    executions.filter((e) => e.status === "failed").length,
      retrying:  executions.filter((e) => e.status === "retrying").length,
    };
  }, [executions]);

  const handleSeed = () => {
    if (!token || !projectId) return;
    setSeeding(true);
    seedSprints(token, projectId)
      .then(() => {
        loadActive();
      })
      .catch(() => {})
      .finally(() => setSeeding(false));
  };

  if (loading) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectId}`}
        title="Sprint execution"
        crumbs={["Projects", projectId, "Sprints", "Execution"]}
      >
        <LoadingState />
      </AppShell>
    );
  }

  if (!active) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectId}`}
        title="Sprint execution"
        crumbs={["Projects", projectId, "Sprints", "Execution"]}
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

  const activeRuns = executions.filter((e) =>
    ["running", "retrying", "queued"].includes(e.status)
  );
  const completed = executions.filter((e) => e.status === "succeeded");
  const failedRuns = executions.filter((e) => e.status === "failed");
  const blockedTasks = tasks.filter((t) => t.status === "blocked").slice(0, 3);

  return (
    <AppShell
      eyebrow={`SPRINTS · ${projectId}`}
      title="Sprint execution"
      description="Live agent runs, retries, failed queue, and blocked workflows for the active sprint."
      crumbs={["Projects", projectId, "Sprints", "Execution"]}
      actions={
        <>
          {streamLive ? (
            <span className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-[7px] bg-[var(--con-ok-soft)] text-ok text-[11.5px] font-medium">
              <span
                className="h-1.5 w-1.5 rounded-full animate-pulse-dot"
                style={{ background: "var(--con-ok)" }}
              />
              Live
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-[7px] bg-[var(--con-warn-soft)] text-warn text-[11.5px] font-medium">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: "var(--con-warn)" }}
              />
              Disconnected
            </span>
          )}
          <Button variant="outline">
            <Pause className="h-4 w-4" /> Pause queue
          </Button>
          <Button variant="primary">
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        </>
      }
    >
      {/* ── Status strip ────────────────────────────────────────── */}
      <div className="grid grid-cols-4 bg-surface border border-hx rounded-[10px] divide-x divide-hx mb-6">
        <MetricCell big label="Running" value={counts.running} hint="Active + queued" accent="var(--con-info)" />
        <MetricCell big label="Succeeded" value={counts.succeeded} hint="This window" accent="var(--con-ok)" />
        <MetricCell big label="Failed" value={counts.failed} hint="Needs attention" accent="var(--con-err)" />
        <MetricCell big label="Retrying" value={counts.retrying} hint="In-flight retries" accent="var(--con-warn)" />
      </div>

      {/* ── Active runs ─────────────────────────────────────────── */}
      <Card
        title="Active runs"
        eyebrow="LIVE"
        className="mb-4"
        actions={<span className="font-mono text-[11px] text-ink-4">{activeRuns.length}</span>}
      >
        {activeRuns.length === 0 ? (
          <p className="text-[12px] text-ink-3">No active runs.</p>
        ) : (
          <div className="space-y-2">
            {activeRuns.map((e) => (
              <AgentExecutionCard key={e.id} execution={e} />
            ))}
          </div>
        )}
      </Card>

      {/* ── Completed (recent) ──────────────────────────────────── */}
      {completed.length > 0 && (
        <Card
          title="Completed"
          eyebrow="RECENT"
          className="mb-4"
          actions={<span className="font-mono text-[11px] text-ink-4">{completed.length}</span>}
        >
          <div className="space-y-2">
            {completed.map((e) => (
              <AgentExecutionCard key={e.id} execution={e} />
            ))}
          </div>
        </Card>
      )}

      {/* ── Failed queue ────────────────────────────────────────── */}
      <Card
        title="Failed queue"
        eyebrow="NEEDS RETRY"
        className="mb-4"
        actions={
          <Button variant="outline" size="sm">
            <RotateCw className="h-3.5 w-3.5" /> Retry all
          </Button>
        }
      >
        {failedRuns.length === 0 ? (
          <p className="text-[12px] text-ink-3">No failed runs.</p>
        ) : (
          <div className="space-y-2">
            {failedRuns.map((e) => (
              <AgentExecutionCard key={e.id} execution={e} />
            ))}
          </div>
        )}
      </Card>

      {/* ── Blocked workflows ───────────────────────────────────── */}
      <Card
        title="Blocked workflows"
        eyebrow="SPRINT TASKS"
        actions={<span className="font-mono text-[11px] text-ink-4">{blockedTasks.length}</span>}
      >
        {blockedTasks.length === 0 ? (
          <p className="text-[12px] text-ink-3">No blocked tasks in this sprint.</p>
        ) : (
          <div className="space-y-2">
            {blockedTasks.map((t) => (
              <BlockedTaskRow key={t.id} task={t} />
            ))}
          </div>
        )}
      </Card>
    </AppShell>
  );
}

// ── Reusable inline components ───────────────────────────────────

function AgentExecutionCard({ execution }: { execution: AgentExecution }) {
  const tone = STATUS_TONE[execution.status];
  const isFailed = execution.status === "failed";
  const isRunning = execution.status === "running" || execution.status === "retrying";

  return (
    <div className="bg-surface border border-hx rounded-[10px] p-3 shadow-xs">
      <div className="flex items-center gap-3">
        {/* Agent icon */}
        <AgentIcon name={execution.agentCode} size={28} />

        {/* Center: task + log */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="font-mono text-[11px] text-ink-3">{execution.taskId}</span>
            <Chip tone={execution.mode === "llm" ? "brand" : "default"} mono>
              {execution.mode}
            </Chip>
            {execution.retries > 0 && (
              <span className="font-mono text-[10.5px] text-ink-4">
                retry {execution.retries}
              </span>
            )}
          </div>
          <div className="text-[12.5px] text-ink-2 truncate">{execution.log}</div>
        </div>

        {/* Right: status + meta */}
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <span
            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium"
            style={{ background: tone.bg, color: tone.fg }}
          >
            {isRunning && (
              <span
                className="h-1.5 w-1.5 rounded-full animate-pulse-dot"
                style={{ background: tone.fg }}
              />
            )}
            {STATUS_LABEL[execution.status]}
          </span>
          <span className="font-mono text-[10.5px] text-ink-4">
            {formatStarted(execution.startedAt)} · {formatDuration(execution.durationMs)}
          </span>
        </div>

        {/* Retry action for failed */}
        {isFailed && (
          <Button variant="outline" size="sm">
            <RotateCw className="h-3.5 w-3.5" /> Retry
          </Button>
        )}
      </div>
    </div>
  );
}

function BlockedTaskRow({ task }: { task: SprintTask }) {
  return (
    <div className="bg-surface border border-hx rounded-[10px] p-3 shadow-xs">
      <div className="flex items-start gap-3">
        <div className="grid place-items-center h-8 w-8 rounded-[8px] bg-[var(--con-err-soft)] text-err flex-shrink-0">
          <AlertTriangle className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="font-mono text-[11px] text-ink-3">{task.id}</span>
            <Chip tone={task.priority === "P0" ? "err" : task.priority === "P1" ? "warn" : "info"} mono>
              {task.priority}
            </Chip>
            <Chip tone="err" dot>blocked</Chip>
          </div>
          <div className="text-[12.5px] font-medium text-ink truncate">{task.title}</div>
          {task.blockedReason && (
            <div className="mt-1 text-[11.5px] text-ink-3 leading-snug">
              <span className="text-ink-4 font-mono uppercase text-[10px] mr-1.5">Reason</span>
              {task.blockedReason}
            </div>
          )}
        </div>
        <Button variant="outline" size="sm">
          Unblock
        </Button>
      </div>
    </div>
  );
}
