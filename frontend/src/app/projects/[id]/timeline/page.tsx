"use client";

/**
 * /projects/[id]/timeline — a REAL activity timeline for the project.
 *
 * Merges two live sources, newest-first, into a single vertical timeline:
 *   1) workflow runs  — listProjectWorkflowRuns (status / mode / created_at)
 *   2) comments + hold/live events — fetchProjectComments (author, kind, body)
 *
 * No fabricated data: when both sources are empty we render an honest
 * EmptyState. Style mirrors source-target / compliance siblings.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Workflow as WorkflowIcon,
  MessageSquare,
  PauseCircle,
  PlayCircle,
  History as HistoryIcon,
} from "lucide-react";

import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, StatusBadge, EmptyState, ErrorBanner, LoadingState } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import { listProjectWorkflowRuns, type WorkflowRun } from "@/lib/workflows/api";
import { fetchProjectComments, type ProjectComment } from "@/lib/projects/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

type EventKind = "workflow" | "comment" | "hold" | "live";

interface TimelineEvent {
  id: string;
  kind: EventKind;
  at: number; // ms epoch, for sorting
  atRaw: string | null;
  title: string;
  detail?: string;
  status?: string; // for workflow runs → StatusBadge
}

/** Nicely format an ISO timestamp into "May 31, 2026 · 14:03". */
function formatTs(raw: string | null): string {
  if (!raw) return "Unknown time";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return `${d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })} · ${d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`;
}

function toMs(raw: string | null): number {
  if (!raw) return 0;
  const t = new Date(raw).getTime();
  return Number.isNaN(t) ? 0 : t;
}

const ICONS: Record<EventKind, React.ReactNode> = {
  workflow: <WorkflowIcon className="h-3.5 w-3.5" />,
  comment: <MessageSquare className="h-3.5 w-3.5" />,
  hold: <PauseCircle className="h-3.5 w-3.5" />,
  live: <PlayCircle className="h-3.5 w-3.5" />,
};

// Dot ring tone per event kind — uses the same design tokens as siblings.
const DOT_CLS: Record<EventKind, string> = {
  workflow: "bg-app-2 text-[var(--con-brand)] border-hx",
  comment: "bg-app-2 text-ink-3 border-hx",
  hold: "bg-app-2 text-[var(--con-warn)] border-hx",
  live: "bg-app-2 text-[var(--con-ok)] border-hx",
};

function runEvent(r: WorkflowRun): TimelineEvent {
  const mode = r.mode ? r.mode.replace(/_/g, " ") : "workflow";
  return {
    id: `wf-${r.workflow_id}`,
    kind: "workflow",
    at: toMs(r.created_at),
    atRaw: r.created_at,
    title: `Workflow run started (${mode})`,
    detail: `Workflow ${r.workflow_id.slice(0, 8)}${r.run_id ? ` · run ${r.run_id.slice(0, 8)}` : ""}`,
    status: r.status,
  };
}

function commentEvent(c: ProjectComment): TimelineEvent {
  const author = c.author_name || "Someone";
  const kind: EventKind = c.kind === "hold" ? "hold" : c.kind === "live" ? "live" : "comment";
  const title =
    kind === "hold"
      ? `${author} put the project on hold`
      : kind === "live"
        ? `${author} set the project live`
        : `${author} commented`;
  return {
    id: `cm-${c.id}`,
    kind,
    at: toMs(c.created_at),
    atRaw: c.created_at,
    title,
    detail: c.body || undefined,
  };
}

export default function ProjectTimelinePage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [projectName, setProjectName] = useState("Project");
  const [projectStatus, setProjectStatus] = useState("draft");
  const [onHold, setOnHold] = useState(false);

  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [error, setError] = useState("");

  useRegisterCrumbLabel(String(id), projectName !== "Project" ? projectName : undefined);

  // Project header + breadcrumb.
  useEffect(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/v1/projects/${id}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => {
        setProjectName(p?.name || "Project");
        if (p?.status) setProjectStatus(p.status);
        setOnHold(!!p?.on_hold);
      })
      .catch(() => setProjectName("Project"));
  }, [id]);

  // Merge the two real sources, newest-first.
  useEffect(() => {
    if (!id) return;
    let alive = true;
    setError("");
    Promise.allSettled([
      listProjectWorkflowRuns(token, String(id)),
      fetchProjectComments(String(id)),
    ])
      .then(([runsRes, commentsRes]) => {
        if (!alive) return;
        const merged: TimelineEvent[] = [];
        if (runsRes.status === "fulfilled") merged.push(...runsRes.value.map(runEvent));
        if (commentsRes.status === "fulfilled") merged.push(...commentsRes.value.map(commentEvent));

        // Surface an error only if BOTH sources failed (so a partial timeline still renders).
        if (runsRes.status === "rejected" && commentsRes.status === "rejected") {
          const e = runsRes.reason;
          setError(e instanceof Error ? e.message : "Failed to load activity");
        }

        merged.sort((a, b) => b.at - a.at);
        setEvents(merged);
      });
    return () => {
      alive = false;
    };
  }, [id, token]);

  return (
    <ProjectShell
      projectId={String(id)}
      projectName={projectName}
      projectStatus={projectStatus as any}
      onHold={onHold}
      subtitle="Everything that happened on this project — workflow runs, comments, and hold/live changes, newest first."
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}
      <Card
        title={
          <span className="flex items-center gap-2">
            <HistoryIcon className="h-4 w-4 text-[var(--con-brand)]" /> Activity timeline
          </span>
        }
      >
        {events === null ? (
          <LoadingState label="Loading activity…" />
        ) : events.length === 0 ? (
          <EmptyState
            icon={<HistoryIcon className="h-4 w-4" />}
            title="No activity yet"
            description="Once a workflow runs or someone comments, the events will appear here in order."
          />
        ) : (
          <ol className="relative ml-1.5">
            {/* The vertical line behind every dot. */}
            <span className="absolute left-[11px] top-1.5 bottom-1.5 w-px bg-hx" aria-hidden />
            {events.map((ev) => (
              <li key={ev.id} className="relative flex gap-3 pl-0 pb-5 last:pb-0">
                <span
                  className={`relative z-[1] grid place-items-center h-6 w-6 shrink-0 rounded-full border ${DOT_CLS[ev.kind]}`}
                >
                  {ICONS[ev.kind]}
                </span>
                <div className="min-w-0 flex-1 -mt-0.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[13px] font-medium text-ink">{ev.title}</span>
                    {ev.status && <StatusBadge status={ev.status} />}
                  </div>
                  <div className="text-[11px] text-ink-4 font-mono mt-0.5">{formatTs(ev.atRaw)}</div>
                  {ev.detail && (
                    <div className="text-[12.5px] text-ink-3 mt-1 whitespace-pre-wrap break-words leading-relaxed">
                      {ev.detail}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </ProjectShell>
  );
}
