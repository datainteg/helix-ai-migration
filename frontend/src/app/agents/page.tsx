"use client";

/**
 * /agents — Agent workflows (BMAD pipeline).
 *
 * Visual layout ported from `Helix Figma Frontend/pages-agents.jsx`.
 * Demo data is inlined; replace each block with a `useQuery` call as backend
 * endpoints land.
 */

import { useEffect, useState } from "react";
import {
  Check,
  File as FileIcon,
  MoreHorizontal,
  Pause,
  Play,
  RefreshCw,
  X,
} from "lucide-react";

import { AppShell } from "@/components/layout";
import { AgentIcon } from "@/components/icons";
import {
  Avatar,
  Button,
  Card,
  StatusBadge,
  Tabs,
  DemoBanner,
  ErrorBanner,
} from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { listOrgWorkflowRuns, type WorkflowRun as ApiWorkflowRun } from "@/lib/workflows/api";

// ─── Demo data — TODO: hydrate from API ────────────────────────────

type NodeStatus = "completed" | "running" | "pending";

interface PipelineNodeData {
  id: string;
  phase: string;
  label: string;
  agent: string;
  role: string;
  status: NodeStatus;
  artifact: string | null;
  t: string;
  tokens: number;
}

interface WorkflowRun {
  id: string;
  project: string;
  status: string;
  started: string;
  mode: string;
  steps: string;
  duration: string;
}

const BMAD_PIPELINE: PipelineNodeData[] = [
  { id: "ctx",   phase: "Phase 0", label: "Project Context",     agent: "Winston", role: "Architect", status: "completed", artifact: "context.md",   t: "0:18", tokens: 1240 },
  { id: "an",    phase: "Phase 1", label: "Product Brief",       agent: "Mary",    role: "Analyst",   status: "completed", artifact: "brief.md",     t: "1:22", tokens: 4820 },
  { id: "pm",    phase: "Phase 2", label: "PRD",                 agent: "John",    role: "PM",        status: "completed", artifact: "prd_v1.md",    t: "2:04", tokens: 8214 },
  { id: "ux",    phase: "Phase 2", label: "UX Design",           agent: "Sally",   role: "Designer",  status: "completed", artifact: "ux_spec.md",   t: "1:41", tokens: 6312 },
  { id: "arch",  phase: "Phase 3", label: "Architecture",        agent: "Winston", role: "Architect", status: "completed", artifact: "arch.md",      t: "3:12", tokens: 9874 },
  { id: "stry",  phase: "Phase 3", label: "Epics & Stories",     agent: "Winston", role: "Architect", status: "completed", artifact: "epics.md",     t: "1:58", tokens: 5128 },
  { id: "rdy",   phase: "Phase 3", label: "Readiness Check",     agent: "Winston", role: "Architect", status: "completed", artifact: "readiness.md", t: "0:38", tokens: 1402 },
  { id: "gate",  phase: "Gate",    label: "Human Approval",      agent: "Human",   role: "Reviewer",  status: "completed", artifact: null,           t: "—",    tokens: 0 },
  { id: "story", phase: "Phase 4", label: "Story File",          agent: "Amelia",  role: "Engineer",  status: "completed", artifact: "story_1.md",   t: "0:48", tokens: 2104 },
  { id: "dev",   phase: "Phase 4", label: "Implementation",      agent: "Amelia",  role: "Engineer",  status: "running",   artifact: null,           t: "1:02", tokens: 3214 },
  { id: "qa",    phase: "Phase 4", label: "QA Tests",            agent: "Amelia",  role: "Engineer",  status: "pending",   artifact: null,           t: "—",    tokens: 0 },
  { id: "rev",   phase: "Phase 4", label: "Code Review",         agent: "Amelia",  role: "Engineer",  status: "pending",   artifact: null,           t: "—",    tokens: 0 },
  { id: "doc",   phase: "Phase 5", label: "Documentation",       agent: "Paige",   role: "Writer",    status: "pending",   artifact: null,           t: "—",    tokens: 0 },
];

