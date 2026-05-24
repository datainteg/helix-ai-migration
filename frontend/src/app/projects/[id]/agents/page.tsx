"use client";

import { useParams } from "next/navigation";
import { Play, Save } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, StatusBadge, Avatar, Chip } from "@/components/ui";

const FLOW = [
  { id: "intake", label: "Requirement Intake", phase: "Input", color: "indigo" as const, status: "completed" },
  { id: "ba", label: "BA Agent", phase: "Analysis", color: "indigo" as const, status: "completed" },
  { id: "arch", label: "Architect Agent", phase: "Design", color: "violet" as const, status: "running" },
  { id: "approval", label: "Human Approval", phase: "Gate", color: "amber" as const, status: "queued" },
  { id: "de", label: "Data Engineer", phase: "Build", color: "cyan" as const, status: "pending" },
  { id: "qa", label: "QA Agent", phase: "Validate", color: "green" as const, status: "pending" },
  { id: "recon", label: "Recon Agent", phase: "Reconcile", color: "indigo" as const, status: "pending" },
  { id: "devops", label: "DevOps Agent", phase: "Deploy", color: "violet" as const, status: "pending" },
  { id: "final", label: "PM · Final", phase: "Sign-off", color: "default" as const, status: "pending" },
];

export default function ProjectAgentsPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <ProjectShell
      projectId={String(id)}
      projectName="Untitled project"
      projectStatus="draft"
      subtitle="Multi-agent workflow canvas with execution log and artifacts."
      actions={<>
        <Button variant="outline"><Save className="h-4 w-4" /> Save</Button>
        <Button><Play className="h-4 w-4" /> Run Workflow</Button>
      </>}
    >
      <div className="grid grid-cols-12 gap-4">
        <Card className="col-span-12 lg:col-span-8" title="Workflow Canvas">
          <div className="space-y-3">
            {FLOW.map((n) => (
              <div key={n.id} className="flex items-center gap-3">
                <FlowNode {...n} />
              </div>
            ))}
          </div>
        </Card>
        <div className="col-span-12 lg:col-span-4 space-y-4">
          <Card title="Workflow Details">
            <dl className="space-y-3 text-[13px]">
              <div>
                <dt className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">Mode</dt>
                <dd className="mt-0.5 text-ink-2">BMAD · Auto with gates</dd>
              </div>
              <div>
                <dt className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">Status</dt>
                <dd className="mt-0.5"><StatusBadge status="running" /></dd>
              </div>
              <div>
                <dt className="text-[11.5px] uppercase tracking-wider text-ink-4 font-medium">Approvers</dt>
                <dd className="mt-1 flex -space-x-2"><Avatar name="Avery Johnson" /><Avatar name="Mei Chen" /><Avatar name="Sofia Marin" /></dd>
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
            <ul className="space-y-1.5 text-[12.5px]">
              <li className="flex justify-between text-ink-2"><span>plan_v1.md</span><Chip tone="indigo">Plan</Chip></li>
              <li className="flex justify-between text-ink-2"><span>ddl.sql</span><Chip tone="violet">DDL</Chip></li>
              <li className="flex justify-between text-ink-2"><span>migrate.py</span><Chip tone="cyan">Code</Chip></li>
            </ul>
          </Card>
        </div>
      </div>
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
