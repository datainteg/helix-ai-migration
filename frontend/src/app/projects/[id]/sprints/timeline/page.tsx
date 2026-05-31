"use client";

/**
 * /projects/[id]/sprints/timeline — Sprint Timeline / Roadmap.
 *
 * Horizontal SVG gantt-style timeline. One row per sprint, milestone dots
 * overlaid, plus a separate "Migration milestones" strip with cross-sprint
 * checkpoints derived from sprint milestones / endDates.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Download, Filter } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, Chip, EmptyState, LoadingState } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { fetchSprints, seedSprints, type Sprint } from "@/lib/sprints";

const HEALTH_FILL: Record<Sprint["health"], string> = {
  "on-track":  "var(--con-ok)",
  "at-risk":   "var(--con-warn)",
  "off-track": "var(--con-err)",
  "blocked":   "var(--con-err)",
};

const HEALTH_BG: Record<Sprint["health"], string> = {
  "on-track":  "var(--con-ok-soft)",
  "at-risk":   "var(--con-warn-soft)",
  "off-track": "var(--con-err-soft)",
  "blocked":   "var(--con-err-soft)",
};

// Layout constants
const CHART_WIDTH = 1100;
const LABEL_COL_WIDTH = 200;
const TRACK_WIDTH = CHART_WIDTH - LABEL_COL_WIDTH;
const ROW_HEIGHT = 48;
const BAR_HEIGHT = 22;
const MONTH_HEADER_HEIGHT = 28;
const MILESTONE_HEADER_HEIGHT = 28;
const MIGRATION_STRIP_HEIGHT = 70;

interface MigrationCheckpoint {
  id: string;
  label: string;
  date: string;
  color: string;
}

export default function SprintTimelinePage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params?.id ?? "");
  const { token } = useAuth();

  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(() => {
    if (!token || !projectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchSprints(token, projectId)
      .then(setSprints)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, projectId]);

  useEffect(() => {
    load();
  }, [load]);

  // Compute global date range
  const range = useMemo(() => {
    if (sprints.length === 0) return { min: 0, max: 0, span: 1 };
    const starts = sprints.map((s) => new Date(s.startDate).getTime());
    const ends = sprints.map((s) => new Date(s.endDate).getTime());
    const min = Math.min(...starts);
    const max = Math.max(...ends);
    return { min, max, span: Math.max(1, max - min) };
  }, [sprints]);

  // x-coordinate within the track (relative to LABEL_COL_WIDTH offset)
  const xFor = (iso: string): number => {
    const t = new Date(iso).getTime();
    const pct = (t - range.min) / range.span;
    return Math.round(pct * TRACK_WIDTH);
  };

  // Month markers across the visible span
  const monthMarkers = useMemo(() => {
    const out: Array<{ x: number; label: string }> = [];
    if (sprints.length === 0) return out;
    const d = new Date(range.min);
    d.setUTCDate(1);
    while (d.getTime() <= range.max) {
      const t = d.getTime();
      const pct = (t - range.min) / range.span;
      const x = Math.round(pct * TRACK_WIDTH);
      out.push({
        x,
        label: d.toLocaleString("en-US", { month: "short", timeZone: "UTC" }),
      });
      d.setUTCMonth(d.getUTCMonth() + 1);
    }
    return out;
  }, [range, sprints.length]);

  // Migration-wide checkpoints derived from sprint milestones / endDates.
  // Defensive: works with any sprint count (>=1).
  const checkpoints = useMemo<MigrationCheckpoint[]>(() => {
    const s = (idx: number) => sprints[Math.min(idx, sprints.length - 1)];
    if (sprints.length === 0) return [];
    const palette = [
      "var(--con-ok)",
      "var(--con-ok)",
      "var(--con-warn)",
      "var(--con-info)",
      "var(--con-info)",
      "var(--con-brand)",
    ];
    const labels = [
      "Discovery Complete",
      "Mapping Complete",
      "Conversion Complete",
      "Validation Passed",
      "Recon Approved",
      "Production Ready",
    ];
    return labels.map((label, i) => {
      const target = s(i);
      const customMilestone = i === 3 ? target.milestones[1]?.date : undefined;
      return {
        id: `cp${i + 1}`,
        label,
        date: customMilestone ?? target.endDate,
        color: palette[i] ?? "var(--con-brand)",
      };
    });
  }, [sprints]);

  const handleSeed = () => {
    if (!token || !projectId) return;
    setSeeding(true);
    seedSprints(token, projectId)
      .then(() => {
        load();
      })
      .catch(() => {})
      .finally(() => setSeeding(false));
  };

  if (loading) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectId}`}
        title="Sprint timeline & roadmap"
        crumbs={["Projects", projectId, "Sprints", "Timeline"]}
      >
        <LoadingState />
      </AppShell>
    );
  }

  if (sprints.length === 0) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectId}`}
        title="Sprint timeline & roadmap"
        crumbs={["Projects", projectId, "Sprints", "Timeline"]}
      >
        <Card>
          <EmptyState
            title="No sprints yet"
            description="Run the seed to populate demo sprints, or create one from the API."
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

  const sprintsHeight = sprints.length * ROW_HEIGHT;
  const totalHeight =
    MONTH_HEADER_HEIGHT + sprintsHeight + MILESTONE_HEADER_HEIGHT + MIGRATION_STRIP_HEIGHT + 24;

  return (
    <AppShell
      eyebrow={`SPRINTS · ${projectId}`}
      title="Sprint timeline & roadmap"
      description="Multi-sprint gantt with migration checkpoints from discovery through production cutover."
      crumbs={["Projects", projectId, "Sprints", "Timeline"]}
      actions={
        <>
          <Button variant="outline">
            <Filter className="h-4 w-4" /> Filter
          </Button>
          <Button variant="primary">
            <Download className="h-4 w-4" /> Export
          </Button>
        </>
      }
    >
      {/* ── Legend ──────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-4 mb-4 text-[11.5px] text-ink-2">
        <span className="eyebrow text-[10px]">HEALTH</span>
        <Chip tone="ok" dot>On track</Chip>
        <Chip tone="warn" dot>At risk</Chip>
        <Chip tone="err" dot>Off track</Chip>
        <span className="ml-auto font-mono text-[11px] text-ink-4">
          {sprints.length} sprints · {Math.round(range.span / 86_400_000)} days
        </span>
      </div>

      {/* ── Timeline chart ─────────────────────────────────────── */}
      <Card padding="sm" bodyClassName="p-0">
        <div className="overflow-x-auto">
          <svg
            width="100%"
            height={totalHeight}
            viewBox={`0 0 ${CHART_WIDTH} ${totalHeight}`}
            preserveAspectRatio="xMinYMin meet"
            className="block"
            style={{ minWidth: CHART_WIDTH }}
            role="img"
            aria-label="Sprint timeline"
          >
            {/* Month markers */}
            <g>
              {monthMarkers.map((m, i) => (
                <g key={i}>
                  <line
                    x1={LABEL_COL_WIDTH + m.x}
                    y1={MONTH_HEADER_HEIGHT - 4}
                    x2={LABEL_COL_WIDTH + m.x}
                    y2={MONTH_HEADER_HEIGHT + sprintsHeight}
                    stroke="var(--con-line)"
                    strokeDasharray="2 4"
                  />
                  <text
                    x={LABEL_COL_WIDTH + m.x + 4}
                    y={16}
                    fontSize="11"
                    fill="var(--con-ink-3)"
                    fontFamily="Geist Mono"
                    fontWeight="600"
                  >
                    {m.label}
                  </text>
                </g>
              ))}
              <line
                x1={LABEL_COL_WIDTH}
                y1={MONTH_HEADER_HEIGHT - 0.5}
                x2={CHART_WIDTH}
                y2={MONTH_HEADER_HEIGHT - 0.5}
                stroke="var(--con-line)"
              />
            </g>

            {/* Sprint rows */}
            <g transform={`translate(0, ${MONTH_HEADER_HEIGHT})`}>
              {sprints.map((s, i) => {
                const x = xFor(s.startDate);
                const w = Math.max(8, xFor(s.endDate) - x);
                const cy = i * ROW_HEIGHT + ROW_HEIGHT / 2;
                return (
                  <g key={s.id}>
                    {/* Row label */}
                    <text
                      x={12}
                      y={cy - 4}
                      fontSize="12"
                      fill="var(--con-ink-1)"
                      fontWeight="600"
                    >
                      {s.name.length > 28 ? s.name.slice(0, 26) + "…" : s.name}
                    </text>
                    <text
                      x={12}
                      y={cy + 10}
                      fontSize="10"
                      fill="var(--con-ink-4)"
                      fontFamily="Geist Mono"
                    >
                      {s.startDate.slice(0, 10)} → {s.endDate.slice(0, 10)}
                    </text>

                    {/* Row baseline */}
                    <line
                      x1={LABEL_COL_WIDTH}
                      y1={cy + 0.5}
                      x2={CHART_WIDTH}
                      y2={cy + 0.5}
                      stroke="var(--con-line)"
                    />

                    {/* Sprint bar */}
                    <rect
                      x={LABEL_COL_WIDTH + x}
                      y={cy - BAR_HEIGHT / 2}
                      width={w}
                      height={BAR_HEIGHT}
                      rx={4}
                      fill={HEALTH_BG[s.health]}
                      stroke={HEALTH_FILL[s.health]}
                      strokeWidth="1"
                    />
                    {/* Progress overlay */}
                    {(() => {
                      const denom = s.metrics.storyPointsTotal || 1;
                      const pct = s.metrics.storyPointsDone / denom;
                      const pw = Math.max(0, Math.round(w * pct));
                      return (
                        <rect
                          x={LABEL_COL_WIDTH + x}
                          y={cy - BAR_HEIGHT / 2}
                          width={pw}
                          height={BAR_HEIGHT}
                          rx={4}
                          fill={HEALTH_FILL[s.health]}
                          opacity={0.65}
                        />
                      );
                    })()}

                    {/* Milestone dots */}
                    {s.milestones.map((m) => (
                      <g key={m.id} transform={`translate(${LABEL_COL_WIDTH + xFor(m.date)}, ${cy})`}>
                        <circle
                          r={4.5}
                          fill={m.status === "done" ? "var(--con-ok)" : m.status === "in_progress" ? "var(--con-brand)" : "var(--con-surface)"}
                          stroke={m.status === "done" ? "var(--con-ok)" : m.status === "in_progress" ? "var(--con-brand)" : "var(--con-ink-4)"}
                          strokeWidth="1.5"
                        />
                      </g>
                    ))}
                  </g>
                );
              })}
            </g>

            {/* Migration milestones header */}
            <g transform={`translate(0, ${MONTH_HEADER_HEIGHT + sprintsHeight + 8})`}>
              <text x={12} y={14} fontSize="10" fill="var(--con-ink-4)" fontFamily="Geist Mono" fontWeight="600">
                MIGRATION MILESTONES
              </text>
              <line
                x1={LABEL_COL_WIDTH}
                y1={MILESTONE_HEADER_HEIGHT - 0.5}
                x2={CHART_WIDTH}
                y2={MILESTONE_HEADER_HEIGHT - 0.5}
                stroke="var(--con-line)"
              />
            </g>

            {/* Migration checkpoints strip */}
            <g
              transform={`translate(0, ${MONTH_HEADER_HEIGHT + sprintsHeight + MILESTONE_HEADER_HEIGHT + 8})`}
            >
              {/* Spine line */}
              <line
                x1={LABEL_COL_WIDTH}
                y1={MIGRATION_STRIP_HEIGHT / 2}
                x2={CHART_WIDTH}
                y2={MIGRATION_STRIP_HEIGHT / 2}
                stroke="var(--con-line-2)"
                strokeWidth="2"
              />
              {checkpoints.map((cp, i) => {
                const cx = LABEL_COL_WIDTH + xFor(cp.date);
                const labelAbove = i % 2 === 0;
                return (
                  <g key={cp.id} transform={`translate(${cx}, ${MIGRATION_STRIP_HEIGHT / 2})`}>
                    <circle r={6} fill={cp.color} stroke="var(--con-surface)" strokeWidth="2" />
                    <text
                      x={0}
                      y={labelAbove ? -12 : 22}
                      fontSize="10.5"
                      fill="var(--con-ink-2)"
                      textAnchor="middle"
                      fontWeight="600"
                    >
                      {cp.label}
                    </text>
                    <text
                      x={0}
                      y={labelAbove ? -24 : 34}
                      fontSize="9.5"
                      fill="var(--con-ink-4)"
                      textAnchor="middle"
                      fontFamily="Geist Mono"
                    >
                      {cp.date.slice(0, 10)}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
      </Card>

      {/* ── Milestone legend ────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-4 mt-4 text-[11.5px] text-ink-2">
        <span className="eyebrow text-[10px]">MILESTONES</span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[var(--con-ok)]" /> Done
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[var(--con-brand)]" /> In progress
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full border border-ink-4 bg-surface" /> Pending
        </span>
      </div>
    </AppShell>
  );
}
