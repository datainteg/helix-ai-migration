"use client";

/**
 * /knowledge — BMAD knowledge base.
 *
 * Upload + search internal docs (Confluence dumps, runbooks, schema
 * dictionaries) that BMAD agents cite during planning. MVP uses keyword
 * search; vector embeddings are a future swap.
 */

import { useEffect, useId, useState } from "react";
import { BookOpen, Trash2, Plus } from "lucide-react";

import { AppShell } from "@/components/layout";
import {
  Button,
  Card,
  ConfirmModal,
  EmptyState,
  ErrorBanner,
  LoadingState,
  Modal,
  SearchInput,
} from "@/components/ui";
import { useAuth } from "@/lib/auth-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Doc {
  id: string;
  title: string;
  source_url: string | null;
  tags: string | null;
  content_length: number;
  created_at: string | null;
}

interface SearchHit {
  id: string;
  title: string;
  source_url: string | null;
  tags: string | null;
  excerpt: string;
}

export default function KnowledgePage() {
  const { token } = useAuth();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Doc | null>(null);
  const [deleting, setDeleting] = useState(false);
  const searchInputId = useId();

  const refresh = async () => {
    // SC-010: auth via the HttpOnly cookie (credentials:"include"); no token gate.
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/knowledge/docs?limit=200`, { credentials: "include" });
      if (!res.ok) throw new Error(`Failed to load (${res.status})`);
      setDocs(await res.json());
      setError("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void refresh(); }, [token]);

  const search = async () => {
    if (q.trim().length < 2) { setHits(null); return; }
    try {
      const res = await fetch(`${API_BASE}/api/v1/knowledge/search?q=${encodeURIComponent(q)}&limit=10`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error(`Search failed (${res.status})`);
      setHits(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/knowledge/docs/${pendingDelete.id}`, {
        method: "DELETE", credentials: "include",
      });
      if (!res.ok) throw new Error(`Delete failed (${res.status})`);
      setPendingDelete(null);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <AppShell
      eyebrow="ENTERPRISE CONTEXT"
      title="Knowledge base"
      description="Docs BMAD agents cite during planning. Keyword search MVP."
      crumbs={["Knowledge"]}
      actions={<Button onClick={() => setShowUpload(true)}><Plus className="h-3.5 w-3.5" aria-hidden /> Upload doc</Button>}
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <Card padding="sm" className="mb-4">
        <div className="flex items-center gap-2">
          {/* UI-026: shared SearchInput primitive (carries its own icon + aria-label). */}
          <SearchInput
            id={searchInputId}
            ariaLabel="Search uploaded docs"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void search(); }}
            placeholder="Search uploaded docs…"
            wrapperClassName="flex-1"
          />
          <Button size="sm" onClick={() => void search()}>Search</Button>
        </div>
      </Card>

      {hits !== null && (
        <div className="mb-6" role="region" aria-label="Search results">
          <div className="eyebrow text-[10px] mb-1.5" aria-live="polite">SEARCH RESULTS · {hits.length}</div>
          <div className="space-y-2">
            {hits.map((h) => (
              <Card key={h.id} bodyClassName="p-3">
                <div className="flex items-center gap-2 mb-1">
                  <BookOpen className="h-3.5 w-3.5 text-[var(--con-brand)]" aria-hidden />
                  <span className="text-[13px] font-medium">{h.title}</span>
                </div>
                <p className="text-[12px] text-ink-3 line-clamp-3">{h.excerpt}</p>
              </Card>
            ))}
          </div>
        </div>
      )}

      <div className="eyebrow text-[10px] mb-1.5">ALL DOCS · {docs.length}</div>
      {loading ? (
        <LoadingState label="Loading docs…" />
      ) : docs.length === 0 ? (
        <EmptyState title="No docs yet" description="Upload runbooks, schema dictionaries, or Confluence exports to enrich BMAD agent context." />
      ) : (
        <Card bodyClassName="p-0">
          <table className="w-full text-[13px]">
            <thead className="bg-surface-hi text-[10.5px] uppercase tracking-[0.08em] text-ink-4 font-mono">
              <tr>
                <th scope="col" className="px-3 py-2 text-left">Title</th>
                <th scope="col" className="px-3 py-2 text-left">Tags</th>
                <th scope="col" className="px-3 py-2 text-right">Size (B)</th>
                <th scope="col" className="px-3 py-2 text-left">Created</th>
                <th scope="col" className="px-3 py-2 text-right"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id} className="border-t border-hx hover:bg-surface-hi">
                  <td className="px-3 py-2 font-medium">{d.title}</td>
                  <td className="px-3 py-2 text-ink-3 font-mono text-[11.5px]">{d.tags || "—"}</td>
                  <td className="px-3 py-2 text-right font-mono">{d.content_length.toLocaleString()}</td>
                  <td className="px-3 py-2 text-ink-3 font-mono text-[11.5px]">{d.created_at?.slice(0, 10) ?? "—"}</td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => setPendingDelete(d)}
                      className="text-ink-3 hover:text-[var(--con-err)] p-1 rounded focus-ring"
                      aria-label={`Delete doc ${d.title}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <UploadDocModal
        open={showUpload}
        onClose={() => setShowUpload(false)}
        onCreated={async () => { setShowUpload(false); await refresh(); }}
      />

      <ConfirmModal
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => void confirmDelete()}
        title="Delete knowledge doc?"
        description={pendingDelete ? `“${pendingDelete.title}” will be removed permanently. BMAD agents will no longer cite it during planning.` : undefined}
        confirmLabel="Delete"
        destructive
        busy={deleting}
      />
    </AppShell>
  );
}

function UploadDocModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => Promise<void> }) {
  const { token } = useAuth();
  const [title, setTitle] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [tags, setTags] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const baseId = useId();
  const titleId = `${baseId}-title`;
  const sourceUrlId = `${baseId}-source`;
  const tagsId = `${baseId}-tags`;
  const contentId = `${baseId}-content`;

  // Reset state when reopening so a closed-then-reopened modal is fresh.
  useEffect(() => {
    if (open) {
      setTitle("");
      setSourceUrl("");
      setTags("");
      setContent("");
      setSaving(false);
      setErr("");
    }
  }, [open]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !content.trim()) {
      setErr("Title and content are required.");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/knowledge/docs`, {
        method: "POST",
        credentials: "include", // SC-010: auth via HttpOnly cookie
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          content,
          source_url: sourceUrl.trim() || undefined,
          tags: tags.trim() || undefined,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(detail.detail || `Upload failed (${res.status})`);
      }
      await onCreated();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Upload failed");
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Upload knowledge doc" width="md">
      <form onSubmit={submit} className="flex flex-col gap-3">
        {err && <ErrorBanner message={err} />}
        <div className="flex flex-col gap-1">
          <label htmlFor={titleId} className="text-[10px] uppercase tracking-wider font-mono text-ink-4">
            TITLE <span aria-hidden className="text-err">*</span>
            <span className="sr-only">(required)</span>
          </label>
          <input
            id={titleId}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            aria-required
            autoFocus
            className="h-8 px-2 text-[13px] rounded-[6px] border border-hx focus-ring"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={sourceUrlId} className="text-[10px] uppercase tracking-wider font-mono text-ink-4">SOURCE URL (optional)</label>
          <input id={sourceUrlId} value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} className="h-8 px-2 text-[13px] rounded-[6px] border border-hx focus-ring" />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={tagsId} className="text-[10px] uppercase tracking-wider font-mono text-ink-4">TAGS (comma-separated)</label>
          <input id={tagsId} value={tags} onChange={(e) => setTags(e.target.value)} className="h-8 px-2 text-[13px] rounded-[6px] border border-hx focus-ring" />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={contentId} className="text-[10px] uppercase tracking-wider font-mono text-ink-4">
            CONTENT (≤ 200 KB) <span aria-hidden className="text-err">*</span>
            <span className="sr-only">(required)</span>
          </label>
          <textarea
            id={contentId}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={10}
            required
            aria-required
            className="p-2 text-[12px] font-mono rounded-[6px] border border-hx focus-ring resize-y"
          />
        </div>
        <div className="flex gap-2 justify-end">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={saving}>{saving ? "Uploading…" : "Upload"}</Button>
        </div>
      </form>
    </Modal>
  );
}
