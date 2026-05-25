import { Flame, AlertOctagon, ArrowRight } from "lucide-react";
import { DemoShell } from "./DemoShell";
import { DEMO_SPRINT_TASKS, DEMO_SPRINT_MILESTONES } from "@/data/demo-data";

const card = "bg-surface border border-zinc-200 rounded-xl shadow-soft p-5";

const STAGES = ["Discovery", "Mapping", "Conversion", "Validation", "Production"];
const STAGE_STATUS: Record<string, "done" | "in_progress" | "pending"> = {
  Discovery:  "done",
  Mapping:    "done",
  Conversion: "in_progress",
  Validation: "pending",
  Production: "pending",
};

// Map raw status → kanban column
function columnOf(status: string): "Backlog" | "In progress" | "Review" | "Done" | "Blocked" {
  if (status === "blocked") return "Blocked";
  if (status === "backlog" || status === "ready") return "Backlog";
  if (status === "in_progress" || status === "ai_processing") return "In progress";
  if (status === "human_review" || status === "validation" || status === "recon") return "Review";
  if (status === "approved" || status === "completed") return "Done";
  return "Backlog";
}

function PriorityChip({ p }: { p: string }) {
  const map: Record<string, string> = {
    P0: "bg-rose-50 text-rose-700",
    P1: "bg-amber-50 text-amber-700",
    P2: "bg-zinc-100 text-ink-3",
  };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${map[p] || "bg-zinc-100 text-ink-3"}`}>
      {p}
    </span>
  );
}

function TaskCard({ t }: { t: typeof DEMO_SPRINT_TASKS[number] }) {
  const isBlocked = t.status === "blocked";
  return (
    <div
      className={
        "bg-surface border rounded-lg p-3 shadow-soft hover:shadow-md transition-all " +
        (isBlocked ? "border-rose-200 ring-1 ring-rose-100" : "border-zinc-200")
      }
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-[10.5px] font-mono text-ink-4">{t.id}</span>
        <PriorityChip p={t.priority} />
      </div>
      <div className="text-[12.5px] font-medium text-ink leading-snug">{t.title}</div>
      <div className="mt-2 text-[11px] text-ink-4">{t.agent}</div>
    </div>
  );
}

export function DemoSprintMapping() {
  const cols: Record<string, typeof DEMO_SPRINT_TASKS> = {
    Backlog:       [],
    "In progress": [],
    Review:        [],
    Done:          [],
    Blocked:       [],
  };
  for (const t of DEMO_SPRINT_TASKS) {
    cols[columnOf(t.status)].push(t);
  }

  const sprintTotal = DEMO_SPRINT_TASKS.length;
  const sprintDone  = cols.Done.length;
  const storyPointsDone = sprintDone * 5;
  const blocked = cols.Blocked;

  return (
    <DemoShell title="Sprint mapping" description="Migration-specific kanban tied to source-to-target execution stages.">
      {/* 4-card metric strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <Metric k="Sprint 12" v="Active sprint" />
        <Metric k={`${storyPointsDone} / ${sprintTotal * 5}`} v="Story points done" />
        <Metric k="92.4%" v="Validation" />
        <Metric k="96.5%" v="Recon" />
      </div>

      {/* Main layout */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-5 mb-5">
        {/* Kanban */}
        <div className="xl:col-span-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {(["Backlog", "In progress", "Review", "Done"] as const).map((col) => (
              <div key={col} className="bg-surface-muted rounded-xl border border-zinc-200 p-3 min-h-[280px]">
                <div className="flex items-center justify-between mb-3 px-1">
                  <h4 className="text-[12.5px] font-semibold text-ink">{col}</h4>
                  <span className="text-[11px] font-mono text-ink-4 bg-surface px-1.5 py-0.5 rounded">{cols[col].length}</span>
                </div>
                <div className="space-y-2">
                  {cols[col].map((t) => <TaskCard key={t.id} t={t} />)}
                  {cols[col].length === 0 && (
                    <div className="text-[11.5px] text-ink-5 text-center py-6">— empty —</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Migration mapping */}
        <div className={card}>
          <h3 className="text-[14px] font-semibold text-ink mb-3">Migration mapping</h3>
          <p className="text-[12px] text-ink-3 mb-4 leading-relaxed">
            Where the sprint lives along the source-to-target pipeline.
          </p>
          <ol className="space-y-2.5">
            {STAGES.map((s, i) => {
              const st = STAGE_STATUS[s];
              const dot =
                st === "done"
                  ? "bg-emerald-500"
                  : st === "in_progress"
                  ? "bg-amber-500"
                  : "bg-zinc-300";
              return (
                <li key={s} className="flex items-center gap-3">
                  <span className={`h-2.5 w-2.5 rounded-full ${dot} shrink-0`} />
                  <span className={`text-[13px] ${st === "pending" ? "text-ink-4" : "text-ink"} font-medium`}>{s}</span>
                  {i < STAGES.length - 1 && <ArrowRight className="ml-auto h-3.5 w-3.5 text-ink-5" />}
                </li>
              );
            })}
          </ol>
        </div>
      </div>

      {/* Milestone timeline */}
      <div className={`${card} mb-5`}>
        <h3 className="text-[14px] font-semibold text-ink mb-4">Sprint milestones</h3>
        <div className="relative">
          <div className="absolute top-3 left-0 right-0 h-px bg-zinc-200" />
          <div className="flex justify-between gap-2 overflow-x-auto pb-2">
            {DEMO_SPRINT_MILESTONES.map((m) => {
              const dot =
                m.status === "done"
                  ? "bg-emerald-500"
                  : m.status === "in_progress"
                  ? "bg-amber-500 animate-pulse"
                  : "bg-zinc-300";
              return (
                <div key={m.label} className="flex flex-col items-center text-center min-w-[100px] relative">
                  <span className={`h-3 w-3 rounded-full ${dot} ring-4 ring-surface`} />
                  <div className="text-[11.5px] font-mono text-ink-4 mt-2">{m.date}</div>
                  <div className="text-[12px] font-medium text-ink mt-0.5 leading-tight">{m.label}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Blockers */}
      {blocked.length > 0 && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <AlertOctagon className="h-4 w-4 text-rose-600" />
            <h3 className="text-[14px] font-semibold text-rose-900">Blockers</h3>
          </div>
          <ul className="space-y-2.5">
            {blocked.map((t) => (
              <li key={t.id} className="flex items-start gap-3 text-[12.5px]">
                <Flame className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="text-rose-900 font-medium">{t.title}</div>
                  <div className="text-rose-800/80 mt-0.5">
                    Awaiting target Snowflake warehouse provisioning · owner {t.agent}
                  </div>
                </div>
                <span className="text-[10.5px] font-mono text-rose-700">{t.id}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </DemoShell>
  );
}

function Metric({ k, v }: { k: string; v: string }) {
  return (
    <div className={card}>
      <div className="text-[18px] font-semibold text-ink tracking-tight">{k}</div>
      <div className="text-[11.5px] text-ink-3 mt-0.5">{v}</div>
    </div>
  );
}
