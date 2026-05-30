"use client";

/**
 * /agents — Agent workflows (BMAD pipeline).
 *
 * Visual layout ported from `Helix Figma Frontend/pages-agents.jsx`.
 * Run list + pipeline steps are hydrated from the backend
 * (`/api/v1/agent-workflows` and `/api/v1/agent-workflows/{id}`). Sections
 * with no backend data yet render a clean empty state — never sample data.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Check,
  File as FileIcon,
  Play,
  RefreshCw,
  ExternalLink,
} from "lucide-react";

import { AppShell } from "@/components/layout";
import { AgentIcon } from "@/components/icons";
import {
  Button,
  Card,
  EmptyState,
  StatusBadge,
  Tabs,
  ErrorBanner,
  Modal,
} from "@/components/ui";
import { Markdown } from "@/components/ui/Markdown";
import { useAuth } from "@/lib/auth-context";
import {
  listOrgWorkflowRuns,
  getWorkflowDetail,
  getWorkflowArtifact,
  type WorkflowRun as ApiWorkflowRun,
  type WorkflowStep as ApiWorkflowStep,
} from "@/lib/workflows/api";

// ─── View models ────────────────────────────────────────────────────

type NodeStatus = "completed" | "running" | "pending";

interface PipelineNodeData {
  id: string;
  label: string;
  agent: string;
  status: NodeStatus;
  artifact: string | null;       // display name (last path segment)
  artifactPath: string | null;   // full path, for fetching content
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

// ─── Helpers ────────────────────────────────────────────────────────

/** Normalise a backend step status onto the three pipeline node states. */
function nodeStatus(raw: string | null | undefined): NodeStatus {
  const s = (raw ?? "").toLowerCase();
  if (s === "completed" || s === "approved" || s === "done" || s === "succeeded") return "completed";
  if (s === "running" || s === "started" || s === "in_progress") return "running";
  return "pending";
}

/** Last path segment of an artifact path, for compact display. */
function artifactName(path: string | null | undefined): string | null {
  if (!path) return null;
  const parts = path.split("/").filter(Boolean);
  return parts.length ? parts[parts.length - 1]! : path;
}

/** Map backend workflow steps onto pipeline node view models. */
function stepsToNodes(steps: ApiWorkflowStep[]): PipelineNodeData[] {
  return steps.map((s) => ({
    id: `${s.agent_name}-${s.step_order}`,
    label: s.agent_name,
    agent: s.agent_name,
    status: nodeStatus(s.status),
    artifact: artifactName(s.artifact_path),
    artifactPath: s.artifact_path ?? null,
  }));
}

// ─── Page ───────────────────────────────────────────────────────────