const WORKFLOW_RUNS: WorkflowRun[] = [
  { id: "bmad-a8f3c2", project: "P-1042", status: "running",   started: "12:36:14", mode: "pydantic_ai", steps: "9 / 13",  duration: "6m 22s" },
  { id: "bmad-9d2e11", project: "P-1038", status: "awaiting",  started: "12:18:02", mode: "pydantic_ai", steps: "7 / 13",  duration: "18m 36s" },
  { id: "bmad-7b1a09", project: "P-1031", status: "failed",    started: "11:42:51", mode: "llm",         steps: "10 / 13", duration: "53m 22s" },
  { id: "bmad-6c4d8e", project: "P-1025", status: "running",   started: "10:05:33", mode: "pydantic_ai", steps: "11 / 13", duration: "2h 31m" },
  { id: "bmad-5a2f01", project: "P-1019", status: "completed", started: "09:48:12", mode: "pydantic_ai", steps: "13 / 13", duration: "47m 02s" },
  { id: "bmad-4e9c33", project: "P-1041", status: "completed", started: "08:12:07", mode: "pydantic_ai", steps: "13 / 13", duration: "1h 08m" },
];

const TOKEN_USAGE = [
  { agent: "Amelia",  v: 18204, color: "#7C3AED" },
  { agent: "Winston", v: 11402, color: "#0F766E" },
  { agent: "John",    v: 6214,  color: "#1E3A8A" },
  { agent: "Sally",   v: 4112,  color: "#7C2D12" },
  { agent: "Mary",    v: 2376,  color: "#374151" },
];

const PHASE_GROUPS = [
  { key: "p0",   label: "Phase 0", caption: "Setup" },
  { key: "p1",   label: "Phase 1", caption: "Analysis" },
  { key: "p2",   label: "Phase 2", caption: "Planning" },
  { key: "p3",   label: "Phase 3", caption: "Solutioning" },
  { key: "gate", label: "Gate",    caption: "Human approval" },
  { key: "p4",   label: "Phase 4", caption: "Implementation" },
  { key: "p5",   label: "Phase 5", caption: "Docs" },
] as const;

type PhaseKey = (typeof PHASE_GROUPS)[number]["key"];

// ─── Helpers ────────────────────────────────────────────────────────

