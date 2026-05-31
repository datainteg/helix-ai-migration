"use client";

/**
 * /projects/[id]/sprints/dependencies — Task Dependency Graph.
 *
 * Inline React Flow render of every task in the active sprint with edges
 * derived from `dependencyIds`. A right-rail summarizes critical path
 * (P0 count, blocked count, completion ratio) and lists blocked task titles.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import ReactFlow, {
  Background, BackgroundVariant, Controls,
  type Edge, type Node, type NodeProps, Handle, Position,
} from "reactflow";
import "reactflow/dist/style.css";
import { AlertTriangle, CheckCircle2, Circle } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, Chip, EmptyState, LoadingState } from "@/components/ui";
import { AgentIcon } from "@/components/icons";
import { useAuth } from "@/lib/auth-context";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import {
  fetchActiveSprint,
  fetchTasks,
  seedSprints,
  type Priority,
  type Sprint,
  type SprintTask,
  type TaskStatus,
} from "@/lib/sprints";

// Status → column index for auto-layout.
const STATUS_COL: Record<TaskStatus, number> = {
  backlog:       0,
  ready:         0,
  in_progress:   1,
  ai_processing: 2,
  human_review:  3,
  validation:    3,
  recon:         4,
  qa:            4,
  approved:      5,
  completed:     5,
  blocked:       2,
};

const STATUS_ACCENT: Record<TaskStatus, string> = {
  backlog:       "var(--con-ink-5)",
  ready:         "var(--con-info)",
  in_progress:   "var(--con-brand)",
  ai_processing: "#8B5CF6",
  human_review:  "var(--con-warn)",
  validation:    "var(--con-info)",
  recon:         "var(--con-info)",
  qa:            "var(--con-warn)",
  approved:      "var(--con-ok)",
  completed:     "var(--con-ok)",
  blocked:       "var(--con-err)",
};

const PRIORITY_BG: Record<Priority, { bg: string; fg: string }> = {
  P0: { bg: "var(--con-err-soft)",  fg: "var(--con-err)" },
  P1: { bg: "var(--con-warn-soft)", fg: "var(--con-warn)" },
  P2: { bg: "var(--con-info-soft)", fg: "var(--con-info)" },
  P3: { bg: "var(--con-bg-2)",      fg: "var(--con-ink-3)" },
};

// React Flow custom node — small task chip.
function TaskNode({ data }: NodeProps<SprintTask>) {
  const accent = STATUS_ACCENT[data.status];
  const truncated = data.title.length > 30 ? data.title.slice(0, 30) + "…" : data.title;
  return (
    <div
      className="bg-surface border border-hx rounded-[8px] shadow-xs w-[200px]"
      style={{ boxShadow: `0 0 0 1px var(--con-line), inset 3px 0 0 0 ${accent}` }}
    >
      <Handle type="target" position={Position.Left} style={{ background: accent, border: "none", width: 5, height: 5 }} />
      <div className="px-2.5 pt-2 pb-1.5 flex items-start justify-between gap-1.5">
        <div className="min-w-0">
          <div className="font-mono text-[9.5px] text-ink-4">{data.id}</div>
          <div className="text-[11.5px] font-medium text-ink mt-0.5 leading-snug">{truncated}</div>
        </div>
        {data.aiAgent && <AgentIcon name={data.aiAgent} size={16} />}
      </div>
      <div className="px-2.5 pb-2 flex items-center justify-between">
        <span
          className="inline-flex items-center px-1.5 py-0.5 rounded text-[9.5px] font-mono font-medium"
          style={{ background: PRIORITY_BG[data.priority].bg, color: PRIORITY_BG[data.priority].fg }}
        >
          {data.priority}
        </span>
        <span className="text-[9.5px] capitalize text-ink-3" style={{ color: accent }}>
          {data.status.replace(/_/g, " ")}
        </span>
      </div>
      <Handle type="source" position={Position.Right} style={{ background: accent, border: "none", width: 5, height: 5 }} />
    </div>
  );
}

const NODE_TYPES = { task: TaskNode };

export default function SprintDependenciesPage() {
  const projectKey = String(useParams<{ id: string }>().id);
  const { id } = useProjectKey(projectKey);
  const { token } = useAuth();

  const [active, setActive] = useState<Sprint | null>(null);
  const [tasks, setTasks] = useState<SprintTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(() => {
    if (!token || !id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchActiveSprint(token, id)
      .then(setActive)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!token || !active) {
      setTasks([]);
      return;
    }
    fetchTasks(token, active.id)
      .then(setTasks)
      .catch(() => setTasks([]));
  }, [token, active]);

  const { rfNodes, rfEdges } = useMemo(() => {
    // Build columns by status; row = ordinal within column.
    const byCol = new Map<number, SprintTask[]>();
    tasks.forEach((t) => {
      const col = STATUS_COL[t.status] ?? 0;
      if (!byCol.has(col)) byCol.set(col, []);
      byCol.get(col)!.push(t);
    });
    const COL_W = 240;
    const ROW_H = 110;
    const PAD_X = 20;
    const PAD_Y = 20;
    const idIndex = new Map<string, SprintTask>();
    tasks.forEach((t) => idIndex.set(t.id, t));

    const nodes: Node[] = [];
    byCol.forEach((rows, col) => {
      rows.forEach((t, i) => {
        nodes.push({
          id: t.id,
          position: { x: PAD_X + col * COL_W, y: PAD_Y + i * ROW_H },
          type: "task",
          data: t,
          draggable: false,
        });
      });
    });

    const edges: Edge[] = [];
    tasks.forEach((t) => {
      t.dependencyIds.forEach((depId) => {
        const dep = idIndex.get(depId);
        if (!dep) return;
        const blocked = t.status === "blocked" || dep.status === "blocked";
        edges.push({
          id: `${depId}->${t.id}`,
          source: depId,
          target: t.id,
          type: "smoothstep",
          animated: !blocked && t.status === "in_progress",
          style: {
            stroke: blocked ? "var(--con-err)" : "var(--con-line-2)",
            strokeWidth: blocked ? 1.5 : 1,
            strokeDasharray: blocked ? "4 3" : undefined,
          },
        });
      });
    });
    return { rfNodes: nodes, rfEdges: edges };
  }, [tasks]);

  const handleSeed = () => {
    if (!token || !id) return;
    setSeeding(true);
    seedSprints(token, id)
      .then(() => {
        load();
      })
      .catch(() => {})
      .finally(() => setSeeding(false));
  };

  if (loading) {
    return (
      <AppShell
        eyebrow={`SPRINT DEPENDENCIES · ${projectKey}`}
        title="Task Dependency Graph"
        crumbs={["Projects", projectKey, "Sprints", "Dependencies"]}
      >
        <LoadingState />
      </AppShell>
    );
  }

  if (!active) {
    return (
      <AppShell
        eyebrow={`SPRINT DEPENDENCIES · ${projectKey}`}
        title="Task Dependency Graph"
        crumbs={["Projects", projectKey, "Sprints", "Dependencies"]}
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

  const p0Count        = tasks.filter((t) => t.priority === "P0").length;
  const blockedTasks   = tasks.filter((t) => t.status === "blocked");
  const completedCount = tasks.filter((t) => t.status === "completed").length;

  return (
    <AppShell
      eyebrow={`SPRINT DEPENDENCIES · ${projectKey}`}
      title="Task Dependency Graph"
      description={`Dependencies across ${tasks.length} tasks in ${active.name}.`}
      crumbs={["Projects", projectKey, "Sprints", "Dependencies"]}
    >
      {/* Legend */}
      <div className="flex items-center gap-5 mb-3 text-[11.5px]">
        <LegendDot label="Critical path"   color="var(--con-err)" />
        <LegendDot label="Blocked"         color="var(--con-err)" dashed />
        <LegendDot label="Normal"          color="var(--con-line-2)" />
        <span className="ml-auto font-mono text-[10.5px] text-ink-4">
          {rfNodes.length} tasks · {rfEdges.length} edges
        </span>
      </div>

      <div className="grid grid-cols-[1fr_280px] gap-4">
        {/* Canvas */}
        <div
          className="bg-surface border border-hx rounded-[10px] overflow-hidden"
          style={{ height: 680 }}
        >
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            nodeTypes={NODE_TYPES}
            fitView
            fitViewOptions={{ padding: 0.15, maxZoom: 1.1 }}
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={true}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="rgba(10,10,10,0.05)" />
            <Controls position="bottom-right" showInteractive={false} />
          </ReactFlow>
        </div>

        {/* Right rail */}
        <div className="flex flex-col gap-4">
          <Card title="Critical path" eyebrow="SUMMARY">
            <Row icon={<AlertTriangle className="h-3.5 w-3.5 text-err" />} label="P0 tasks"          value={p0Count} />
            <Row icon={<AlertTriangle className="h-3.5 w-3.5 text-err" />} label="Blocked"           value={blockedTasks.length} />
            <Row icon={<CheckCircle2 className="h-3.5 w-3.5 text-ok" />}  label="Completed / total" value={`${completedCount}/${tasks.length}`} />
          </Card>

          <Card title="Blocked tasks" eyebrow="ATTENTION">
            {blockedTasks.length === 0 ? (
              <p className="text-[12px] text-ink-3">No blocked tasks. Sprint is unblocked.</p>
            ) : (
              <div className="space-y-3">
                {blockedTasks.map((t) => (
                  <div key={t.id} className="border-l-2 border-[var(--con-err)] pl-2.5">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Chip tone="err" mono>{t.priority}</Chip>
                      <span className="font-mono text-[10px] text-ink-4">{t.id}</span>
                    </div>
                    <div className="text-[12px] font-medium text-ink leading-snug">{t.title}</div>
                    {t.blockedReason && (
                      <div className="text-[10.5px] text-ink-3 mt-1 leading-snug">
                        <span className="text-ink-4 font-mono uppercase text-[9.5px] mr-1">Reason</span>
                        {t.blockedReason}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

function LegendDot({ label, color, dashed }: { label: string; color: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-ink-3">
      <svg width="18" height="6" viewBox="0 0 18 6">
        <line
          x1="0" y1="3" x2="18" y2="3"
          stroke={color}
          strokeWidth="1.6"
          strokeDasharray={dashed ? "4 3" : undefined}
        />
      </svg>
      {label}
    </span>
  );
}

function Row({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-hx last:border-b-0">
      <div className="grid place-items-center h-5 w-5 rounded-md bg-app-2">{icon ?? <Circle className="h-3 w-3 text-ink-4" />}</div>
      <span className="text-[12px] text-ink-2">{label}</span>
      <span className="ml-auto font-mono tabular-nums text-[13px] font-medium text-ink">{value}</span>
    </div>
  );
}
