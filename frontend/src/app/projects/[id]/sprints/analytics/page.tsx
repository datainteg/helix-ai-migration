"use client";

/**
 * /projects/[id]/sprints/analytics — Sprint Analytics Dashboard.
 *
 * Cross-sprint migration analytics: velocity, agent contribution split,
 * validation + recon trend lines, and a per-sprint stats table.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Download, BarChart3 } from "lucide-react";

import { AppShell } from "@/components/layout";
import {
  AreaChart,
  Button,
  Card,
  Donut,
  EmptyState,
  LoadingState,
  MetricCell,
  StatusBadge,
} from "@/components/ui";
import { SprintVelocityChart } from "@/components/sprints";
import { useAuth } from "@/lib/auth-context";
import {
  fetchSprints,
  fetchVelocity,
  seedSprints,
  type Sprint,
  type VelocityPoint,
} from "@/lib/sprints";

// Fake agent contribution split — purely illustrative for analytics demo.
const AGENT_BREAKDOWN: Array<{ label: string; value: number; color: string }> = [
  { label: "Mary",    value: 18, color: "#4338CA" },
  { label: "John",    value: 12, color: "#6D28D9" },
  { label: "Sally",   value:  9, color: "#B45309" },
  { label: "Winston", value: 14, color: "#1D4ED8" },
  { label: "Amelia",  value: 22, color: "#15803D" },
  { label: "Paige",   value:  6, color: "#B91C1C" },
  { label: "Humans",  value: 12, color: "#374151" },
];

export default function SprintAnalyticsPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params?.id ?? "");
  const { token } = useAuth();

  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [velocity, setVelocity] = useState<VelocityPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(() => {
    if (!token || !projectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([
      fetchSprints(token, projectId),
      fetchVelocity(token, projectId),
    ])
      .then(([list, vel]) => {
        setSprints(list);
        setVelocity(vel);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const avgVelocity = useMemo(() => {
    const delivered = velocity.map((v) => v.delivered);
    return delivered.length ? Math.round(delivered.reduce((a, b) => a + b, 0) / delivered.length) : 0;
  }, [velocity]);

  const avgValidation = useMemo(() => {
    const pcts = sprints.map((s) => s.metrics.validationCoveragePct);
    return pcts.length ? Math.round(pcts.reduce((a, b) => a + b, 0) / pcts.length) : 0;
  }, [sprints]);

  const avgRecon = useMemo(() => {
    const pcts = sprints.map((s) => s.metrics.reconCoveragePct);
    return pcts.length ? Math.round(pcts.reduce((a, b) => a + b, 0) / pcts.length) : 0;
  }, [sprints]);

  const validationTrend = useMemo(
    () =>
      sprints.map((s) => ({
        label: `S${s.index}`,
        a: s.metrics.validationCoveragePct,
      })),
    [sprints]
  );

  const reconTrend = useMemo(
    () =>
      sprints.map((s) => ({
        label: `S${s.index}`,
        a: s.metrics.reconCoveragePct,
      })),
    [sprints]
  );

  const totalAgent = AGENT_BREAKDOWN.reduce((a, b) => a + b.value, 0);

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
        title="Sprint analytics"
        crumbs={["Projects", projectId, "Sprints", "Analytics"]}
      >
        <LoadingState />
      </AppShell>
    );
  }

  if (sprints.length === 0) {
    return (
      <AppShell
        eyebrow={`SPRINTS · ${projectId}`}
        title="Sprint analytics"
        crumbs={["Projects", projectId, "Sprints", "Analytics"]}
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

  return (
    <AppShell
      eyebrow={`SPRINTS · ${projectId}`}
      title="Sprint analytics"
      description="Cross-sprint velocity, validation + recon trends, and AI vs human contribution split."
      crumbs={["Projects", projectId, "Sprints", "Analytics"]}
      actions={
        <>
          <Button variant="outline">
            <Download className="h-4 w-4" /> Export
          </Button>
          <Button variant="primary">
            <BarChart3 className="h-4 w-4" /> Compare portfolios
          </Button>
        </>
      }
    >
      {/* Top metric strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 bg-surface border border-hx rounded-[10px] divide-y lg:divide-y-0 lg:divide-x divide-hx mb-6">
        <MetricCell big label="Avg velocity"        value={`${avgVelocity} SP`} hint="Rolling 5 sprints" />
        <MetricCell big label="Avg cycle time"      value="4.2d"                hint="Task ready → done" />
        <MetricCell big label="Validation pass"     value={`${avgValidation}%`} hint="Avg across sprints" />
        <MetricCell big label="Recon pass"          value={`${avgRecon}%`}      hint="Avg across sprints" />
        <MetricCell big label="AI vs Human"         value="71% / 29%"           hint="Work attribution" />
      </div>

      {/* Velocity + agent donut */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <Card className="lg:col-span-2" title="Velocity by sprint" eyebrow="DELIVERY">
          <SprintVelocityChart data={velocity} width={720} height={260} />
        </Card>
        <Card title="Agent contribution" eyebrow="WORK SHARE">
          <div className="flex flex-col items-center gap-4">
            <Donut
              data={AGENT_BREAKDOWN}
              size={180}
              thickness={22}
              centerValue={String(totalAgent)}
              centerLabel="TASKS"
            />
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 w-full">
              {AGENT_BREAKDOWN.map((d) => {
                const pct = Math.round((d.value / totalAgent) * 100);
                return (
                  <div key={d.label} className="flex items-center gap-2 text-[11.5px]">
                    <span className="h-2 w-2 rounded-full" style={{ background: d.color }} />
                    <span className="text-ink-2">{d.label}</span>
                    <span className="ml-auto font-mono text-ink-4">{pct}%</span>
                  </div>
                );
              })}
            </div>
          </div>
        </Card>
      </div>

      {/* Validation + recon trends */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <Card title="Validation coverage trend" eyebrow="QUALITY">
          <AreaChart data={validationTrend} width={520} height={220} color="var(--con-ok)" />
        </Card>
        <Card title="Recon parity trend" eyebrow="QUALITY">
          <AreaChart data={reconTrend} width={520} height={220} color="var(--con-brand)" />
        </Card>
      </div>

      {/* Per-sprint stats table */}
      <Card title="Per-sprint stats" eyebrow="BREAKDOWN" bodyClassName="p-0">
        <div className="w-full overflow-x-auto">
          <table className="w-full border-collapse text-[12.5px]">
            <thead className="bg-surface-hi">
              <tr>
                <TH>Sprint</TH>
                <TH>Status</TH>
                <TH align="right">Story points</TH>
                <TH align="right">Validation</TH>
                <TH align="right">Recon</TH>
                <TH align="right">Velocity</TH>
              </tr>
            </thead>
            <tbody>
              {sprints.map((s) => (
                <tr key={s.id} className="border-b border-hx last:border-b-0 hover:bg-surface-hi">
                  <TD>
                    <div className="font-medium text-ink">{s.name}</div>
                    <div className="text-[10.5px] text-ink-4 font-mono mt-0.5">{s.id}</div>
                  </TD>
                  <TD>
                    <StatusBadge status={s.status} />
                  </TD>
                  <TD align="right" mono>
                    {s.metrics.storyPointsDone}/{s.metrics.storyPointsTotal}
                  </TD>
                  <TD align="right" mono>
                    <span style={{ color: pctColor(s.metrics.validationCoveragePct) }}>
                      {s.metrics.validationCoveragePct}%
                    </span>
                  </TD>
                  <TD align="right" mono>
                    <span style={{ color: pctColor(s.metrics.reconCoveragePct) }}>
                      {s.metrics.reconCoveragePct}%
                    </span>
                  </TD>
                  <TD align="right" mono>
                    {s.metrics.velocity} SP
                  </TD>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </AppShell>
  );
}

function pctColor(v: number): string {
  if (v >= 90) return "var(--con-ok)";
  if (v >= 60) return "var(--con-warn)";
  if (v > 0)   return "var(--con-err)";
  return "var(--con-ink-4)";
}

function TH({ children, align = "left" }: { children: React.ReactNode; align?: "left" | "right" | "center" }) {
  return (
    <th
      className={`px-3.5 py-2.5 font-medium text-ink-4 text-[10.5px] uppercase tracking-[0.08em] font-mono border-b border-hx ${
        align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}

function TD({
  children,
  align = "left",
  mono = false,
}: {
  children: React.ReactNode;
  align?: "left" | "right" | "center";
  mono?: boolean;
}) {
  return (
    <td
      className={`px-3.5 py-3 align-middle ${
        align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left"
      } ${mono ? "font-mono" : ""}`}
    >
      {children}
    </td>
  );
}
