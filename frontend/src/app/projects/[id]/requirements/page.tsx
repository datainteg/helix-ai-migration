"use client";

/**
 * /projects/[id]/requirements — manage the migration requirements the agents
 * plan from.
 *
 * - Two authoring modes: a type-aware STRUCTURED form, or PLAIN ENGLISH prose
 *   (stored verbatim as the agent prompt — best for accuracy when you know
 *   exactly what you want).
 * - EDIT preserves history: editing creates a NEW version in the same chain
 *   (root_id), the prior version is marked superseded. Versions are grouped so
 *   the latest is shown with its history available.
 * Real data via GET/POST/PUT /projects/{id}/requirements.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { FileText, Plus, Play, Pencil, ChevronDown, ChevronRight, History } from "lucide-react";

import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, StatusBadge, EmptyState, ErrorBanner, LoadingState } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import {
  listProjectRequirements, createProjectRequirement, editProjectRequirement,
  compileRequirement, fieldsForType, EMPTY_SPEC,
  type ProjectRequirement, type RequirementSpec,
} from "@/lib/workflows/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/** Light renderer for the compiled markdown source_text (# / ## headings). */
function RequirementBody({ text }: { text: string }) {
  return (
    <div className="space-y-1.5 text-[12.5px] leading-relaxed">
      {text.split("\n").map((line, i) => {
        if (line.startsWith("## ")) return <p key={i} className="font-semibold text-ink mt-2">{line.slice(3)}</p>;
        if (line.startsWith("# ")) return <p key={i} className="font-semibold text-ink text-[13.5px]">{line.slice(2)}</p>;
        if (!line.trim()) return <div key={i} className="h-1" />;
        return <p key={i} className="text-ink-2">{line}</p>;
      })}
    </div>
  );
}

interface Group { root: string; head: ProjectRequirement; history: ProjectRequirement[]; }

function groupByChain(reqs: ProjectRequirement[]): Group[] {
  const byRoot = new Map<string, ProjectRequirement[]>();
  for (const r of reqs) {
    const root = r.root_id || r.id;
    (byRoot.get(root) ?? byRoot.set(root, []).get(root)!).push(r);
  }
  const vnum = (r: ProjectRequirement) => (/^\d+$/.test(r.version) ? parseInt(r.version, 10) : 1);
  const groups: Group[] = [];
  for (const [root, rows] of byRoot) {
    rows.sort((a, b) => vnum(b) - vnum(a)); // newest first
    groups.push({ root, head: rows[0], history: rows.slice(1) });
  }
  // newest chains first by head creation
  groups.sort((a, b) => (b.head.created_at || "").localeCompare(a.head.created_at || ""));
  return groups;
}

