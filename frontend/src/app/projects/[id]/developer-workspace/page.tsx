"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Upload, FileCode, History, GitCompare, Hash, FileType2, Clock, Pencil, Save, X } from "lucide-react";
import { ProjectShell } from "@/components/layout/ProjectShell";
import { Card, Button, Chip, EmptyState, LoadingState, ErrorBanner } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useRegisterCrumbLabel } from "@/lib/breadcrumbs";
import {
  listProjectArtifacts, listArtifactVersions, fetchArtifactContent, saveArtifactContent,
  type Artifact, type ArtifactVersion, type ArtifactContent,
} from "@/lib/artifacts/api";
import { CodeBlock } from "./CodeBlock";
import { DiffView } from "./DiffView";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * Developer Workspace — artifact explorer · code/diff · AI review.
 *
 * Version control: each artifact has 1+ CodeArtifactVersion rows. We list them
 * (newest first), let the user pick any version to view its REAL stored content
 * (GET /artifacts/{id}/content?version=N), and diff a version against the one
 * immediately older. Content is fetched + cached per (artifact, version); we
 * never fabricate it — an honest empty state shows when bytes are unavailable.
 */
export default function ProjectDevWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const { token, can } = useAuth();
  const canWrite = can("project:write");
  const [projectName, setProjectName] = useState("Project");
  const [artifacts, setArtifacts] = useState<Artifact[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [versions, setVersions] = useState<ArtifactVersion[]>([]);
  const [activeVerIdx, setActiveVerIdx] = useState(0); // 0 = latest
  const [contentCache, setContentCache] = useState<Record<string, ArtifactContent>>({});
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"code" | "diff">("code");
  // edit state
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [summary, setSummary] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [editErr, setEditErr] = useState("");
  const [versionsReloadKey, setVersionsReloadKey] = useState(0);

  useRegisterCrumbLabel(String(id), projectName !== "Project" ? projectName : undefined);

  // Real project name for the header/breadcrumb.
  useEffect(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/v1/projects/${id}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => setProjectName(p?.name || "Project"))
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

  // Whenever the active version (or its older sibling for diff) changes, load content.
  useEffect(() => {
    ensureContent(versions[activeVerIdx]?.version_number);
    ensureContent(versions[activeVerIdx + 1]?.version_number);
  }, [versions, activeVerIdx, ensureContent]);

  const hasReal = (artifacts?.length ?? 0) > 0;
  const selected = hasReal ? artifacts!.find((a) => a.id === selectedId) ?? null : null;

  const activeVer = versions[activeVerIdx];
  const olderVer = versions[activeVerIdx + 1];
  const curEntry = selectedId && activeVer ? contentCache[keyFor(selectedId, activeVer.version_number)] : undefined;
  const prevEntry = selectedId && olderVer ? contentCache[keyFor(selectedId, olderVer.version_number)] : undefined;
  const selectedContent = curEntry?.content ?? null;
  const prevContent = prevEntry?.content ?? null;
  const canDiff = Boolean(selectedContent && prevContent);

  useEffect(() => { if (!canDiff && view === "diff") setView("code"); }, [canDiff, view]);

  const startEdit = () => { setDraft(selectedContent ?? ""); setSummary(""); setEditErr(""); setEditing(true); setView("code"); };
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

  const lang = useMemo(
    () => selected?.file_type || selected?.ext || selected?.filename?.split(".").pop(),
    [selected],
  );

  return (
    <ProjectShell projectId={String(id)} projectName={projectName} subtitle="Three-pane IDE: artifact explorer · version control · AI review">
      {loading ? <LoadingState label="Loading artifacts…" /> : null}
      <div className="grid grid-cols-12 gap-4">
        <Card className="col-span-12 lg:col-span-3" title="Artifacts" padding="sm">
          {hasReal ? (
            <ul className="space-y-1 text-[12.5px]">
              {artifacts!.map((f) => (
                <li
                  key={f.id}
                  onClick={() => setSelectedId(f.id)}
                  className={`px-2 py-1.5 rounded-md flex items-center gap-2 cursor-pointer ${f.id === selectedId ? "bg-helix-50 text-helix-700" : "text-ink-3 hover:bg-app-2"}`}
                >
                  <FileCode className="h-3.5 w-3.5" />{f.filename}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[12px] text-ink-3 py-2">No artifacts yet. Upload one to get started.</p>
          )}
          <Button variant="outline" size="sm" className="w-full mt-3 justify-center"><Upload className="h-3.5 w-3.5" /> Upload</Button>
          <hr className="border-hx my-3" />
          <p className="text-[11.5px] text-ink-3 uppercase tracking-wider font-medium mb-2 flex items-center gap-1"><History className="h-3 w-3" /> Version history</p>
          {versions.length > 0 ? (
            <ul className="space-y-1 text-[12px]">
              {versions.map((v, i) => (
                <li key={v.id}>
                  <button
                    type="button"
                    onClick={() => setActiveVerIdx(i)}
                    className={`w-full text-left px-2 py-1.5 rounded-md flex items-center justify-between gap-2 ${i === activeVerIdx ? "bg-helix-50 text-helix-700" : "text-ink-2 hover:bg-app-2"}`}
                  >
                    <span className="font-mono">v{v.version_number}</span>
                    <span className="flex items-center gap-1.5">
                      {v.approval_status ? <Chip tone={v.approval_status === "approved" ? "green" : "zinc"}>{v.approval_status}</Chip> : null}
                      {i === 0 ? <Chip tone="indigo">latest</Chip> : null}
                    </span>
                  </button>
                  {v.change_summary ? <p className="px-2 text-[11px] text-ink-4 truncate">{v.change_summary}</p> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[12px] text-ink-3">No versions yet.</p>
          )}
        </Card>

        <div className="col-span-12 lg:col-span-6 space-y-4">
          <Card>
            {selected ? (
              <>
                <div className="flex items-center gap-2 text-[12.5px] border-b border-hx -mx-5 px-5 pb-3 mb-4">
                  <FileCode className="h-3.5 w-3.5 text-ink-3" />
                  <span className="font-medium text-ink">{selected.filename}</span>
                  {activeVer ? <Chip tone="zinc">v{activeVer.version_number}</Chip> : null}
                  {selected.file_type ? <Chip tone="zinc">{selected.file_type}</Chip> : null}
                  {(selectedContent || canDiff) && !editing ? (
                    <div className="ml-auto flex items-center gap-1">
                      <button type="button" onClick={() => setView("code")}
                        className={`text-[12px] px-2 py-0.5 rounded-md ${view === "code" ? "bg-helix-50 text-helix-700" : "text-ink-3 hover:bg-app-2"}`}>
                        Code
                      </button>
                      <button type="button" onClick={() => canDiff && setView("diff")} disabled={!canDiff}
                        title={canDiff ? `Compare v${olderVer?.version_number} → v${activeVer?.version_number}` : "Need an older version with content to diff"}
                        className={`text-[12px] px-2 py-0.5 rounded-md inline-flex items-center gap-1 ${view === "diff" ? "bg-helix-50 text-helix-700" : "text-ink-3 hover:bg-app-2"} ${!canDiff ? "opacity-40 cursor-not-allowed" : ""}`}>
                        <GitCompare className="h-3 w-3" /> Diff
                      </button>
                      {canWrite && selectedContent ? (
                        <button type="button" onClick={startEdit}
                          className="text-[12px] px-2 py-0.5 rounded-md inline-flex items-center gap-1 text-ink-3 hover:bg-app-2">
                          <Pencil className="h-3 w-3" /> Edit
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                </div>

                {editing ? (
                  <div className="flex flex-col gap-3">
                    {editErr ? <ErrorBanner message={editErr} onDismiss={() => setEditErr("")} /> : null}
                    <p className="text-[12px] text-ink-3">Editing creates a <strong>new version</strong> — the current one is kept in history. Use this to fix anything the AI generated incorrectly.</p>
                    <textarea
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      spellCheck={false}
                      rows={20}
                      className="w-full px-3 py-2 text-[12.5px] font-mono leading-relaxed rounded-lg border border-hx bg-app-2 focus-ring resize-y"
                    />
                    <input
                      value={summary}
                      onChange={(e) => setSummary(e.target.value)}
                      placeholder="What changed? (optional) e.g. removed extra DROP, added missing index"
                      className="w-full h-9 px-2.5 text-[12.5px] rounded-[8px] border border-hx bg-surface focus-ring"
                    />
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" onClick={() => setEditing(false)} disabled={savingEdit}><X className="h-3.5 w-3.5" /> Cancel</Button>
                      <Button onClick={saveEdit} loading={savingEdit}><Save className="h-3.5 w-3.5" /> Save as new version</Button>
                    </div>
                  </div>
                ) : view === "diff" && canDiff ? (
                  <DiffView
                    oldText={prevContent!}
                    newText={selectedContent!}
                    oldLabel={`v${olderVer?.version_number}`}
                    newLabel={`v${activeVer?.version_number}`}
                  />
                ) : selectedContent ? (
                  <>
                    <CodeBlock code={selectedContent} language={lang} filename={selected.filename} />
                    {curEntry?.truncated ? <p className="mt-2 text-[11px] text-ink-4">Showing the first 512 KB — content was truncated.</p> : null}
                  </>
                ) : (
                  <div className="rounded-lg border border-hx bg-app-2 p-5 min-h-[300px] flex flex-col">
                    <EmptyState
                      icon={<FileCode className="h-4 w-4" />}
                      title={curEntry ? "No content for this version" : "Loading content…"}
                      description={curEntry?.note || "Fetching the stored bytes for this artifact version."}
                    />
                    <dl className="mt-4 grid grid-cols-1 gap-2 text-[12px] border-t border-hx pt-4">
                      {selected.file_type ? (
                        <div className="flex items-center gap-2 text-ink-3">
                          <FileType2 className="h-3.5 w-3.5 text-ink-4" />
                          <span className="text-ink-4 w-24">Type</span>
                          <span className="font-mono text-ink-2">{selected.file_type}</span>
                        </div>
                      ) : null}
                      {(curEntry?.content_hash || selected.content_hash) ? (
                        <div className="flex items-center gap-2 text-ink-3">
                          <Hash className="h-3.5 w-3.5 text-ink-4" />
                          <span className="text-ink-4 w-24">Content hash</span>
                          <span className="font-mono text-ink-2 truncate">{(curEntry?.content_hash || selected.content_hash)!.slice(0, 16)}…</span>
                        </div>
                      ) : null}
                      {selected.created_at ? (
                        <div className="flex items-center gap-2 text-ink-3">
                          <Clock className="h-3.5 w-3.5 text-ink-4" />
                          <span className="text-ink-4 w-24">Created</span>
                          <span className="font-mono text-ink-2">{selected.created_at.slice(0, 19).replace("T", " ")}</span>
                        </div>
                      ) : null}
                    </dl>
                  </div>
                )}
              </>
            ) : (
              <div className="min-h-[300px] grid place-items-center">
                <EmptyState
                  icon={<FileCode className="h-4 w-4" />}
                  title="Select an artifact to view"
                  description="Choose a file from the artifact explorer to inspect it here."
                />
              </div>
            )}
          </Card>
        </div>

        <Card className="col-span-12 lg:col-span-3" title="AI Review" padding="sm">
          <EmptyState title="Awaiting analysis" description="Upload code to surface assumptions, risks, and security findings." />
        </Card>
      </div>
    </ProjectShell>
  );
}