function fmtShort(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function phaseColor(phase: string): { fg: string; bg: string } {
  if (phase.includes("0")) return { fg: "var(--con-ink-3)", bg: "var(--con-bg-2)" };
  if (phase.includes("1")) return { fg: "var(--con-brand)", bg: "var(--con-brand-soft)" };
  if (phase.includes("2")) return { fg: "var(--con-info)", bg: "var(--con-info-soft)" };
  if (phase.includes("3")) return { fg: "var(--con-warn)", bg: "var(--con-warn-soft)" };
  if (phase.includes("4")) return { fg: "var(--con-ok)", bg: "var(--con-ok-soft)" };
  if (phase.includes("5")) return { fg: "var(--con-ink-3)", bg: "var(--con-bg-2)" };
  if (phase === "Gate")    return { fg: "var(--con-err)", bg: "var(--con-err-soft)" };
  return { fg: "var(--con-ink-3)", bg: "var(--con-bg-2)" };
}

function groupOf(phase: string): PhaseKey {
  if (phase.includes("0")) return "p0";
  if (phase.includes("1")) return "p1";
  if (phase.includes("2")) return "p2";
  if (phase.includes("3")) return "p3";
  if (phase === "Gate")    return "gate";
  if (phase.includes("4")) return "p4";
  if (phase.includes("5")) return "p5";
  return "p5";
}

// ─── Page ───────────────────────────────────────────────────────────

export default function AgentsPage() {
  const { token } = useAuth();
  const [realRuns, setRealRuns] = useState<ApiWorkflowRun[] | null>(null);
  const [loadError, setLoadError] = useState<string>("");

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    listOrgWorkflowRuns(token, 100)
      .then((rows) => { if (!cancelled) setRealRuns(rows); })
      .catch((e: unknown) => { if (!cancelled) { setRealRuns([]); setLoadError((e instanceof Error ? e.message : null) ?? "Failed to load workflow runs"); } });
    return () => { cancelled = true; };
  }, [token]);

  // Pipeline/timeline visualisations stay backed by BMAD_PIPELINE demo data
  // until per-run step detail is wired (next workstream). Top-level run list,
  // counts, and selection use real backend data when present.
  const displayRuns: WorkflowRun[] = (realRuns && realRuns.length > 0)
    ? realRuns.map((r) => ({
        id: r.workflow_id,
        project: r.project_id,
        status: r.status,
        started: r.created_at ? new Date(r.created_at).toLocaleTimeString() : "—",
        mode: r.mode,
        steps: "—",
        duration: "—",
      }))
    : WORKFLOW_RUNS;

  const firstRun = displayRuns[0]!;
  const [selectedRun, setSelectedRun] = useState<string>(firstRun.id);
  const [layout, setLayout] = useState<string>("linear");
  const run = displayRuns.find((r) => r.id === selectedRun) ?? firstRun;

  const runningCount = displayRuns.filter((r) => r.status === "running" || r.status === "started").length;
  const awaitingCount = displayRuns.filter((r) => r.status === "awaiting" || r.status === "awaiting_approval" || r.status === "pending").length;
  const failedCount = displayRuns.filter((r) => r.status === "failed" || r.status === "rejected" || r.status === "expired").length;
  const metricLine = `${displayRuns.length} runs · ${awaitingCount} awaiting · ${failedCount} failed`;
  const usingRealData = (realRuns?.length ?? 0) > 0;

  return (
    <AppShell
      eyebrow="BMAD MULTI-AGENT ORCHESTRATION"
      title="Agent workflows"
      metric={metricLine}
      description="Live view of the 13-node BMAD migration pipeline. Mary → John → Sally → Winston → Amelia → Paige."
      actions={
        <>
          <Tabs
            value={layout}
            onChange={setLayout}
            tabs={[
              { id: "linear", label: "Linear" },
              { id: "phases", label: "Phases" },
            ]}
          />
          <Button variant="outline"><RefreshCw className="h-3.5 w-3.5" /> Refresh</Button>
          <Button variant="primary"><Play className="h-3 w-3" /> Start workflow</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {loadError && <ErrorBanner message={loadError} onDismiss={() => setLoadError("")} />}
        {!usingRealData && (
          <DemoBanner message="Run list shown here is sample. Once your first BMAD workflow lands the table populates from /agent-workflows." />
        )}
        {layout === "phases" ? (
          <PhasesView run={run} runs={displayRuns} selectedRun={selectedRun} setSelectedRun={setSelectedRun} />
        ) : (
          <LinearView run={run} runs={displayRuns} selectedRun={selectedRun} setSelectedRun={setSelectedRun} />
        )}
      </div>
    </AppShell>
  );
}

// ─── Linear view ────────────────────────────────────────────────────

interface ViewProps {
  run: WorkflowRun;
  runs: WorkflowRun[];
  selectedRun: string;
  setSelectedRun: (id: string) => void;
}

