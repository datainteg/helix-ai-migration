"use client";

/**
 * /projects/[id]/artifacts — per-project artifact browser, markdown-first.
 *
 * Left: list of the project's artifacts (filename + file_type). Main pane shows
 * the selected artifact's REAL stored content for the chosen version — rendered
 * as beautiful markdown when it's a .md/markdown file, otherwise as a themed
 * monospace code block. A version selector (newest first) re-fetches that
 * version's bytes. With project:write you can edit the content and save it as a
 * NEW version (history preserved). No fabricated data — honest empty states.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { FileText, FileCode, History, Pencil, Save, X } from "lucide-react";

import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, EmptyState, LoadingState, ErrorBanner, MarkdownView } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import {
  listProjectArtifacts, listArtifactVersions, fetchArtifactContent, saveArtifactContent,
  type Artifact, type ArtifactVersion, type ArtifactContent,
} from "@/lib/artifacts/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/** Decide if an artifact should render as markdown. */
function isMarkdown(filename?: string | null, fileType?: string | null): boolean {
  const ft = (fileType || "").toLowerCase();
  if (ft === "md" || ft === "markdown") return true;
  return /\.md$/i.test(filename || "");
}

export default function ProjectArtifactsPage() {
  const projectKey = String(useParams<{ id: string }>().id);
  const { id } = useProjectKey(projectKey);
  const { token, can } = useAuth();
  const canWrite = can("project:write");

  const [projectName, setProjectName] = useState("Project");
  const [projectStatus, setProjectStatus] = useState("draft");
  const [onHold, setOnHold] = useState(false);

  const [artifacts, setArtifacts] = useState<Artifact[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [versions, setVersions] = useState<ArtifactVersion[]>([]);
  const [activeVerIdx, setActiveVerIdx] = useState(0); // 0 = latest
  const [contentCache, setContentCache] = useState<Record<string, ArtifactContent>>({});
  const [loading, setLoading] = useState(true);

  // edit state
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [summary, setSummary] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [editErr, setEditErr] = useState("");
  const [versionsReloadKey, setVersionsReloadKey] = useState(0);

  useRegisterCrumbLabel(projectKey, projectName !== "Project" ? projectName : undefined);

  // Real project name + status for the ProjectShell header + breadcrumb.
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

  // Artifacts for the explorer.
  useEffect(() => {
    if (!token || !id) return;
    let cancelled = false;
    setLoading(true);
    listProjectArtifacts(token, String(id), 100)
      .then((rows) => {
        if (cancelled) return;
        setArtifacts(rows);
        if (rows.length > 0) setSelectedId(rows[0].id);
      })
      .catch(() => { if (!cancelled) setArtifacts([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token, id]);

  // Versions for the selected artifact (newest first). Reset to latest.
  useEffect(() => {
    if (!token || !selectedId) { setVersions([]); return; }
    let cancelled = false;
    setActiveVerIdx(0);
    listArtifactVersions(token, selectedId)
      .then((rows) => { if (!cancelled) setVersions(rows); })
      .catch(() => { if (!cancelled) setVersions([]); });
    return () => { cancelled = true; };
  }, [token, selectedId, versionsReloadKey]);

  // Leaving an artifact / version cancels any in-progress edit.
  useEffect(() => { setEditing(false); setEditErr(""); }, [selectedId, activeVerIdx]);

  const keyFor = (artifactId: string, vnum: string) => `${artifactId}@${vnum}`;

  // Fetch (and cache) content for one version of the selected artifact.
  const ensureContent = useCallback(
    (vnum: string | undefined) => {
      if (!token || !selectedId || !vnum) return;
      const k = keyFor(selectedId, vnum);
      setContentCache((prev) => {
        if (prev[k]) return prev;
        fetchArtifactContent(token, selectedId, vnum)
          .then((c) => setContentCache((m) => ({ ...m, [k]: c })))
          .catch(() => setContentCache((m) => ({ ...m, [k]: { artifact_id: selectedId, version_number: vnum, content: null, truncated: false, size_bytes: 0, note: "Content unavailable." } })));
        return prev;
      });
    },
    [token, selectedId],
  );

  // Whenever the active version changes, load its content.
  useEffect(() => {
    ensureContent(versions[activeVerIdx]?.version_number);
  }, [versions, activeVerIdx, ensureContent]);

  const hasReal = (artifacts?.length ?? 0) > 0;
  const selected = hasReal ? artifacts!.find((a) => a.id === selectedId) ?? null : null;

  const activeVer = versions[activeVerIdx];
  const curEntry = selectedId && activeVer ? contentCache[keyFor(selectedId, activeVer.version_number)] : undefined;
  const selectedContent = curEntry?.content ?? null;

  const renderAsMd = isMarkdown(selected?.filename, curEntry?.file_type ?? selected?.file_type);

  const startEdit = () => { setDraft(selectedContent ?? ""); setSummary(""); setEditErr(""); setEditing(true); };
  const saveEdit = async () => {
    if (!token || !selectedId) return;
    setSavingEdit(true); setEditErr("");
    try {
      await saveArtifactContent(token, selectedId, draft, summary || undefined);
      // Drop cached content for this artifact so the new version refetches.
      setContentCache((m) => {
        const next = { ...m };
        for (const k of Object.keys(next)) if (k.startsWith(`${selectedId}@`)) delete next[k];
        return next;
      });
      setEditing(false);
      setActiveVerIdx(0);
      setVersionsReloadKey((k) => k + 1); // re-list versions → new head appears
    } catch (e: unknown) {
      setEditErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSavingEdit(false);
    }
  };

  return (
    <ProjectShell
      projectId={projectKey}
      projectName={projectName}
      projectStatus={projectStatus as any}
      onHold={onHold}
      subtitle="Browse this project's generated artifacts — read the markdown, inspect versions, edit."
    >
      {loading ? <LoadingState label="Loading artifacts…" /> : null}
      <div className="grid grid-cols-12 gap-4">
        {/* Artifact list */}
        <Card className="col-span-12 lg:col-span-3" title="Artifacts" padding="sm">
          {hasReal ? (
            <ul className="space-y-1 text-[12.5px]">
              {artifacts!.map((f) => {
                const md = isMarkdown(f.filename, f.file_type);
                return (
                  <li
                    key={f.id}
                    onClick={() => setSelectedId(f.id)}
                    className={`px-2 py-1.5 rounded-md flex items-center gap-2 cursor-pointer ${f.id === selectedId ? "bg-helix-50 text-helix-700" : "text-ink-3 hover:bg-app-2"}`}
                  >
                    {md ? <FileText className="h-3.5 w-3.5 shrink-0" /> : <FileCode className="h-3.5 w-3.5 shrink-0" />}
                    <span className="truncate flex-1">{f.filename}</span>
                    {f.file_type ? <span className="text-[10.5px] text-ink-4 font-mono shrink-0">{f.file_type}</span> : null}
                  </li>
                );
              })}
            </ul>
          ) : !loading ? (
            <EmptyState
              icon={<FileText className="h-4 w-4" />}
              title="No artifacts yet"
              description="Artifacts appear here once the agents generate them for this project."
            />
          ) : null}
        </Card>

        {/* Main content pane */}
        <div className="col-span-12 lg:col-span-9 space-y-4">
          <Card>
            {selected ? (
              <>
                <div className="flex items-center gap-2 text-[12.5px] border-b border-hx -mx-5 px-5 pb-3 mb-4">
                  {renderAsMd ? <FileText className="h-3.5 w-3.5 text-ink-3" /> : <FileCode className="h-3.5 w-3.5 text-ink-3" />}
                  <span className="font-medium text-ink truncate">{selected.filename}</span>
                  {activeVer ? <Chip tone="zinc">v{activeVer.version_number}</Chip> : null}
                  {selected.file_type ? <Chip tone="zinc">{selected.file_type}</Chip> : null}

                  {/* Version selector */}
                  {versions.length > 0 && !editing ? (
                    <label className="ml-auto flex items-center gap-1.5 text-[11.5px] text-ink-4">
                      <History className="h-3 w-3" />
                      <select
                        value={activeVerIdx}
                        onChange={(e) => setActiveVerIdx(Number(e.target.value))}
                        className="h-7 px-2 text-[12px] rounded-[8px] border border-hx bg-surface focus-ring text-ink-2"
                      >
                        {versions.map((v, i) => (
                          <option key={v.id} value={i}>
                            v{v.version_number}{i === 0 ? " (latest)" : ""}{v.approval_status === "approved" ? " · approved" : ""}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}

                  {canWrite && selectedContent != null && !editing ? (
                    <button
                      type="button"
                      onClick={startEdit}
                      className={`text-[12px] px-2 py-0.5 rounded-md inline-flex items-center gap-1 text-ink-3 hover:bg-app-2 ${versions.length > 0 ? "" : "ml-auto"}`}
                    >
                      <Pencil className="h-3 w-3" /> Edit
                    </button>
                  ) : null}
                </div>

                {editing ? (
                  <div className="flex flex-col gap-3">
                    {editErr ? <ErrorBanner message={editErr} onDismiss={() => setEditErr("")} /> : null}
                    <p className="text-[12px] text-ink-3">
                      Editing creates a <strong>new version</strong> — the current one is kept in history.
                    </p>
                    <textarea
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      spellCheck={false}
                      rows={22}
                      className="w-full px-3 py-2 text-[12.5px] font-mono leading-relaxed rounded-lg border border-hx bg-app-2 focus-ring resize-y"
                    />
                    <input
                      value={summary}
                      onChange={(e) => setSummary(e.target.value)}
                      placeholder="What changed? (optional)"
                      className="w-full h-9 px-2.5 text-[12.5px] rounded-[8px] border border-hx bg-surface focus-ring"
                    />
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" onClick={() => setEditing(false)} disabled={savingEdit}><X className="h-3.5 w-3.5" /> Cancel</Button>
                      <Button onClick={saveEdit} loading={savingEdit}><Save className="h-3.5 w-3.5" /> Save as new version</Button>
                    </div>
                  </div>
                ) : selectedContent != null ? (
                  <>
                    {renderAsMd ? (
                      <MarkdownView text={selectedContent} />
                    ) : (
                      <pre className="rounded-lg border border-hx bg-app-2 p-3 text-[12px] font-mono leading-relaxed text-ink-2 max-h-[70vh] overflow-auto whitespace-pre">
                        {selectedContent}
                      </pre>
                    )}
                    {curEntry?.truncated ? <p className="mt-2 text-[11px] text-ink-4">Showing the first portion — content was truncated.</p> : null}
                  </>
                ) : (
                  <div className="min-h-[280px] grid place-items-center">
                    <EmptyState
                      icon={renderAsMd ? <FileText className="h-4 w-4" /> : <FileCode className="h-4 w-4" />}
                      title={curEntry ? "No content for this version" : "Loading content…"}
                      description={curEntry?.note || "Fetching the stored bytes for this artifact version."}
                    />
                  </div>
                )}
              </>
            ) : !loading ? (
              <div className="min-h-[280px] grid place-items-center">
                <EmptyState
                  icon={<FileText className="h-4 w-4" />}
                  title={hasReal ? "Select an artifact to view" : "No artifacts yet"}
                  description={hasReal ? "Choose a file from the list to read it here." : "Artifacts appear here once the agents generate them for this project."}
                />
              </div>
            ) : null}
          </Card>
        </div>
      </div>
    </ProjectShell>
  );
}
