import { Check, CircleDot, Circle, Clock } from "lucide-react";
import { DemoShell } from "./DemoShell";
import { DEMO_PROJECTS, DEMO_SPRINT_MILESTONES } from "@/data/demo-data";

const card = "bg-surface border border-zinc-200 rounded-xl shadow-soft p-5";

const PHASES = ["Intake", "Mapping", "Conversion", "Validation", "Production"];

const APPROVALS = [
  { title: "Schema map for GL_TRANS",       requester: "Architect Agent", age: "12m" },
  { title: "Cutover plan v3",                requester: "PM Agent",        age: "1h" },
  { title: "Adversarial review of migrate.py", requester: "Code Review Agent", age: "3h" },
];

export function DemoProjectWorkspace() {
  const p = DEMO_PROJECTS[0];
  const currentPhaseIdx = PHASES.indexOf("Conversion");

  return (
    <DemoShell title="Project workspace" description="A single project in flight — phases, status, and pending decisions in one view.">
      {/* Header */}
      <div className={`${card} mb-5`}>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <div className="text-[11px] text-ink-4 font-mono">{p.id}</div>
            <h2 className="text-[18px] font-semibold text-ink mt-0.5">{p.name}</h2>
            <div className="text-[12px] text-ink-3 mt-1">
              {p.source} <span className="text-ink-5">→</span> {p.target} · owned by {p.owner}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-2.5 py-1 rounded-md text-[11.5px] font-medium bg-amber-50 text-amber-700">
              {p.status}
            </span>
            <span className="inline-flex items-center px-2.5 py-1 rounded-md text-[11.5px] font-medium bg-zinc-100 text-ink-3">
              {p.tables} tables
            </span>
          </div>
        </div>

        {/* Phase ticker */}
        <div className="mt-5 flex items-center gap-1 overflow-x-auto pb-1">
          {PHASES.map((ph, i) => {
            const done = i < currentPhaseIdx;
            const active = i === currentPhaseIdx;
            return (
              <div key={ph} className="flex items-center gap-1 shrink-0">
                <div
                  className={
                    "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11.5px] font-medium " +
                    (done
                      ? "bg-emerald-50 text-emerald-700"
                      : active
                      ? "bg-brand-50 text-brand-700"
                      : "bg-zinc-100 text-ink-4")
                  }
                >
                  {done ? <Check className="h-3 w-3" /> : active ? <CircleDot className="h-3 w-3" /> : <Circle className="h-3 w-3" />}
                  {ph}
                </div>
                {i < PHASES.length - 1 && <div className="h-px w-6 bg-zinc-300" />}
              </div>
            );
          })}
        </div>
      </div>

      {/* 2-col status + summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-5">
        <div className={`${card} lg:col-span-2`}>
          <h3 className="text-[14px] font-semibold text-ink mb-3">Migration status</h3>
          <div className="space-y-3">
            <Bar label="Tables migrated" value={Math.round(p.tables * 0.69)} total={p.tables} color="bg-brand-600" />
            <Bar label="Validation passed" value={p.valid} total={100} color="bg-emerald-500" />
            <Bar label="Recon parity"     value={p.recon} total={100} color="bg-cyan-500" />
          </div>
          <div className="mt-4 grid grid-cols-3 gap-3 text-center">
            <Tile k={String(Math.round(p.tables * 0.69))} v="Tables migrated" />
            <Tile k="128" v="Pending review" />
            <Tile k="0" v="Failed cutovers" />
          </div>
        </div>

        <div className={card}>
          <h3 className="text-[14px] font-semibold text-ink mb-3">Source / target summary</h3>
          <dl className="space-y-2.5 text-[12.5px]">
            <Row k="Source" v={p.source} />
            <Row k="Target" v={p.target} />
            <Row k="Owner"  v={p.owner} />
            <Row k="Phase"  v={p.phase} />
            <Row k="Risk"   v={`${p.risk} / 100`} />
            <Row k="Updated" v={p.updated} />
          </dl>
        </div>
      </div>

      {/* Timeline + approvals */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className={`${card} lg:col-span-2`}>
          <h3 className="text-[14px] font-semibold text-ink mb-4">Project timeline</h3>
          <ol className="relative border-l border-zinc-200 ml-3 space-y-4">
            {DEMO_SPRINT_MILESTONES.map((m) => {
              const dot =
                m.status === "done"
                  ? "bg-emerald-500"
                  : m.status === "in_progress"
                  ? "bg-amber-500"
                  : "bg-zinc-300";
              return (
                <li key={m.label} className="pl-4 relative">
                  <span className={`absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full ${dot} ring-4 ring-surface`} />
                  <div className="text-[13px] font-medium text-ink">{m.label}</div>
                  <div className="text-[11.5px] text-ink-4 font-mono mt-0.5">{m.date} · {m.status.replace("_", " ")}</div>
                </li>
              );
            })}
          </ol>
        </div>

        <div className={card}>
          <h3 className="text-[14px] font-semibold text-ink mb-3">Pending approvals</h3>
          <ul className="space-y-3">
            {APPROVALS.map((a, i) => (
              <li key={i} className="flex gap-3 border-b border-zinc-200 last:border-0 pb-3 last:pb-0">
                <Clock className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <div className="text-[13px] font-medium text-ink truncate">{a.title}</div>
                  <div className="text-[11.5px] text-ink-4 mt-0.5">from {a.requester} · {a.age} ago</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </DemoShell>
  );
}

function Bar({ label, value, total, color }: { label: string; value: number; total: number; color: string }) {
  const pct = Math.min(100, Math.round((value / total) * 100));
  return (
    <div>
      <div className="flex items-center justify-between text-[12px] mb-1">
        <span className="text-ink-2">{label}</span>
        <span className="font-mono text-ink-3">{value} / {total}</span>
      </div>
      <div className="h-1.5 rounded-full bg-zinc-100 overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between border-b border-zinc-100 last:border-0 pb-2 last:pb-0">
      <dt className="text-ink-4">{k}</dt>
      <dd className="text-ink font-medium">{v}</dd>
    </div>
  );
}

function Tile({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-lg bg-surface-muted border border-zinc-200 py-3">
      <div className="text-[18px] font-semibold text-ink">{k}</div>
      <div className="text-[11px] text-ink-4 mt-0.5">{v}</div>
    </div>
  );
}
