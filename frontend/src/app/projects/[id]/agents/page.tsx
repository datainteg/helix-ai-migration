"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Play, Save } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, StatusBadge, Avatar, Chip, EmptyState, LoadingState } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import {
  listProjectWorkflowRuns,
  getWorkflowDetail,
  subscribeToWorkflow,
  type WorkflowRun,
  type WorkflowDetail,
  type WorkflowStep,
} from "@/lib/workflows/api";

const AGENT_PHASE: Record<string, { label: string; color: "indigo" | "violet" | "cyan" | "amber" | "green" | "default" }> = {
  project_context: { label: "Setup", color: "default" },
  analyst:          { label: "Analysis", color: "indigo" },
  pm:               { label: "Planning", color: "indigo" },
  ux_designer:      { label: "Planning", color: "indigo" },
  architect:        { label: "Design", color: "violet" },
  architect_stories:{ label: "Design", color: "violet" },
  architect_readiness:{ label: "Design", color: "violet" },
  approval_gate:    { label: "Gate", color: "amber" },
  dev_story:        { label: "Build", color: "cyan" },
  dev:              { label: "Build", color: "cyan" },
  qa:               { label: "Validate", color: "green" },
  code_review:      { label: "Validate", color: "green" },
  tech_writer:      { label: "Docs", color: "default" },
};

export default function ProjectAgentsPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [runs, setRuns] = useState<WorkflowRun[] | null>(null);
  const [active, setActive] = useState<WorkflowDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // SC-010: auth via the HttpOnly cookie; gate on id only.
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    listProjectWorkflowRuns(token, String(id), 20)
      .then(async (rows) => {
        if (cancelled) return;
        setRuns(rows);
        if (rows.length > 0) {
          try {
            const detail = await getWorkflowDetail(token, rows[0].workflow_id);
            if (!cancelled) setActive(detail);
          } catch {
            if (!cancelled) setActive(null);
          }
        }
      })
      .catch(() => { if (!cancelled) setRuns([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token, id]);

  // Live SSE — append-on-step. Only subscribes when the active run is not yet
  // terminal so we don't reopen connections to completed workflows.
  useEffect(() => {
    if (!active) return;
    if (["completed", "approved", "rejected", "failed", "expired"].includes(active.status)) return;
    let es: EventSource | null = null;
    let cancelled = false;
    subscribeToWorkflow(
      token,
      active.workflow_id,
      (step: WorkflowStep) => {
        setActive((prev) => {
          if (!prev || prev.workflow_id !== active.workflow_id) return prev;
          const without = prev.steps.filter((s) => s.step_order !== step.step_order);
          return { ...prev, steps: [...without, step].sort((a, b) => a.step_order - b.step_order) };
        });
      },
      (terminal) => {
        setActive((prev) => prev ? { ...prev, status: terminal } : prev);
      },
    ).then((handle) => {
      if (cancelled) { handle?.close(); return; }
      es = handle;
    });
    return () => {
      cancelled = true;
      es?.close();
    };
  }, [token, active?.workflow_id, active?.status]);

  const flow = active && active.steps.length > 0
    ? active.steps.map((s, idx) => {
        const meta = AGENT_PHASE[s.agent_name] ?? { label: "Step", color: "default" as const };
        return {
          id: `step-${idx}`,
          label: s.agent_name.replace(/_/g, " "),
          phase: meta.label,
          color: meta.color,
          status: s.status,
        };
      })
    : [];
  const hasRuns = (runs?.length ?? 0) > 0;

  return (
    <ProjectShell
      projectId={String(id)}
      projectName="Untitled project"
      projectStatus={active ? (active.status as any) : "draft"}
      subtitle="Multi-agent workflow canvas with execution log and artifacts."
      actions={<>
        <Button variant="outline"><Save className="h-4 w-4" /> Save</Button>
        <Button><Play className="h-4 w-4" /> Run Workflow</Button>
      </>}
    >
      {loading ? (
        <LoadingState label="Loading workflow runs…" />
      ) : (
        <>
          <div className="grid grid-cols-12 gap-4">
            <Card className="col-span-12 lg:col-span-8" title="Workflow Canvas">
              {flow.length > 0 ? (
                <div className="space-y-3">
                  {flow.map((n) => (
                    <div key={n.id} className="flex items-center gap-3">
                      <FlowNode {...n} />
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No agent runs yet"
                  description={hasRuns
                    ? "This workflow has no recorded steps yet."
                    : "Run a workflow to see per-agent execution state here."}
                />
              )}
            </Card>
            <div className="col-span-12 lg:col-span-4 space-y-4">
              <Card title="Workflow Details">
                <dl className="space-y-3 text-[13px]">
                  <div>
                    <dt className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">Mode</dt>
                    <dd className="mt-0.5 text-ink-2">{active?.mode ?? "BMAD · Auto with gates"}</dd>
                  </div>
                  <div>
                    <dt className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">Status</dt>
                    <dd className="mt-0.5"><StatusBadge status={active?.status ?? "draft"} /></dd>
                  </div>
                  <div>
                    <dt className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">Workflow ID</dt>
                    <dd className="mt-0.5 font-mono text-[11.5px] text-ink-3">{active?.workflow_id ?? "—"}</dd>
                  </div>
                </dl>
              </Card>
              <Card title="Human Approval">
                <p className="text-[12.5px] text-ink-3">Review the Architect Agent output before proceeding to execution agents.</p>
                <div className="mt-3 flex flex-col gap-2">
                  <Button className="w-full justify-center">Approve</Button>
                  <Button variant="outline" className="w-full justify-center">Request changes</Button>
                  <Button variant="danger" className="w-full justify-center">Reject</Button>
                </div>
              </Card>
              <Card title="Output Artifacts">
                {active && active.steps.some((s) => s.artifact_path) ? (
                  <ul className="space-y-1.5 text-[12.5px]">
                    {active.steps.filter((s) => s.artifact_path).map((s, i) => (
                      <li key={`art-${i}`} className="flex justify-between text-ink-2 gap-2 min-w-0">
                        <span className="truncate font-mono text-[11.5px]">{s.artifact_path?.split(/[\\/]/).pop()}</span>
                        <Chip tone="indigo">{s.agent_name.replace(/_/g, " ")}</Chip>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[12.5px] text-ink-3">No artifacts yet.</p>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </ProjectShell>
  );
}

function FlowNode({ label, phase, color, status }: { label: string; phase: string; color: "indigo" | "violet" | "cyan" | "amber" | "green" | "default"; status: string }) {
  const palette: Record<typeof color, string> = {
    indigo: "bg-helix-50 text-helix-800 border-helix-200",
    violet: "bg-violet-50 text-violet-800 border-violet-200",
    cyan: "bg-cyan-50 text-cyan-800 border-cyan-200",
    amber: "bg-amber-50 text-amber-800 border-amber-200",
    green: "bg-emerald-50 text-emerald-800 border-emerald-200",
    default: "bg-zinc-50 text-ink-2 border-hx",
  };
  return (
    <div className={`rounded-xl border px-4 py-3 shadow-xs w-full flex items-center justify-between ${palette[color]}`}>
      <div>
        <div className="text-[11px] uppercase tracking-wider opacity-70 font-medium">{phase}</div>
        <div className="text-[14px] font-semibold">{label}</div>
      </div>
      <StatusBadge status={status} />
    </div>
  );
}
