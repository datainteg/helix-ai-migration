import { ArrowDown, CheckCircle2, CircleDot, Circle, UserCheck, Cpu } from "lucide-react";
import { DemoShell } from "./DemoShell";
import { DEMO_AGENT_FLOW, DEMO_RUN } from "@/data/demo-data";

const card = "bg-surface border border-zinc-200 rounded-xl shadow-soft p-5";

// Description map keyed off node label substring
function describe(label: string): string {
  const m: Record<string, string> = {
    "Requirement Intake":  "Captures the brief, source, target, and constraints.",
    "BA Agent":            "Drafts the product brief with persona and scope analysis.",
    "Architect Agent":     "Writes the architecture and readiness check.",
    "Human Approval":      "Operator reviews artifacts and gates the pipeline.",
    "Data Engineer Agent": "Generates code, schema map, and migration scripts.",
    "QA Agent":            "Builds validation rules and acceptance tests.",
    "Recon Agent":         "Runs source vs target reconciliation summaries.",
    "DevOps Agent":        "Prepares cutover, monitoring, and rollback plan.",
    "PM Agent":            "Sequences epics and stories for the sprint.",
    "Final Review":        "Adversarial review of code + final docs.",
  };
  return m[label] || "Step in the BMAD migration pipeline.";
}

function nodeStatus(idx: number): "completed" | "running" | "pending" {
  // First 4 done, 5th running, rest pending
  if (idx < 4) return "completed";
  if (idx === 4) return "running";
  return "pending";
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: "bg-emerald-50 text-emerald-700",
    running:   "bg-amber-50 text-amber-700",
    pending:   "bg-zinc-100 text-ink-3",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium ${map[status]}`}>
      {status}
    </span>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === "completed") return <CheckCircle2 className="h-5 w-5 text-emerald-600" />;
  if (status === "running") return <CircleDot className="h-5 w-5 text-amber-600 animate-pulse" />;
  return <Circle className="h-5 w-5 text-zinc-400" />;
}

export function DemoAgentWorkflow() {
  return (
    <DemoShell title="Agent workflow" description="The BMAD-METHOD pipeline that orchestrates every migration project.">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className={`${card} lg:col-span-2`}>
          <h3 className="text-[14px] font-semibold text-ink mb-4">Pipeline run · BMAD-a8f3c2</h3>
          <ol className="space-y-2">
            {DEMO_AGENT_FLOW.map((label, i) => {
              const status = nodeStatus(i);
              const isHuman = label.includes("Approval") || label.includes("Final Review");
              const NodeIcon = isHuman ? UserCheck : Cpu;
              return (
                <li key={label}>
                  <div
                    className={
                      "flex items-start gap-3 p-3 rounded-lg border " +
                      (status === "running"
                        ? "bg-amber-50/40 border-amber-200 ring-1 ring-amber-200 animate-pulse"
                        : "bg-surface-muted border-zinc-200")
                    }
                  >
                    <StatusIcon status={status} />
                    <div className="h-8 w-8 rounded-md grid place-items-center bg-brand-50 text-brand-600 shrink-0">
                      <NodeIcon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="text-[13px] font-medium text-ink">{label}</div>
                        <StatusChip status={status} />
                      </div>
                      <div className="text-[12px] text-ink-3 mt-0.5">{describe(label)}</div>
                    </div>
                    <div className="text-[11px] text-ink-4 font-mono shrink-0">node {String(i + 1).padStart(2, "0")}</div>
                  </div>
                  {i < DEMO_AGENT_FLOW.length - 1 && (
                    <div className="flex justify-center py-1">
                      <ArrowDown className="h-3.5 w-3.5 text-ink-5" />
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </div>

        <div className="space-y-5">
          <div className={card}>
            <h3 className="text-[14px] font-semibold text-ink mb-2">Run summary</h3>
            <dl className="text-[12.5px] space-y-2">
              <Row k="Workflow ID"  v={DEMO_RUN.workflowId} mono />
              <Row k="Project"      v="P-1042" mono />
              <Row k="Started"      v="08:11 UTC" />
              <Row k="Elapsed"      v="2h 14m" />
              <Row k="Tokens"       v="184,302" />
              <Row k="Cost (est)"   v="$2.14" />
            </dl>
          </div>
          <div className={card}>
            <h3 className="text-[14px] font-semibold text-ink mb-2">Approval gates</h3>
            <p className="text-[12.5px] text-ink-3 leading-relaxed">
              Humans approve at two gates — after architecture, and before deploy.
              The pipeline pauses; agents resume when an admin signs off.
            </p>
          </div>
        </div>
      </div>
    </DemoShell>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-ink-4">{k}</dt>
      <dd className={`text-ink font-medium ${mono ? "font-mono text-[12px]" : ""}`}>{v}</dd>
    </div>
  );
}