export default function AgentsPage() {
  const { token } = useAuth();
  const [realRuns, setRealRuns] = useState<ApiWorkflowRun[] | null>(null);
  const [loadError, setLoadError] = useState<string>("");
  const [refreshing, setRefreshing] = useState(false);

  const loadRuns = () => {
    if (!token) return Promise.resolve();
    setRefreshing(true);
    return listOrgWorkflowRuns(token, 100)
      .then((rows) => { setRealRuns(rows); setLoadError(""); })
      .catch((e: unknown) => { setRealRuns([]); setLoadError((e instanceof Error ? e.message : null) ?? "Failed to load workflow runs"); })
      .finally(() => setRefreshing(false));
  };

  useEffect(() => {
    if (!token) return;
    void loadRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const refresh = () => { void loadRuns(); };

  const displayRuns: WorkflowRun[] = (realRuns ?? []).map((r) => ({
    id: r.workflow_id,
    project: r.project_id,
    status: r.status,
    started: r.created_at ? new Date(r.created_at).toLocaleTimeString() : "—",
    mode: r.mode,
    steps: "—",      // populated for the selected run from its step detail
    duration: "—",
  }));

  const [selectedRun, setSelectedRun] = useState<string>("");
  const [layout, setLayout] = useState<string>("linear");

  // Keep the selection valid as runs arrive; default to the first run.
  useEffect(() => {
    if (displayRuns.length === 0) {
      if (selectedRun) setSelectedRun("");
      return;
    }
    if (!displayRuns.some((r) => r.id === selectedRun)) {
      setSelectedRun(displayRuns[0]!.id);
    }
  }, [displayRuns, selectedRun]);

  const run = displayRuns.find((r) => r.id === selectedRun) ?? null;

  // Per-run step detail (pipeline + artifacts) from the real backend endpoint.
  const [nodes, setNodes] = useState<PipelineNodeData[] | null>(null);
  const [stepsError, setStepsError] = useState<string>("");

  useEffect(() => {
    if (!token || !selectedRun) { setNodes(null); return; }
    let cancelled = false;
    setNodes(null);
    setStepsError("");
    getWorkflowDetail(token, selectedRun)
      .then((detail) => { if (!cancelled) setNodes(stepsToNodes(detail.steps ?? [])); })
      .catch((e: unknown) => { if (!cancelled) { setNodes([]); setStepsError((e instanceof Error ? e.message : null) ?? "Failed to load workflow steps"); } });
    return () => { cancelled = true; };
  }, [token, selectedRun]);

  // Artifact viewer modal — opens the raw content for a clicked artifact.
  const [artifactView, setArtifactView] = useState<{ name: string; path: string } | null>(null);
  const openArtifact = (node: PipelineNodeData) => {
    if (node.artifactPath) setArtifactView({ name: node.artifact ?? node.artifactPath, path: node.artifactPath });
  };

  const awaitingCount = displayRuns.filter((r) => r.status === "awaiting" || r.status === "awaiting_approval" || r.status === "pending").length;
  const failedCount = displayRuns.filter((r) => r.status === "failed" || r.status === "rejected" || r.status === "expired").length;
  const metricLine = `${displayRuns.length} runs · ${awaitingCount} awaiting · ${failedCount} failed`;

  return (
    <AppShell
      eyebrow="BMAD MULTI-AGENT ORCHESTRATION"
      title="Agent workflows"
      metric={metricLine}
      description="Live view of the 13-step BMAD migration pipeline, driven by 6 agents — Mary, John, Sally, Winston, Amelia, Paige."
      crumbs={["Agents"]}
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
          <Button variant="outline" onClick={refresh} loading={refreshing}><RefreshCw className="h-3.5 w-3.5" /> Refresh</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {loadError && <ErrorBanner message={loadError} onDismiss={() => setLoadError("")} />}
        {displayRuns.length === 0 ? (
          <Card padding="md">
            <EmptyState
              icon={<Play className="h-4 w-4" />}
              title="No workflow runs yet"
              description="Start a BMAD workflow and it will appear here, hydrated live from /agent-workflows."
            />
          </Card>
        ) : layout === "phases" ? (
          <PhasesView run={run} runs={displayRuns} nodes={nodes} stepsError={stepsError} selectedRun={selectedRun} setSelectedRun={setSelectedRun} onOpenArtifact={openArtifact} />
        ) : (
          <LinearView run={run} runs={displayRuns} nodes={nodes} stepsError={stepsError} selectedRun={selectedRun} setSelectedRun={setSelectedRun} onOpenArtifact={openArtifact} />
        )}
      </div>

      {artifactView && (
        <ArtifactViewer
          workflowId={selectedRun}
          name={artifactView.name}
          path={artifactView.path}
          token={token}
          onClose={() => setArtifactView(null)}
        />
      )}
    </AppShell>
  );
}

function ArtifactViewer({ workflowId, name, path, token, onClose }: { workflowId: string; name: string; path: string; token: string | null; onClose: () => void }) {
  const [content, setContent] = useState<string | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let cancelled = false;
    getWorkflowArtifact(token, workflowId, path)
      .then((r) => { if (!cancelled) setContent(r.content); })
      .catch((e: unknown) => { if (!cancelled) setErr(e instanceof Error ? e.message : "Failed to load artifact"); });
    return () => { cancelled = true; };
  }, [token, workflowId, path]);
  return (
    <Modal open onClose={onClose} title={name} width="lg">
      {err ? (
        <ErrorBanner message={err} />
      ) : content === null ? (
        <div className="py-8 text-center text-[12.5px] text-ink-4">Loading artifact…</div>
      ) : (
        <div className="max-h-[60vh] overflow-auto rounded-lg border border-hx bg-app-2 p-3">
          <Markdown text={content} />
        </div>
      )}
    </Modal>
  );
}

