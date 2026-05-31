"use client";

/**
 * /projects/[id]/sprints/risks — Sprint Risk Dashboard.
 *
 * Per-sprint risk register with severity counts, category breakdown, a
 * 5x5 likelihood × impact heatmap, and detail cards sorted by severity.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout";
import { Button, Card, EmptyState, LoadingState, MetricCell } from "@/components/ui";
import { SprintRiskCard } from "@/components/sprints";
import { useAuth } from "@/lib/auth-context";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import {
  fetchActiveSprint,
  fetchRisks,
  seedSprints,
  type RiskCategory,
  type RiskLevel,
  type Sprint,
  type SprintRisk,
} from "@/lib/sprints";

const LEVEL_ORDER: Record<RiskLevel, number> = { critical: 0, high: 1, med: 2, low: 3 };
const LEVEL_COLOR: Record<RiskLevel, string> = {
  critical: "var(--con-err)",
  high:     "var(--con-err)",
  med:      "var(--con-warn)",
  low:      "var(--con-ok)",
};

const CATEGORIES: { id: RiskCategory; label: string }[] = [
  { id: "data",        label: "Data quality" },
  { id: "validation",  label: "Validation" },
  { id: "recon",       label: "Reconciliation" },
  { id: "deployment",  label: "Deployment" },
  { id: "compliance",  label: "Compliance" },
  { id: "security",    label: "Security" },
];

// Map level → (likelihood, impact) coordinates on the 5x5 grid.
const LEVEL_CELL: Record<RiskLevel, { lik: number; imp: number }> = {
  critical: { lik: 4, imp: 4 },
  high:     { lik: 4, imp: 3 },
  med:      { lik: 2, imp: 2 },
  low:      { lik: 1, imp: 0 },
};

export default function SprintRisksPage() {
  const projectKey = String(useParams<{ id: string }>().id);
  const { id } = useProjectKey(projectKey);
  const { token } = useAuth();

  const [active, setActive] = useState<Sprint | null>(null);
  const [risks, setRisks] = useState<SprintRisk[]>([]);
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
      setRisks([]);
      return;
    }
    fetchRisks(token, active.id)
      .then(setRisks)
      .catch(() => setRisks([]));
  }, [token, active]);

  const counts = useMemo(() => {
    const c: Record<RiskLevel, number> = { critical: 0, high: 0, med: 0, low: 0 };
    risks.forEach((r) => { c[r.level]++; });
    return c;
  }, [risks]);

  const byCategory = useMemo(() => {
    const m = new Map<RiskCategory, SprintRisk[]>();
    CATEGORIES.forEach((c) => m.set(c.id, []));
    risks.forEach((r) => {
      if (!m.has(r.category)) m.set(r.category, []);
      m.get(r.category)!.push(r);
    });
    return m;
  }, [risks]);

  const sorted = useMemo(() => {
    return [...risks].sort((a, b) => LEVEL_ORDER[a.level] - LEVEL_ORDER[b.level]);
  }, [risks]);

  // Heatmap matrix [likelihood][impact] -> count
  const heat = useMemo(() => {
    const grid: number[][] = Array.from({ length: 5 }, () => Array(5).fill(0));
    risks.forEach((r) => {
      const cell = LEVEL_CELL[r.level];
      grid[cell.lik][cell.imp] += 1;
    });
    return grid;
  }, [risks]);

  const maxByCategory = useMemo(() => {
    let m = 0;
    byCategory.forEach((v) => { if (v.length > m) m = v.length; });
    return Math.max(1, m);
  }, [byCategory]);

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
        eyebrow={`SPRINTS · ${projectKey}`}
        title="Risk dashboard"
        crumbs={["Projects", projectKey, "Sprints", "Risks"]}
      >
        <LoadingState />
      </AppShell>
    );
  }

  if (!active) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectKey}`}
        title="Risk dashboard"
        crumbs={["Projects", projectKey, "Sprints", "Risks"]}
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
      eyebrow={`SPRINTS · ${projectKey}`}
      title="Risk dashboard"
      description={`${risks.length} open risks across ${active.name}.`}
      crumbs={["Projects", projectKey, "Sprints", "Risks"]}
    >
      {/* Metric strip (6 cells, wraps 3+3) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 bg-surface border border-hx rounded-[10px] divide-y sm:divide-y-0 sm:divide-x divide-hx mb-6">
        <MetricCell big label="Critical" value={counts.critical} accent={counts.critical > 0 ? "var(--con-err)" : undefined} />
        <MetricCell big label="High"     value={counts.high}     accent={counts.high > 0 ? "var(--con-err)" : undefined} />
        <MetricCell big label="Medium"   value={counts.med}      accent={counts.med > 0 ? "var(--con-warn)" : undefined} />
        <MetricCell big label="Low"      value={counts.low}      accent="var(--con-ok)" />
        <MetricCell big label="AI confidence" value="78%" hint="Average across risks" />
        <MetricCell big label="Mitigation"    value="62%" hint="Plans in progress" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-4">
        <div className="flex flex-col gap-4">
          {/* Category breakdown */}
          <Card title="Risk by category" eyebrow="DISTRIBUTION">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
              {CATEGORIES.map((c) => {
                const items = byCategory.get(c.id) ?? [];
                const pct = (items.length / maxByCategory) * 100;
                return (
                  <div key={c.id}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[12px] text-ink-2 capitalize">{c.label}</span>
                      <span className="font-mono text-[11px] text-ink-4">{items.length}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-app-2 overflow-hidden mb-1.5">
                      <div
                        className="h-full"
                        style={{
                          width: `${pct}%`,
                          background: items.length === 0 ? "var(--con-line-2)" : "var(--con-ink-1)",
                        }}
                      />
                    </div>
                    <div className="flex gap-1.5">
                      {items.length === 0 && <span className="text-[10.5px] text-ink-5 font-mono">None</span>}
                      {items.map((r) => (
                        <span
                          key={r.id}
                          className="h-2 w-2 rounded-full"
                          style={{ background: LEVEL_COLOR[r.level] }}
                          title={`${r.level.toUpperCase()} — ${r.title}`}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Risk cards */}
          <div className="flex flex-col gap-3">
            <div className="flex items-end justify-between">
              <div>
                <div className="eyebrow text-[10px]">REGISTER</div>
                <h2 className="text-[15px] font-semibold text-ink tracking-tight">All risks</h2>
              </div>
              <span className="font-mono text-[11px] text-ink-4">{sorted.length} total</span>
            </div>
            {sorted.length === 0 ? (
              <Card>
                <p className="text-[12px] text-ink-3">No risks currently open in this sprint.</p>
              </Card>
            ) : (
              sorted.map((r) => <SprintRiskCard key={r.id} risk={r} />)
            )}
          </div>
        </div>

        {/* Heatmap */}
        <Card title="Risk heatmap" eyebrow="LIKELIHOOD × IMPACT">
          <Heatmap grid={heat} />
          <div className="mt-3 pt-3 border-t border-hx flex items-center justify-between text-[10.5px] text-ink-4 font-mono">
            <span>Low risk</span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-3 rounded-sm" style={{ background: "var(--con-ok-soft)" }} />
              <span className="h-2 w-3 rounded-sm" style={{ background: "var(--con-warn-soft)" }} />
              <span className="h-2 w-3 rounded-sm" style={{ background: "var(--con-err-soft)" }} />
            </span>
            <span>Critical</span>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

function Heatmap({ grid }: { grid: number[][] }) {
  // grid[lik][imp]. Render so likelihood increases upward (row 4 at top).
  return (
    <div>
      <div className="flex">
        <div className="flex flex-col justify-between text-[9.5px] font-mono text-ink-4 pr-2 py-[3px]" style={{ height: 200 }}>
          <span>HIGH</span>
          <span>LIK.</span>
          <span>LOW</span>
        </div>
        <div className="grid grid-cols-5 gap-1 flex-1" style={{ height: 200 }}>
          {Array.from({ length: 5 }).map((_, rowIdx) => {
            const lik = 4 - rowIdx;
            return Array.from({ length: 5 }).map((__, imp) => {
              const count = grid[lik]?.[imp] ?? 0;
              const severity = (lik + imp) / 8;
              const bg = count === 0
                ? "var(--con-bg-2)"
                : severity >= 0.7
                  ? "var(--con-err-soft)"
                  : severity >= 0.4
                    ? "var(--con-warn-soft)"
                    : "var(--con-ok-soft)";
              const fg = severity >= 0.7
                ? "var(--con-err)"
                : severity >= 0.4
                  ? "var(--con-warn)"
                  : "var(--con-ok)";
              return (
                <div
                  key={`${lik}-${imp}`}
                  className="rounded grid place-items-center border border-hx"
                  style={{ background: bg }}
                >
                  {count > 0 && (
                    <span className="font-mono tabular-nums text-[12px] font-medium" style={{ color: fg }}>
                      {count}
                    </span>
                  )}
                </div>
              );
            });
          })}
        </div>
      </div>
      <div className="grid grid-cols-5 gap-1 text-[9.5px] font-mono text-ink-4 mt-1.5 text-center" style={{ marginLeft: 36 }}>
        <span>LOW</span>
        <span></span>
        <span>IMPACT</span>
        <span></span>
        <span>HIGH</span>
      </div>
    </div>
  );
}
