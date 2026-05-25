"use client";

/**
 * /knowledge — BMAD knowledge base.
 *
 * Upload + search internal docs (Confluence dumps, runbooks, schema
 * dictionaries) that BMAD agents cite during planning. MVP uses keyword
 * search; vector embeddings are a future swap.
 */

import { useEffect, useState } from "react";
import { BookOpen, Trash2, Plus, Search } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, ErrorBanner, EmptyState, LoadingState } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

  const refresh = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/knowledge/docs?limit=200`, { headers: { Authorization: `Bearer ${token}` } });
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
    if (!token || q.trim().length < 2) { setHits(null); return; }
    try {
      const res = await fetch(`${API_BASE}/api/v1/knowledge/search?q=${encodeURIComponent(q)}&limit=10`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Search failed (${res.status})`);
      setHits(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
    }
  };

  const remove = async (id: string) => {
    if (!token) return;
    if (!confirm("Delete this doc?")) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/knowledge/docs/${id}`, {
        method: "DELETE", headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Delete failed (${res.status})`);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  return (
    <AppShell
      eyebrow="ENTERPRISE CONTEXT"
      title="Knowledge base"
      description="Docs BMAD agents cite during planning. Keyword search MVP."
      crumbs={["Knowledge"]}
      actions={<Button onClick={() => setShowUpload(true)}><Plus className="h-3.5 w-3.5" /> Upload doc</Button>}
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <Card padding="sm" className="mb-4">
        <div className="flex items-center gap-2">
          <Search className="h-3.5 w-3.5 text-ink-4" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void search(); }}
            placeholder="Search uploaded docs…"
            className="flex-1 h-8 px-2 text-[13px] bg-transparent focus-ring"
          />
          <Button size="sm" onClick={() => void search()}>Search</Button>
        </div>
      </Card>

      {hits !== null && (
        <div className="mb-6">
          <div className="eyebrow text-[10px] mb-1.5">SEARCH RESULTS · {hits.length}</div>
          <div className="space-y-2">
            {hits.map((h) => (
              <Card key={h.id} bodyClassName="p-3">
                <div className="flex items-center gap-2 mb-1">
                  <BookOpen className="h-3.5 w-3.5 text-[var(--con-brand)]" />
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
                <th className="px-3 py-2 text-left">Title</th>
                <th className="px-3 py-2 text-left">Tags</th>
                <th className="px-3 py-2 text-right">Size (B)</th>
                <th className="px-3 py-2 text-left">Created</th>
                <th className="px-3 py-2 text-right"></th>
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
                    <button onClick={() => void remove(d.id)} className="text-ink-3 hover:text-[var(--con-err)]" aria-label="Delete">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {showUpload && (
        <UploadDocModal
          onClose={() => setShowUpload(false)}
          onCreated={async () => { setShowUpload(false); await refresh(); }}
        />
      )}
    </AppShell>
  );
}

function UploadDocModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => Promise<void> }) {
  const { token } = useAuth();
  const [title, setTitle] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [tags, setTags] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    if (!title.trim() || !content.trim()) {
      setErr("Title and content are required.");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/knowledge/docs`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
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
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"
      role="dialog" aria-modal="true"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <form onSubmit={submit} className="w-full max-w-lg bg-surface border border-hx rounded-[10px] p-4 flex flex-col gap-3">
        <h2 className="text-[14px] font-medium">Upload knowledge doc</h2>
        {err && <ErrorBanner message={err} />}
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">TITLE</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus className="h-8 px-2 text-[13px] rounded-[6px] border border-hx focus-ring" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">SOURCE URL (optional)</span>
          <input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} className="h-8 px-2 text-[13px] rounded-[6px] border border-hx focus-ring" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">TAGS (comma-separated)</span>
          <input value={tags} onChange={(e) => setTags(e.target.value)} className="h-8 px-2 text-[13px] rounded-[6px] border border-hx focus-ring" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">CONTENT (≤ 200 KB)</span>
          <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={10} className="p-2 text-[12px] font-mono rounded-[6px] border border-hx focus-ring resize-y" />
        </label>
        <div className="flex gap-2 justify-end">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={saving}>{saving ? "Uploading…" : "Upload"}</Button>
        </div>
      </form>
    </div>
  );
}