// ─── Shared section: token usage (no backend data → empty state) ──────

function TokenUsageCard() {
  return (
    <Card title="Token usage">
      <EmptyState
        title="No token usage yet"
        description="Per-agent token and cost accounting is not reported by the workflow backend yet."
      />
    </Card>
  );
}

// ─── Linear view ────────────────────────────────────────────────────

interface ViewProps {
  run: WorkflowRun | null;
  runs: WorkflowRun[];
  nodes: PipelineNodeData[] | null;
  stepsError: string;
  selectedRun: string;
  setSelectedRun: (id: string) => void;
  onOpenArtifact: (node: PipelineNodeData) => void;
}

function LinearView({ run, runs, nodes, stepsError, selectedRun, setSelectedRun, onOpenArtifact }: ViewProps) {
  const artifacts = (nodes ?? []).filter((n) => n.artifact);

  return (
    <div className="grid gap-4" style={{ gridTemplateColumns: "280px minmax(0, 1fr) 280px" }}>
      {/* Workflow runs sidebar */}
      <Card title="Runs" eyebrow={`${runs.length} TOTAL`} padding="md" bodyClassName="p-0 pb-2">
        <div className="border-t border-hx">
          {runs.map((r, i) => {
            const active = r.id === selectedRun;
            return (
              <button
                key={r.id}
                onClick={() => setSelectedRun(r.id)}
                className="w-full flex flex-col gap-1.5 px-[18px] py-[11px] text-left bg-transparent"
                style={{
                  background: active ? "var(--con-surface-hi)" : "transparent",
                  borderBottom: i === runs.length - 1 ? "none" : "1px solid var(--con-line)",
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
              <div className="eyebrow">WORKFLOW · {run?.id ?? "—"}</div>
              <div className="text-[16px] font-semibold mt-1 flex items-center gap-2.5">
                {run?.project ?? "—"}
                {run && <StatusBadge status={run.status} />}
              </div>
              <div className="text-[12px] text-ink-3 mt-1">
                Started <span className="font-mono">{run?.started ?? "—"}</span> · Mode{" "}
                <span className="font-mono">{run?.mode ?? "—"}</span> · Steps{" "}
                <span className="font-mono">{nodes ? `${nodes.filter((n) => n.status === "completed").length}/${nodes.length}` : "—"}</span>
              </div>
            </div>
            {run?.project && (
              <Link href={`/projects/${run.project}`}>
                <Button variant="outline" size="sm"><ExternalLink className="h-3 w-3" /> View project</Button>
              </Link>
            )}
          </div>

          {/* The pipeline */}
          {stepsError ? (
            <EmptyState title="Couldn't load pipeline" description={stepsError} />
          ) : nodes === null ? (
            <EmptyState title="Loading pipeline…" />
          ) : nodes.length === 0 ? (
            <EmptyState title="No pipeline steps yet" description="Steps appear here as the workflow's agents run." />
          ) : (
            <div className="flex flex-col gap-3.5 py-2">
              {nodes.map((node, i) => (
                <PipelineNode key={node.id} node={node} index={i} />
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Right rail */}
      <div className="flex flex-col gap-4">
        <Card title="Workflow details" padding="md">
          {run ? (
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
          ) : (
            <EmptyState title="No run selected" />
          )}
        </Card>

        <TokenUsageCard />

        <Card title="Artifacts" eyebrow={`${artifacts.length} GENERATED`}>
          {artifacts.length === 0 ? (
            <EmptyState
              icon={<FileIcon className="h-4 w-4" />}
              title="No artifacts yet"
              description="Agent outputs appear here once steps produce files."
            />
          ) : (
            <div className="flex flex-col gap-px">
              {artifacts.map((n, i, arr) => (
                <button
                  key={n.id}
                  onClick={() => onOpenArtifact(n)}
                  disabled={!n.artifactPath}
                  className="grid items-center gap-2.5 py-[7px] text-left bg-transparent rounded-md hover:bg-app-2 px-1.5 -mx-1.5 disabled:opacity-60 disabled:cursor-default transition-colors"
                  style={{
                    gridTemplateColumns: "16px 1fr auto",
                    borderBottom: i === arr.length - 1 ? "none" : "1px solid var(--con-line)",
                  }}
                >
                  <FileIcon className="h-3.5 w-3.5 text-ink-4" />
                  <span className="font-mono text-[11.5px] text-ink-2 hover:text-ink truncate">{n.artifact}</span>
                  <span className="inline-flex items-center gap-1 text-[10.5px] text-ink-4">
                    <AgentIcon name={n.agent} size={14} /> {n.agent}
                  </span>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

// ─── Linear pipeline node ───────────────────────────────────────────

function PipelineNode({ node, index }: { node: PipelineNodeData; index: number }) {
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
              <span className="text-[13.5px] font-medium">{node.label}</span>
              <span className="inline-flex items-center gap-1.5">
                <AgentIcon name={node.agent} size={16} />
                <span className="font-mono text-[11.5px] text-ink-3">{node.agent}</span>
              </span>
            </div>
            <div className="flex items-center gap-2.5">
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

function PhasesView({ run, runs, nodes, stepsError, selectedRun, setSelectedRun, onOpenArtifact }: ViewProps) {
  const artifacts = (nodes ?? []).filter((n) => n.artifact);

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
            <div className="eyebrow">WORKFLOW · {run?.id ?? "—"} · {run?.mode ?? "—"}</div>
            <div className="text-[16px] font-semibold mt-1 flex items-center gap-2.5">
              {run?.project ?? "—"}
              {run && <StatusBadge status={run.status} />}
            </div>
          </div>
          {run?.project && (
            <Link href={`/projects/${run.project}`}>
              <Button variant="outline" size="sm"><ExternalLink className="h-3 w-3" /> View project</Button>
            </Link>
          )}
        </div>
      </Card>

      {/* Pipeline phases */}
      <Card padding="md" bodyClassName="p-0">
        <div className="bg-surface border-t border-hx" style={{ padding: "20px 24px" }}>
          {stepsError ? (
            <EmptyState title="Couldn't load pipeline" description={stepsError} />
          ) : nodes === null ? (
            <EmptyState title="Loading pipeline…" />
          ) : nodes.length === 0 ? (
            <EmptyState
              title="No pipeline phases yet"
              description="The phase swim-lanes populate from the selected run's steps once agents start producing output."
            />
          ) : (
            <div className="flex flex-col gap-2.5">
              {nodes.map((n) => <PhaseNode key={n.id} node={n} />)}
            </div>
          )}
        </div>
      </Card>

      {/* Below: details + tokens + artifacts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Workflow details" padding="md">
          {run ? (
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
          ) : (
            <EmptyState title="No run selected" />
          )}
        </Card>

        <TokenUsageCard />

        <Card title="Artifacts" eyebrow={`${artifacts.length} GENERATED`}>
          {artifacts.length === 0 ? (
            <EmptyState
              icon={<FileIcon className="h-4 w-4" />}
              title="No artifacts yet"
              description="Agent outputs appear here once steps produce files."
            />
          ) : (
            <div className="flex flex-col gap-px">
              {artifacts.map((n, i, arr) => (
                <button
                  key={n.id}
                  onClick={() => onOpenArtifact(n)}
                  disabled={!n.artifactPath}
                  className="grid items-center gap-2.5 py-1.5 text-left bg-transparent rounded-md hover:bg-app-2 px-1.5 -mx-1.5 disabled:opacity-60 disabled:cursor-default transition-colors"
                  style={{
                    gridTemplateColumns: "16px 1fr auto",
                    borderBottom: i === arr.length - 1 ? "none" : "1px solid var(--con-line)",
                  }}
                >
                  <FileIcon className="h-3 w-3 text-ink-4" />
                  <span className="font-mono text-[11px] text-ink-2 truncate">{n.artifact}</span>
                  <span className="text-[10px] text-ink-4">{n.agent}</span>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

// ─── Phase node ─────────────────────────────────────────────────────

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