function LinearView({ run, selectedRun, setSelectedRun }: ViewProps) {
  return (
    <div className="grid gap-4" style={{ gridTemplateColumns: "280px minmax(0, 1fr) 280px" }}>
      {/* Workflow runs sidebar */}
      <Card title="Runs" eyebrow="6 TOTAL" padding="md" bodyClassName="p-0 pb-2">
        <div className="border-t border-hx">
          {WORKFLOW_RUNS.map((r, i) => {
            const active = r.id === selectedRun;
            return (
              <button
                key={r.id}
                onClick={() => setSelectedRun(r.id)}
                className="w-full flex flex-col gap-1.5 px-[18px] py-[11px] text-left bg-transparent"
                style={{
                  background: active ? "var(--con-surface-hi)" : "transparent",
                  borderBottom: i === WORKFLOW_RUNS.length - 1 ? "none" : "1px solid var(--con-line)",
                  borderLeft: `2px solid ${active ? "var(--con-ink-1)" : "transparent"}`,
                }}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] text-ink-2 font-medium">
                    {r.id.replace("bmad-", "")}
                  </span>
                  <StatusBadge status={r.status} />
                </div>
                <div className="flex items-center justify-between text-[11px] text-ink-4">
                  <span className="font-mono">{r.project} · {r.started}</span>
                  <span className="font-mono">{r.steps}</span>
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Pipeline */}
      <div className="flex flex-col gap-4 min-w-0">
        <Card padding="md">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="eyebrow">WORKFLOW · {run.id}</div>
              <div className="text-[16px] font-semibold mt-1 flex items-center gap-2.5">
                Oracle GL → Snowflake
                <StatusBadge status={run.status} />
              </div>
              <div className="text-[12px] text-ink-3 mt-1">
                Started <span className="font-mono">{run.started}</span> · Mode{" "}
                <span className="font-mono">{run.mode}</span> · Duration{" "}
                <span className="font-mono">{run.duration}</span>
              </div>
            </div>
            <div className="flex gap-1.5">
              <Button variant="outline" size="sm"><Pause className="h-3 w-3" /> Pause</Button>
              <Button variant="outline" size="sm"><X className="h-3 w-3" /> Cancel</Button>
              <Button variant="ghost" size="icon" aria-label="More actions"><MoreHorizontal className="h-3.5 w-3.5" /></Button>
            </div>
          </div>

          {/* The pipeline */}
          <div className="flex flex-col gap-3.5 py-2">
            {BMAD_PIPELINE.map((node, i) => (
              <PipelineNode key={node.id} node={node} index={i} />
            ))}
          </div>
        </Card>
      </div>

      {/* Right rail */}
      <div className="flex flex-col gap-4">
        <Card title="Workflow details" padding="md">
          <dl className="flex flex-col gap-3 m-0 text-[12.5px]">
            {(
              [
                ["Workflow ID", run.id, true],
                ["Project", run.project, true],
                ["Mode", run.mode, true],
                ["Status", <StatusBadge key="s" status={run.status} />, false],
                ["Steps", run.steps, true],
                ["Started", run.started, true],
                ["Duration", run.duration, true],
              ] as [string, React.ReactNode, boolean][]
            ).map(([k, v, mono]) => (
              <div key={k} className="flex justify-between items-center gap-2">
                <dt className="eyebrow" style={{ fontSize: "9.5px" }}>{k}</dt>
                <dd
                  className="m-0 text-ink"
                  style={{
                    fontFamily: mono ? "var(--font-mono, Geist Mono)" : "inherit",
                    fontSize: mono ? "11.5px" : "12.5px",
                  }}
                >
                  {v}
                </dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card title="Token usage" eyebrow="SESSION · USD 4.82">
          <div className="flex items-baseline gap-2 mb-3">
            <span className="font-mono tabular-nums text-[26px] font-medium tracking-[-0.02em]">42,308</span>
            <span className="text-[12px] text-ink-3">tokens</span>
          </div>
          <div className="flex flex-col gap-1.5">
            {TOKEN_USAGE.map((row) => (
              <div
                key={row.agent}
                className="grid items-center gap-2 text-[11.5px]"
                style={{ gridTemplateColumns: "60px 1fr 60px" }}
              >
                <span className="text-ink-2">{row.agent}</span>
                <div className="h-1 bg-app-2 rounded-sm overflow-hidden">
                  <div
                    className="h-full rounded-sm"
                    style={{ width: `${(row.v / 18204) * 100}%`, background: row.color }}
                  />
                </div>
                <span className="font-mono tabular-nums text-ink-3 text-[11px] text-right">
                  {fmtShort(row.v)}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Artifacts" eyebrow="6 GENERATED">
          <div className="flex flex-col gap-px">
            {BMAD_PIPELINE.filter((n) => n.artifact).map((n, i, arr) => (
              <button
                key={n.id}
                className="grid items-center gap-2.5 py-[7px] text-left bg-transparent"
                style={{
                  gridTemplateColumns: "16px 1fr auto",
                  borderBottom: i === arr.length - 1 ? "none" : "1px solid var(--con-line)",
                }}
              >
                <FileIcon className="h-3.5 w-3.5 text-ink-4" />
                <span className="font-mono text-[11.5px] text-ink-2">{n.artifact}</span>
                <span className="inline-flex items-center gap-1 text-[10.5px] text-ink-4">
                  <AgentIcon name={n.agent} size={14} /> {n.agent}
                </span>
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

// ─── Linear pipeline node ───────────────────────────────────────────

function PipelineNode({ node, index }: { node: PipelineNodeData; index: number }) {
  const colors = phaseColor(node.phase);
  const isRunning = node.status === "running";
  const isCompleted = node.status === "completed";
  const isPending = node.status === "pending";

  const statusIcon = isCompleted ? (
    <Check className="h-2.5 w-2.5" />
  ) : isRunning ? (
    <span
      className="rounded-full animate-spin"
      style={{
        width: 11,
        height: 11,
        border: "2px solid var(--con-brand)",
        borderRightColor: "transparent",
      }}
    />
  ) : (
    <span className="rounded-full" style={{ width: 5, height: 5, background: "var(--con-ink-5)" }} />
  );

  return (
    <div className="relative">
      {index > 0 && (
        <div
          className="absolute"
          style={{
            left: 19,
            top: -14,
            height: 14,
            width: 1,
            background: "var(--con-line-2)",
          }}
        />
      )}
      <div className="grid items-stretch gap-3" style={{ gridTemplateColumns: "40px 1fr" }}>
        <div className="flex flex-col items-center">
          <div
            className="rounded-full grid place-items-center font-mono font-semibold relative"
            style={{
              width: 24,
              height: 24,
              background: isCompleted
                ? "var(--con-ink-1)"
                : isRunning
                  ? "var(--con-brand)"
                  : "var(--con-surface)",
              border: isCompleted || isRunning ? "none" : "1px solid var(--con-line-2)",
              color: isCompleted || isRunning ? "#FFF" : "var(--con-ink-4)",
              fontSize: "10.5px",
              zIndex: 1,
            }}
          >
            {statusIcon}
          </div>
        </div>

        <div
          className="bg-surface rounded-lg"
          style={{
            border: "1px solid",
            borderColor: isRunning ? "var(--con-brand)" : "var(--con-line)",
            padding: "12px 14px",
            boxShadow: isRunning ? "0 0 0 3px rgba(79,70,229,0.08)" : "var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04))",
            opacity: isPending ? 0.55 : 1,
          }}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <span
                className="font-mono"
                style={{
                  fontSize: "9.5px",
                  fontWeight: 500,
                  color: colors.fg,
                  background: colors.bg,
                  padding: "1px 7px",
                  borderRadius: 3,
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                }}
              >
                {node.phase}
              </span>
              <span className="text-[13.5px] font-medium">{node.label}</span>
              <span className="inline-flex items-center gap-1.5">
                <AgentIcon name={node.agent} size={16} />
                <span className="font-mono text-[11.5px] text-ink-3">{node.agent}</span>
              </span>
            </div>
            <div className="flex items-center gap-2.5">
              {node.tokens > 0 && (
                <span className="font-mono text-[11px] text-ink-4">{fmtShort(node.tokens)} tok</span>
              )}
              <span
                className="font-mono tabular-nums text-[11px] text-ink-3 text-right"
                style={{ minWidth: 36 }}
              >
                {node.t}
              </span>
              {node.artifact && (
                <button
                  className="inline-flex items-center gap-1 bg-transparent border-none rounded font-mono"
                  style={{
                    padding: "2px 6px",
                    color: "var(--con-brand)",
                    fontSize: "11px",
                  }}
                >
                  <FileIcon className="h-2.5 w-2.5" /> {node.artifact}
                </button>
              )}
              <StatusBadge status={node.status} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Phases view ────────────────────────────────────────────────────

function PhasesView({ run, runs, selectedRun, setSelectedRun }: ViewProps) {
  const grouped: Record<PhaseKey, PipelineNodeData[]> = {
    p0: [], p1: [], p2: [], p3: [], gate: [], p4: [], p5: [],
  };
  PHASE_GROUPS.forEach((g) => {
    grouped[g.key] = BMAD_PIPELINE.filter((n) => groupOf(n.phase) === g.key);
  });
  const gateStatus = grouped.gate[0]?.status;

  return (
    <div className="flex flex-col gap-4">
      {/* Run picker strip */}
      <Card padding="md" bodyClassName="p-0">
        <div className="flex overflow-x-auto border-t border-hx">
          {runs.map((r, i) => {
            const active = r.id === selectedRun;
            return (
              <button
                key={r.id}
                onClick={() => setSelectedRun(r.id)}
                className="flex flex-col gap-1 px-4 py-[11px] text-left bg-transparent"
                style={{
                  flex: "0 0 auto",
                  minWidth: 180,
                  background: active ? "var(--con-surface-hi)" : "transparent",
                  borderRight: i === runs.length - 1 ? "none" : "1px solid var(--con-line)",
                  borderTop: `2px solid ${active ? "var(--con-ink-1)" : "transparent"}`,
                  marginTop: -1,
                }}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] text-ink-2 font-medium">
                    {r.id.replace("bmad-", "")}
                  </span>
                  <StatusBadge status={r.status} />
                </div>
                <div className="flex items-center justify-between text-[10.5px] text-ink-4">
                  <span className="font-mono">{r.project}</span>
                  <span className="font-mono">{r.steps}</span>
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Workflow header */}
      <Card padding="md">
        <div className="flex items-center justify-between">
          <div>
            <div className="eyebrow">WORKFLOW · {run.id} · {run.mode}</div>
            <div className="text-[16px] font-semibold mt-1 flex items-center gap-2.5">
              Oracle GL → Snowflake
              <StatusBadge status={run.status} />
            </div>
          </div>
          <div className="flex gap-1.5">
            <Button variant="outline" size="sm"><Pause className="h-3 w-3" /> Pause</Button>
            <Button variant="outline" size="sm"><X className="h-3 w-3" /> Cancel</Button>
          </div>
        </div>
      </Card>

      {/* Swim-lanes canvas */}
      <Card padding="md" bodyClassName="p-0">
        <div
          className="bg-surface border-t border-hx overflow-x-auto"
          style={{ padding: "20px 24px" }}
        >
          {/* Phase headers */}
          <div
            className="grid gap-3 mb-3.5"
            style={{ gridTemplateColumns: "repeat(7, minmax(150px, 1fr))" }}
          >
            {PHASE_GROUPS.map((g) => (
              <div key={g.key} className="flex flex-col gap-[3px] items-start">
                <div
                  className="eyebrow"
                  style={{
                    fontSize: "9.5px",
                    color: g.key === "gate" ? "var(--con-warn)" : "var(--con-ink-4)",
                  }}
                >
                  {g.label}
                </div>
                <div className="text-[11.5px] text-ink-2 font-medium">{g.caption}</div>
                <div
                  className="w-full mt-1"
                  style={{
                    height: 2,
                    background: g.key === "gate" ? "var(--con-warn)" : "var(--con-line-2)",
                  }}
                />
              </div>
            ))}
          </div>

          {/* Nodes by phase */}
          <div
            className="grid gap-3 items-start relative"
            style={{ gridTemplateColumns: "repeat(7, minmax(150px, 1fr))" }}
          >
            {PHASE_GROUPS.map((g) => (
              <div key={g.key} className="flex flex-col gap-2.5">
                {g.key === "gate" ? (
                  <GateNode status={gateStatus} />
                ) : (
                  grouped[g.key].map((n) => <PhaseNode key={n.id} node={n} />)
                )}
              </div>
            ))}
          </div>

          {/* Rejected branch */}
          <div className="mt-6 pt-[18px]" style={{ borderTop: "1px dashed var(--con-line-2)" }}>
            <div className="flex items-center gap-4">
              <div className="eyebrow" style={{ fontSize: "9.5px", color: "var(--con-err)" }}>
                REJECTED BRANCH
              </div>
              <div className="flex-1 h-px bg-[var(--con-line)]" />
            </div>
            <div className="flex items-center gap-3.5 mt-3">
              <div
                className="rounded-full"
                style={{
                  width: 14,
                  height: 14,
                  border: "2px solid var(--con-err)",
                  background: "var(--con-surface)",
                  marginLeft: 12,
                }}
              />
              <div
                className="rounded-md flex items-center gap-2"
                style={{
                  fontSize: "12px",
                  padding: "8px 12px",
                  background: "var(--con-err-soft)",
                  color: "var(--con-err)",
                  border: "1px solid #FCA5A5",
                  fontFamily: "var(--font-mono, Geist Mono)",
                }}
              >
                <X className="h-3 w-3" />
                <span style={{ fontFamily: "var(--font-sans, Geist)" }}>
                  Workflow terminates · changes requested by reviewer
                </span>
              </div>
              <span className="flex-1" />
              <span className="font-mono text-[10.5px] text-ink-4">
                NO ARTIFACTS · NO BILLING
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* Below: details + tokens + artifacts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Workflow details" padding="md">
          <dl className="flex flex-col gap-2.5 m-0 text-[12.5px]">
            {(
              [
                ["Workflow ID", run.id, true],
                ["Project", run.project, true],
                ["Mode", run.mode, true],
                ["Steps", run.steps, true],
                ["Duration", run.duration, true],
              ] as [string, string, boolean][]
            ).map(([k, v, mono]) => (
              <div key={k} className="flex justify-between gap-2">
                <dt className="eyebrow" style={{ fontSize: "9.5px" }}>{k}</dt>
                <dd
                  className="m-0 text-ink"
                  style={{
                    fontFamily: mono ? "var(--font-mono, Geist Mono)" : "inherit",
                    fontSize: mono ? "11.5px" : "12.5px",
                  }}
                >
                  {v}
                </dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card title="Token usage" eyebrow="SESSION · USD 4.82">
          <div className="flex items-baseline gap-2 mb-2.5">
            <span className="font-mono tabular-nums text-[24px] font-medium tracking-[-0.02em]">42,308</span>
            <span className="text-[11px] text-ink-3">tokens</span>
          </div>
          {TOKEN_USAGE.slice(0, 4).map((row) => (
            <div
              key={row.agent}
              className="grid items-center gap-2 text-[11.5px] py-[3px]"
              style={{ gridTemplateColumns: "60px 1fr 60px" }}
            >
              <span className="text-ink-2">{row.agent}</span>
              <div className="h-1 bg-app-2 rounded-sm">
                <div
                  className="h-full rounded-sm"
                  style={{ width: `${(row.v / 18204) * 100}%`, background: row.color }}
                />
              </div>
              <span className="font-mono tabular-nums text-ink-3 text-[11px] text-right">
                {fmtShort(row.v)}
              </span>
            </div>
          ))}
        </Card>

        <Card title="Artifacts" eyebrow={`${BMAD_PIPELINE.filter((n) => n.artifact).length} GENERATED`}>
          <div className="flex flex-col gap-px">
            {BMAD_PIPELINE.filter((n) => n.artifact).map((n, i, arr) => (
              <button
                key={n.id}
                className="grid items-center gap-2.5 py-1.5 text-left bg-transparent"
                style={{
                  gridTemplateColumns: "16px 1fr auto",
                  borderBottom: i === arr.length - 1 ? "none" : "1px solid var(--con-line)",
                }}
              >
                <FileIcon className="h-3 w-3 text-ink-4" />
                <span className="font-mono text-[11px] text-ink-2">{n.artifact}</span>
                <span className="text-[10px] text-ink-4">{n.agent}</span>
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

// ─── Phase node + Gate node ─────────────────────────────────────────

function PhaseNode({ node }: { node: PipelineNodeData }) {
  const isRunning = node.status === "running";
  const isCompleted = node.status === "completed";
  const isPending = node.status === "pending";

  const icon = isCompleted ? (
    <Check className="h-2.5 w-2.5" />
  ) : isRunning ? (
    <span
      className="rounded-full animate-spin"
      style={{
        width: 10,
        height: 10,
        border: "2px solid var(--con-brand)",
        borderRightColor: "transparent",
      }}
    />
  ) : (
    <span className="rounded-full" style={{ width: 5, height: 5, background: "var(--con-ink-5)" }} />
  );

  return (
    <div
      className="bg-surface rounded-lg flex flex-col gap-1.5"
      style={{
        border: "1px solid",
        borderColor: isRunning ? "var(--con-brand)" : "var(--con-line)",
        padding: "10px 12px",
        boxShadow: isRunning ? "0 0 0 3px rgba(79,70,229,0.08)" : "var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04))",
        opacity: isPending ? 0.55 : 1,
      }}
    >
      <div className="flex items-center gap-1.5">
        <div
          className="rounded-full grid place-items-center text-white flex-shrink-0"
          style={{
            width: 18,
            height: 18,
            background: isCompleted
              ? "var(--con-ink-1)"
              : isRunning
                ? "var(--con-brand)"
                : "var(--con-surface)",
            border: isCompleted || isRunning ? "none" : "1px solid var(--con-line-2)",
          }}
        >
          {icon}
        </div>
        <span className="text-[12px] font-medium leading-tight flex-1 min-w-0">{node.label}</span>
      </div>
      <div className="flex items-center gap-1.5" style={{ paddingLeft: 24 }}>
        <AgentIcon name={node.agent} size={14} />
        <span className="font-mono text-[10.5px] text-ink-3">{node.agent}</span>
        {node.t !== "—" && (
          <span className="font-mono text-[10px] text-ink-4 ml-auto">{node.t}</span>
        )}
      </div>
      {node.artifact && (
        <div className="flex items-center gap-1" style={{ paddingLeft: 24 }}>
          <FileIcon className="h-2.5 w-2.5" style={{ color: "var(--con-brand)" }} />
          <span className="font-mono text-[10.5px]" style={{ color: "var(--con-brand)" }}>
            {node.artifact}
          </span>
        </div>
      )}
    </div>
  );
}

function GateNode({ status }: { status: NodeStatus | undefined }) {
  const completed = status === "completed";
  return (
    <div
      className="rounded-lg flex flex-col gap-2"
      style={{
        background: completed ? "var(--con-surface)" : "var(--con-warn-soft)",
        border: `1.5px solid ${completed ? "var(--con-ok)" : "var(--con-warn)"}`,
        padding: "10px 12px",
      }}
    >
      <div className="flex items-center gap-1.5">
        <span
          className="inline-block"
          style={{
            width: 12,
            height: 12,
            background: completed ? "var(--con-ok)" : "var(--con-warn)",
            transform: "rotate(45deg)",
          }}
        />
        <span
          className="text-[12px] font-semibold"
          style={{ color: completed ? "var(--con-ok)" : "var(--con-warn)" }}
        >
          Human Gate
        </span>
      </div>
      <div className="flex items-center gap-1.5" style={{ paddingLeft: 18 }}>
        <Avatar name="@priya" size={14} />
        <span className="font-mono text-[10.5px] text-ink-3">@priya</span>
        <span className="font-mono text-[10px] text-ink-4 ml-auto">0:12</span>
      </div>
      <div className="flex flex-col gap-1 mt-0.5" style={{ paddingLeft: 18 }}>
        <div
          className="flex items-center gap-1 font-mono"
          style={{
            fontSize: "10.5px",
            color: completed ? "var(--con-ok)" : "var(--con-ink-4)",
          }}
        >
          <span style={{ width: 14, height: 1, background: "currentColor" }} />
          → APPROVED
        </div>
        <div
          className="flex items-center gap-1 font-mono"
          style={{
            fontSize: "10.5px",
            color: "var(--con-err)",
            opacity: 0.5,
          }}
        >
          <span style={{ width: 14, height: 1, background: "currentColor" }} />
          ↘ REJECTED
        </div>
      </div>
    </div>
  );
}