export default function ProjectRequirementsPage() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const canWrite = can("project:write");

  const [projectName, setProjectName] = useState("Project");
  const [migType, setMigType] = useState("db_to_db");
  const [onHold, setOnHold] = useState(false);
  const [reqs, setReqs] = useState<ProjectRequirement[] | null>(null);
  const [error, setError] = useState("");
  // builder: null (closed) | {} (new) | {editId, initialText} (edit)
  const [builder, setBuilder] = useState<null | { editId?: string; initialText?: string }>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [histOpen, setHistOpen] = useState<Record<string, boolean>>({});

  useRegisterCrumbLabel(String(id), projectName !== "Project" ? projectName : undefined);

  useEffect(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/v1/projects/${id}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => { setProjectName(p?.name || "Project"); if (p?.migration_type) setMigType(p.migration_type); setOnHold(!!p?.on_hold); })
      .catch(() => setProjectName("Project"));
  }, [id]);

  const load = useCallback(() => {
    if (!id) return;
    setReqs(null); setError("");
    listProjectRequirements(String(id))
      .then(setReqs)
      .catch((e) => { setReqs([]); setError(e instanceof Error ? e.message : "Failed to load requirements"); });
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const groups = reqs ? groupByChain(reqs) : [];

  return (
    <ProjectShell
      projectId={String(id)}
      projectName={projectName}
      onHold={onHold}
      subtitle="The structured requirements the agents plan from — versioned, editable, and reusable across runs."
      actions={canWrite && !builder ? <Button variant="outline" onClick={() => setBuilder({})}><Plus className="h-4 w-4" /> New requirement</Button> : undefined}
    >
      {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError("")} /></div>}

      {builder && (
        <div className="mb-5">
          <RequirementBuilder
            projectId={String(id)}
            migType={migType}
            editId={builder.editId}
            initialText={builder.initialText}
            onCancel={() => setBuilder(null)}
            onDone={() => { setBuilder(null); load(); }}
          />
        </div>
      )}

      {reqs === null ? (
        <LoadingState label="Loading requirements…" />
      ) : groups.length === 0 ? (
        <Card>
          <EmptyState
            icon={<FileText className="h-4 w-4" />}
            title="No requirements yet"
            description={canWrite ? "Build a structured requirement, or write one in plain English, so the agents know exactly what to migrate." : "No requirements have been defined for this project yet."}
            action={canWrite && !builder ? <Button onClick={() => setBuilder({})}><Plus className="h-4 w-4" /> New requirement</Button> : undefined}
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {groups.map(({ root, head, history }) => {
            const open = expanded[root];
            const firstLine = head.source_text.split("\n").find((l) => l.startsWith("# "))?.slice(2) || head.source_text.slice(0, 80);
            return (
              <Card key={root} padding="sm">
                <div className="flex items-center gap-3">
                  <button type="button" onClick={() => setExpanded((m) => ({ ...m, [root]: !m[root] }))} className="flex items-center gap-3 flex-1 min-w-0 text-left">
                    {open ? <ChevronDown className="h-4 w-4 text-ink-4 flex-shrink-0" /> : <ChevronRight className="h-4 w-4 text-ink-4 flex-shrink-0" />}
                    <FileText className="h-4 w-4 text-ink-3 flex-shrink-0" />
                    <span className="flex-1 min-w-0 text-[13px] font-medium text-ink truncate">{firstLine}</span>
                  </button>
                  <Chip tone="zinc" mono>v{head.version}</Chip>
                  <StatusBadge status={head.status} />
                  {canWrite && (
                    <Button size="sm" variant="ghost" onClick={() => setBuilder({ editId: head.id, initialText: head.source_text })} aria-label="Edit requirement">
                      <Pencil className="h-3.5 w-3.5" /> Edit
                    </Button>
                  )}
                </div>

                {open && (
                  <div className="mt-3 pt-3 border-t border-hx flex flex-col gap-3">
                    <RequirementBody text={head.source_text} />

                    {history.length > 0 && (
                      <div className="rounded-[8px] border border-hx bg-app-2/50">
                        <button type="button" onClick={() => setHistOpen((m) => ({ ...m, [root]: !m[root] }))}
                          className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-ink-3">
                          <History className="h-3.5 w-3.5" /> Version history ({history.length})
                          {histOpen[root] ? <ChevronDown className="h-3.5 w-3.5 ml-auto" /> : <ChevronRight className="h-3.5 w-3.5 ml-auto" />}
                        </button>
                        {histOpen[root] && (
                          <ul className="px-3 pb-3 space-y-2">
                            {history.map((h) => (
                              <li key={h.id} className="border-t border-hx pt-2">
                                <div className="flex items-center gap-2 text-[12px] text-ink-3">
                                  <Chip tone="zinc" mono>v{h.version}</Chip>
                                  <StatusBadge status={h.status} />
                                  <span className="ml-auto text-ink-4 text-[11px]">{h.created_at?.slice(0, 19).replace("T", " ")}</span>
                                </div>
                                <p className="mt-1 text-[11.5px] text-ink-4 line-clamp-2 whitespace-pre-wrap">{h.source_text.slice(0, 240)}</p>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}

                    {canWrite && (
                      <div>
                        <Link href={`/projects/${id}/agents?run=new`}>
                          <Button size="sm" variant="outline" disabled={onHold} title={onHold ? "Project is on hold" : undefined}>
                            <Play className="h-3.5 w-3.5" /> Use in a workflow run
                          </Button>
                        </Link>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </ProjectShell>
  );
}

function RequirementBuilder({ projectId, migType, editId, initialText, onCancel, onDone }: {
  projectId: string; migType: string; editId?: string; initialText?: string;
  onCancel: () => void; onDone: () => void;
}) {
  // Editing always opens in plain-text mode pre-filled with the current text
  // (the structured fields aren't recoverable from compiled markdown).
  const [mode, setMode] = useState<"structured" | "plain">(editId ? "plain" : "structured");
  const [spec, setSpec] = useState<RequirementSpec>(EMPTY_SPEC);
  const [plain, setPlain] = useState(initialText || "");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const fields = fieldsForType(migType);

  const save = async () => {
    const text = mode === "plain" ? plain.trim() : compileRequirement(migType, spec);
    if (!text || (mode === "structured" && !spec.goal.trim())) {
      setErr(mode === "plain" ? "Write the requirement before saving." : "Describe at least the migration goal.");
      return;
    }
    setSaving(true); setErr("");
    try {
      if (editId) await editProjectRequirement(projectId, editId, text);
      else await createProjectRequirement(projectId, text);
      onDone();
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Failed to save"); }
    finally { setSaving(false); }
  };

  const ta = "px-2.5 py-2 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring resize-y w-full";
  const segBtn = (m: "structured" | "plain", label: string) => (
    <button type="button" onClick={() => setMode(m)}
      className={`px-3 h-8 rounded-md text-[12.5px] border ${mode === m ? "border-[var(--con-brand)] bg-[var(--con-brand-soft)] text-[var(--con-brand)]" : "border-hx-2 bg-surface text-ink-3"}`}>
      {label}
    </button>
  );

  return (
    <Card
      title={editId ? "Edit requirement (saves a new version)" : "New requirement"}
      description={editId ? "Editing creates a new version; the previous one is kept in history." : "Build it structurally, or write the requirement in plain English."}
    >
      <div className="space-y-4">
        {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}

        <div className="flex gap-2">
          {segBtn("structured", "Structured")}
          {segBtn("plain", "Plain English")}
        </div>

        {mode === "plain" ? (
          <label className="flex flex-col gap-1.5">
            <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">Requirement (used verbatim as the agent prompt)</span>
            <textarea rows={10} value={plain} onChange={(e) => setPlain(e.target.value)}
              placeholder={"Briefly but precisely describe the migration in your own words. e.g.\nMigrate the sales schema (customers, orders, order_items, products) from PostgreSQL to Snowflake. Preserve keys and indexes. Map jsonb -> VARIANT and timestamptz -> TIMESTAMP_TZ. Migrate all rows with row-count + checksum reconciliation per table. Rename legacy_id -> id."}
              className={`${ta} font-mono leading-relaxed`} />
            <span className="text-[11.5px] text-ink-4">Plain-English requirements are passed straight to the agents — the more specific, the higher the accuracy.</span>
          </label>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {fields.map((f) => (
              <label key={f.key} className={`flex flex-col gap-1.5 ${f.full ? "sm:col-span-2" : ""}`}>
                <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">{f.label}</span>
                <textarea rows={2} value={spec[f.key]} onChange={(e) => setSpec((s) => ({ ...s, [f.key]: e.target.value }))} placeholder={f.placeholder} className={ta} />
              </label>
            ))}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button onClick={save} loading={saving}>{editId ? "Save new version" : "Save requirement"}</Button>
        </div>
      </div>
    </Card>
  );
}
