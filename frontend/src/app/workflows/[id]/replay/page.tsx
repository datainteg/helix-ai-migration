"use client";

/**
 * /workflows/[id]/replay — Time-machine UI.
 *
 * Lets an operator enter per-agent prompt overrides + (optional) model
 * override, fires POST /workflows/{id}/replay, then renders the parent vs
 * replay run side-by-side by step. Each step pair shows agent name +
 * status; clicking a row reveals the parsed-output diff.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Play, GitCompare, Plus, X } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, Chip, ErrorBanner, LoadingState, StatusBadge } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import {
  getWorkflowDetail,
  type WorkflowDetail,
  type WorkflowStep,
} from "@/lib/workflows/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const AGENT_CODES = [
  "bmad-agent-architect",
  "bmad-agent-analyst",
  "bmad-agent-pm",
  "bmad-agent-ux-designer",
  "bmad-agent-dev",
  "bmad-agent-tech-writer",
];

export default function WorkflowReplayPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();

  const [parent, setParent] = useState<WorkflowDetail | null>(null);
  const [replay, setReplay] = useState<WorkflowDetail | null>(null);
  const [replayId, setReplayId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [modelOverride, setModelOverride] = useState("");

  useEffect(() => {
    // SC-010: auth via the HttpOnly cookie; gate on id only.
    if (!id) return;
    let cancelled = false;
    getWorkflowDetail(token, String(id))
      .then((d) => { if (!cancelled) setParent(d); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token, id]);

  useEffect(() => {
    if (!replayId) return;
    let stopped = false;
    const poll = () => {
      getWorkflowDetail(token, replayId).then((d) => {
        if (stopped) return;
        setReplay(d);
        const terminal = ["completed", "approved", "rejected", "failed", "expired"].includes(d.status);
        if (!terminal) setTimeout(poll, 2000);
      }).catch(() => { if (!stopped) setTimeout(poll, 4000); });
    };
    poll();
    return () => { stopped = true; };
  }, [token, replayId]);

  const triggerReplay = async () => {
    if (!id) return;
    setRunning(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/workflows/${id}/replay`, {
        method: "POST",
        credentials: "include", // SC-010: auth via HttpOnly cookie
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_prompt_overrides: overrides,
          model_override: modelOverride || null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(detail.detail || `Replay failed (${res.status})`);
      }
      const body = await res.json();
      setReplayId(body.replay_workflow_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Replay failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <AppShell
      eyebrow="WORKFLOW TIME-MACHINE"
      title="Replay workflow"
      description="Re-run a completed workflow with prompt or model overrides; compare side-by-side."
      crumbs={[{ label: "Agents", href: "/agents" }, { label: "Replay" }]}
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Overrides">
          <div className="space-y-3">
            {AGENT_CODES.map((code) => (
              <label key={code} className="flex flex-col gap-1">
                <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">{code}</span>
                <textarea
                  rows={2}
                  value={overrides[code] || ""}
                  onChange={(e) => setOverrides({ ...overrides, [code]: e.target.value })}
                  placeholder={`Override prompt for ${code}…`}
                  className="p-2 text-[12px] rounded-[6px] border border-hx focus-ring resize-none font-mono"
                />
              </label>
            ))}
            <label className="flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">MODEL OVERRIDE (OPTIONAL)</span>
              <input
                value={modelOverride}
                onChange={(e) => setModelOverride(e.target.value)}
                placeholder="claude-opus-4-7 | gpt-5 | …"
                className="h-8 px-2 text-[13px] rounded-[6px] border border-hx focus-ring font-mono"
              />
            </label>
            <Button onClick={() => void triggerReplay()} disabled={running || !parent}>
              <Play className="h-3.5 w-3.5" /> {running ? "Submitting…" : "Replay"}
            </Button>
          </div>
        </Card>

        <Card title={<span className="flex items-center gap-2"><GitCompare className="h-4 w-4" /> Parent vs replay</span>} className="col-span-1 lg:col-span-2">
          {loading ? (
            <LoadingState label="Loading parent workflow…" />
          ) : !parent ? (
            <p className="text-[12.5px] text-ink-3">Parent workflow not loaded.</p>
          ) : (
            <DiffView parent={parent} replay={replay} />
          )}
        </Card>
      </div>
    </AppShell>
  );
}

function DiffView({ parent, replay }: { parent: WorkflowDetail; replay: WorkflowDetail | null }) {
  const pSteps = stepsByName(parent.steps);
  const rSteps = stepsByName(replay?.steps ?? []);
  const agents = Array.from(new Set([...Object.keys(pSteps), ...Object.keys(rSteps)])).sort();
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="text-[13px]">
      <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-center mb-2 px-2 text-[10.5px] uppercase tracking-wider text-ink-4 font-mono">
        <span>PARENT · {parent.workflow_id.slice(0, 12)}</span>
        <span className="text-center"> </span>
        <span>{replay ? `REPLAY · ${replay.workflow_id.slice(0, 12)}` : "REPLAY (not started)"}</span>
      </div>
      {agents.map((agent) => {
        const p = pSteps[agent];
        const r = rSteps[agent];
        return (
          <div key={agent} className="border-t border-hx">
            <button
              type="button"
              onClick={() => setExpanded(expanded === agent ? null : agent)}
              className="w-full grid grid-cols-[1fr_auto_1fr] gap-2 items-center p-2 text-left hover:bg-app-2"
            >
              <span className="flex items-center gap-2">
                {p ? <StatusBadge status={p.status} /> : <Chip tone="default">—</Chip>}
                <span className="text-ink-3 text-[12px]">{p?.parsed_output ? "✓ parsed" : "—"}</span>
              </span>
              <span className="font-medium font-mono text-[12px]">{agent}</span>
              <span className="flex items-center gap-2 justify-end">
                {r ? <StatusBadge status={r.status} /> : <Chip tone="default">pending</Chip>}
                <span className="text-ink-3 text-[12px]">{r?.parsed_output ? "✓ parsed" : "—"}</span>
              </span>
            </button>
            {expanded === agent && (
              <div className="grid grid-cols-2 gap-2 p-3 bg-app-2 text-[11px] font-mono">
                <pre className="overflow-x-auto whitespace-pre-wrap">{p ? JSON.stringify(p.parsed_output, null, 2) : "—"}</pre>
                <pre className="overflow-x-auto whitespace-pre-wrap">{r ? JSON.stringify(r.parsed_output, null, 2) : "—"}</pre>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function stepsByName(steps: WorkflowStep[]): Record<string, WorkflowStep> {
  return steps.reduce((acc, s) => {
    acc[s.agent_name] = s;
    return acc;
  }, {} as Record<string, WorkflowStep>);
}
