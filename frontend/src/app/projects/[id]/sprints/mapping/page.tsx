"use client";

/**
 * /projects/[id]/sprints/mapping — Sprint Mapping Showcase.
 *
 * Flagship visualization. Renders the migration execution graph (React Flow
 * based) with a colour/status legend and side-panel summary statistics.
 */

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { Download, Maximize2 } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card } from "@/components/ui";
import { AgentIcon } from "@/components/icons";
import { MigrationMappingCanvas } from "@/components/sprints";
import {
  getMappingGraph,
  PROJECT_ID,
  type MappingNode as MNode,
  type MappingNodeStatus,
} from "@/lib/sprints";

const STATUS_LIST: Array<{ key: MappingNodeStatus; label: string; color: string }> = [
  { key: "completed",     label: "Completed",     color: "var(--con-ok)" },
  { key: "active",        label: "Active",        color: "var(--con-brand)" },
  { key: "ai_processing", label: "AI processing", color: "#8B5CF6" },
  { key: "review",        label: "Review",        color: "var(--con-warn)" },
  { key: "blocked",       label: "Blocked",       color: "var(--con-err)" },
  { key: "failed",        label: "Failed",        color: "var(--con-err)" },
  { key: "pending",       label: "Pending",       color: "var(--con-ink-5)" },
];

export default function SprintMappingPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params?.id ?? PROJECT_ID);

  const { nodes, edges } = getMappingGraph();

  // Aggregate counts per status
  const statusCounts = useMemo(() => {
    const map = new Map<MappingNodeStatus, number>();
    for (const n of nodes) map.set(n.status, (map.get(n.status) ?? 0) + 1);
    return STATUS_LIST.map((s) => ({ ...s, count: map.get(s.key) ?? 0 }));
  }, [nodes]);

  // Group nodes by agent
  const agentBreakdown = useMemo(() => {
    const map = new Map<string, number>();
    for (const n of nodes) {
      const k = n.agent ?? "Unassigned";
      map.set(k, (map.get(k) ?? 0) + 1);
    }
    return Array.from(map.entries())
      .map(([agent, count]) => ({ agent, count }))
      .sort((a, b) => b.count - a.count);
  }, [nodes]);

  // Top blocked paths
  const blockedPaths = useMemo(() => {
    return edges
      .filter((e) => e.status === "blocked")
      .slice(0, 3)
      .map((e) => ({
        id: e.id,
        source: nodes.find((n) => n.id === e.source)?.label ?? e.source,
        target: nodes.find((n) => n.id === e.target)?.label ?? e.target,
        label: e.label,
      }));
  }, [edges, nodes]);

  return (
    <AppShell
      eyebrow="SPRINT MAPPING SHOWCASE"
      title="Migration Execution Mapping"
      description="End-to-end execution graph — every stage from requirement intake to release deployment."
      crumbs={["Projects", projectId, "Sprints", "Mapping"]}
      actions={
        <>
          <Button variant="outline">
            <Download className="h-4 w-4" /> Export graph
          </Button>
          <Button variant="primary">
            <Maximize2 className="h-4 w-4" /> Fullscreen
          </Button>
        </>
      }
    >
      {/* ── Legend explainer card ───────────────────────────────── */}
      <Card padding="sm" className="mb-4">
        <div className="flex items-start gap-4 flex-wrap">
          <div className="eyebrow text-[10px] pt-1 min-w-[80px]">LEGEND</div>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[11.5px] text-ink-2 flex-1">
            <LegendDot color="var(--con-ok)" label="Green — Completed" />
            <LegendDot color="var(--con-warn)" label="Yellow — Review pending" />
            <LegendDot color="var(--con-err)" label="Red — Blocked / Failed" />
            <LegendDot color="var(--con-brand)" label="Blue — Active" />
            <LegendDot color="#8B5CF6" label="Purple — AI processing" />
          </div>
        </div>
      </Card>

      {/* ── Canvas + side panel ─────────────────────────────────── */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 xl:col-span-9">
          <MigrationMappingCanvas nodes={nodes} edges={edges} height={680} />
        </div>

        <aside className="col-span-12 xl:col-span-3 space-y-4" style={{ maxWidth: 320 }}>
          {/* Node status totals */}
          <Card eyebrow="STATUS BREAKDOWN" title="Nodes by status">
            <ul className="space-y-1.5">
              {statusCounts.map((s) => (
                <li
                  key={s.key}
                  className="flex items-center justify-between text-[12px]"
                >
                  <span className="flex items-center gap-2 text-ink-2">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: s.color }}
                    />
                    {s.label}
                  </span>
                  <span className="font-mono tabular-nums text-ink-3">{s.count}</span>
                </li>
              ))}
            </ul>
          </Card>

          {/* Agent assignment breakdown */}
          <Card eyebrow="AGENTS" title="Assignments">
            <ul className="space-y-1.5">
              {agentBreakdown.map((a) => (
                <li
                  key={a.agent}
                  className="flex items-center justify-between text-[12px]"
                >
                  <span className="flex items-center gap-2 text-ink-2 min-w-0">
                    {a.agent === "Unassigned" ? (
                      <span className="h-[18px] w-[18px] rounded-full bg-app-2 flex-shrink-0" />
                    ) : (
                      <AgentIcon name={a.agent} size={18} />
                    )}
                    <span className="truncate">{a.agent}</span>
                  </span>
                  <span className="font-mono tabular-nums text-ink-3">{a.count}</span>
                </li>
              ))}
            </ul>
          </Card>

          {/* Blocked paths */}
          <Card eyebrow="BLOCKED PATHS" title="Top blockers">
            {blockedPaths.length === 0 ? (
              <p className="text-[11.5px] text-ink-3">No blocked edges.</p>
            ) : (
              <ul className="space-y-2">
                {blockedPaths.map((b) => (
                  <li
                    key={b.id}
                    className="rounded-[8px] border border-hx bg-[var(--con-err-soft)] px-2.5 py-2"
                  >
                    <div className="text-[11.5px] text-ink-2 leading-snug">
                      <span className="font-medium">{b.source}</span>
                      <span className="text-ink-4 mx-1">→</span>
                      <span className="font-medium">{b.target}</span>
                    </div>
                    {b.label && (
                      <div className="mt-0.5 text-[10.5px] font-mono text-err">
                        {b.label}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </aside>
      </div>

      {/* ── Footer legend strip (all 7 statuses) ────────────────── */}
      <Card className="mt-4" eyebrow="ALL STATUSES" title="Status reference">
        <div className="flex flex-wrap gap-2">
          {STATUS_LIST.map((s) => (
            <span
              key={s.key}
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium leading-[1.45] bg-app-2 text-ink-2"
            >
              <span
                className="inline-block h-1.5 w-1.5 rounded-full"
                style={{ background: s.color }}
              />
              {s.label}
            </span>
          ))}
        </div>
      </Card>
    </AppShell>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      <span>{label}</span>
    </span>
  );
}
