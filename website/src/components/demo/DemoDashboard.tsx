import {
  Briefcase,
  Activity,
  ShieldCheck,
  GitCompareArrows,
  ClipboardCheck,
  Cpu,
  AlertTriangle,
} from "lucide-react";
import { DemoShell } from "./DemoShell";
import { DEMO_METRICS, DEMO_PROJECTS, DEMO_AUDIT_LOGS } from "@/data/demo-data";

const card = "bg-surface border border-zinc-200 rounded-xl shadow-soft p-5";

function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    running:  "bg-amber-50 text-amber-700",
    awaiting: "bg-zinc-100 text-ink-3",
    pass:     "bg-emerald-50 text-emerald-700",
    fail:     "bg-rose-50 text-rose-700",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium ${map[status] || "bg-zinc-100 text-ink-3"}`}>
      {status}
    </span>
  );
}

function Spark({ data }: { data: number[] }) {
  const max = Math.max(...data, 1);
  const w = 80, h = 24;
  // Guard against div-by-zero when the dataset has fewer than 2 points.
  const denom = Math.max(1, data.length - 1);
  const pts = data
    .map((v, i) => `${(i / denom) * w},${h - (v / max) * h}`)
    .join(" ");
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={pts} fill="none" stroke="#4F46E5" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MetricCard({ icon: Icon, label, value, sub, trend }: { icon: any; label: string; value: string; sub?: string; trend: number[] }) {
  return (
    <div className={card}>
      <div className="flex items-start justify-between">
        <div className="h-8 w-8 rounded-md bg-brand-50 text-brand-600 grid place-items-center">
          <Icon className="h-4 w-4" />
        </div>
        <Spark data={trend} />
      </div>
      <div className="mt-3">
        <div className="text-[20px] font-semibold text-ink tracking-tight">{value}</div>
        <div className="text-[12px] text-ink-3 mt-0.5">{label}</div>
        {sub && <div className="text-[11px] text-ink-4 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

export function DemoDashboard() {
  return (
    <DemoShell title="Operations dashboard" description="A single pane for migration health across all active projects.">
      {/* 7-card metric strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3 mb-6">
        <MetricCard icon={Briefcase}      label="Total projects"     value={String(DEMO_METRICS.totalProjects)}             trend={[3,5,4,7,9,12,14]} />
        <MetricCard icon={Activity}       label="Active migrations"  value={String(DEMO_METRICS.activeMigrations)}          trend={[6,8,7,10,12,14,18]} />
        <MetricCard icon={ShieldCheck}    label="Validation %"       value={`${DEMO_METRICS.validationScore}%`}             trend={[78,82,85,89,90,91,92]} />
        <MetricCard icon={GitCompareArrows} label="Recon %"           value={`${DEMO_METRICS.reconScore}%`}                  trend={[90,92,93,94,95,96,97]} />
        <MetricCard icon={ClipboardCheck} label="Pending approvals"  value={String(DEMO_METRICS.pendingApprovals)}          trend={[7,6,5,4,4,4,4]} />
        <MetricCard icon={Cpu}            label="Agent tasks"        value={String(DEMO_METRICS.agentTasks)}                trend={[60,72,84,96,112,128,138]} />
        <MetricCard icon={AlertTriangle}  label="Risk score"         value={String(DEMO_METRICS.riskScore)} sub="lower is better" trend={[58,55,52,48,44,40,38]} />
      </div>

      {/* 2-col: projects + agent activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className={`${card} lg:col-span-2 p-0 overflow-hidden`}>
          <div className="px-5 py-3 border-b border-zinc-200 flex items-center justify-between">
            <h3 className="text-[14px] font-semibold text-ink">Active projects</h3>
            <span className="text-[11px] text-ink-4">{DEMO_PROJECTS.length} running</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead className="bg-surface-subtle text-ink-3">
                <tr>
                  <th className="text-left font-medium px-5 py-2.5">Project</th>
                  <th className="text-left font-medium px-3 py-2.5">Phase</th>
                  <th className="text-left font-medium px-3 py-2.5">Valid</th>
                  <th className="text-left font-medium px-3 py-2.5">Recon</th>
                  <th className="text-left font-medium px-3 py-2.5">Status</th>
                  <th className="text-left font-medium px-3 py-2.5">Owner</th>
                </tr>
              </thead>
              <tbody>
                {DEMO_PROJECTS.map((p) => (
                  <tr key={p.id} className="border-b border-zinc-200 last:border-0 hover:bg-surface-muted">
                    <td className="px-5 py-2.5">
                      <div className="font-medium text-ink">{p.name}</div>
                      <div className="text-[11px] text-ink-4 font-mono">{p.id} · {p.tables} tables</div>
                    </td>
                    <td className="px-3 py-2.5 text-ink-2">{p.phase}</td>
                    <td className="px-3 py-2.5 font-mono text-ink-2">{p.valid}%</td>
                    <td className="px-3 py-2.5 font-mono text-ink-2">{p.recon}%</td>
                    <td className="px-3 py-2.5"><StatusChip status={p.status} /></td>
                    <td className="px-3 py-2.5 text-ink-3">{p.owner}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className={card}>
          <h3 className="text-[14px] font-semibold text-ink mb-3">Agent activity</h3>
          <ul className="space-y-3">
            {DEMO_AUDIT_LOGS.slice(0, 5).map((a, i) => (
              <li key={i} className="flex gap-3">
                <div className="h-7 w-7 rounded-full bg-brand-50 text-brand-700 text-[11px] font-mono grid place-items-center shrink-0">
                  {a.actor.replace("@", "").slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[12.5px] text-ink">
                    <span className="font-medium">{a.actor}</span>{" "}
                    <span className="text-ink-3">{a.action.replace(/_/g, " ")}</span>
                  </div>
                  <div className="text-[11px] text-ink-4 truncate font-mono">{a.entity}</div>
                  <div className="text-[11px] text-ink-5 mt-0.5">{a.ts}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </DemoShell>
  );
}
