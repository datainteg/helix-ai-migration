"use client";

/**
 * /artifacts/[id] — Artifact detail page.
 *
 * Surfaces:
 *  - Metadata (filename, type, status, rollback link)
 *  - Generate-rollback button (only if no rollback linked yet)
 *  - Pair-review button + reviewer selection
 *  - Latest pair-review findings (when present)
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ShieldCheck, FileCode, RotateCcw, Sparkles } from "lucide-react";

import { AppShell } from "@/components/layout";
import { Button, Card, Chip, ErrorBanner, LoadingState } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface ArtifactDetail {
  id: string;
  filename: string;
  file_type?: string;
  status?: string;
  storage_path?: string;
  rollback_artifact_id?: string | null;
  created_at?: string;
}

interface PairReviewResp {
  review_id: string;
  artifact_id: string;
  reviewer_provider: string;
  reviewer_model: string;
  findings_preview: string;
}

export default function ArtifactDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [art, setArt] = useState<ArtifactDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reviewerModel, setReviewerModel] = useState("");
  const [reviewerProvider, setReviewerProvider] = useState("");
  const [pairReview, setPairReview] = useState<PairReviewResp | null>(null);
  const [rolling, setRolling] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  const refresh = async () => {
    if (!id) return;
    setLoading(true);
    try {
      // SC-010: auth via the HttpOnly cookie (credentials:"include").
      const res = await fetch(`${API_BASE}/api/v1/artifacts/${id}`, { credentials: "include" });
      if (!res.ok) throw new Error(`Failed (${res.status})`);
      setArt(await res.json());
      setError("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void refresh(); }, [token, id]);

  const generateRollback = async () => {
    if (!id) return;
    setRolling(true);
    setError("");
    try {
      // SC-010: auth via the HttpOnly cookie (credentials:"include").
      const res = await fetch(`${API_BASE}/api/v1/artifacts/${id}/generate-rollback`, {
        method: "POST", credentials: "include",
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(detail.detail || `Failed (${res.status})`);
      }
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Rollback generation failed");
    } finally {
      setRolling(false);
    }
  };

  const runPairReview = async () => {
    if (!id) return;
    setReviewing(true);
    setError("");
    setPairReview(null);
    try {
      // SC-010: auth via the HttpOnly cookie (credentials:"include").
      const res = await fetch(`${API_BASE}/api/v1/artifacts/${id}/pair-review`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reviewer_model: reviewerModel || null,
          reviewer_provider_type: reviewerProvider || null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(detail.detail || `Failed (${res.status})`);
      }
      setPairReview(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Pair review failed");
    } finally {
      setReviewing(false);
    }
  };

  return (
    <AppShell
      eyebrow="ARTIFACT REVIEW"
      title={art?.filename ?? "Artifact"}
      crumbs={[{ label: "Projects", href: "/projects" }, { label: art?.filename ?? "—" }]}
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {loading ? (
        <LoadingState label="Loading artifact…" />
      ) : !art ? (
        <p className="text-[12.5px] text-ink-3">Artifact not found.</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
          <Card title={<span className="flex items-center gap-2"><FileCode className="h-4 w-4 text-[var(--con-brand)]" /> Metadata</span>}>
            <dl className="grid grid-cols-2 gap-2 text-[12.5px]">
              <dt className="text-ink-3">Filename</dt>
              <dd className="font-mono">{art.filename}</dd>
              <dt className="text-ink-3">Type</dt>
              <dd className="font-mono">{art.file_type || "—"}</dd>
              <dt className="text-ink-3">Status</dt>
              <dd>{art.status ? <Chip tone="default">{art.status}</Chip> : "—"}</dd>
              <dt className="text-ink-3">Created</dt>
              <dd className="font-mono">{art.created_at?.slice(0, 19) || "—"}</dd>
              <dt className="text-ink-3">Storage</dt>
              <dd className="font-mono text-[11px] text-ink-3 break-all">{art.storage_path || "—"}</dd>
              <dt className="text-ink-3">Rollback linked</dt>
              <dd>{art.rollback_artifact_id
                ? <Chip tone="ok" dot>linked</Chip>
                : <Chip tone="default">none</Chip>}</dd>
            </dl>
            <div className="mt-4 flex gap-2 flex-wrap">
              <Button onClick={() => void generateRollback()} disabled={rolling || !!art.rollback_artifact_id}>
                <RotateCcw className="h-3.5 w-3.5" />
                {rolling ? "Generating…" : art.rollback_artifact_id ? "Rollback linked" : "Generate rollback"}
              </Button>
            </div>
          </Card>

          <Card title={<span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-[var(--con-brand)]" /> AI pair-review</span>}>
            <p className="text-[12.5px] text-ink-3 mb-3">
              Runs a second LLM against this artifact. Pick a different vendor than the
              generator to maximize cross-model divergence catch.
            </p>
            <label className="flex flex-col gap-1 mb-2">
              <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">REVIEWER PROVIDER (OPTIONAL)</span>
              <input
                value={reviewerProvider}
                onChange={(e) => setReviewerProvider(e.target.value)}
                placeholder="openai | anthropic | google | …"
                className="h-8 px-2 text-[13px] rounded-[6px] border border-hx focus-ring font-mono"
              />
            </label>
            <label className="flex flex-col gap-1 mb-3">
              <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">REVIEWER MODEL (OPTIONAL)</span>
              <input
                value={reviewerModel}
                onChange={(e) => setReviewerModel(e.target.value)}
                placeholder="gpt-4o | claude-haiku-4-5 | …"
                className="h-8 px-2 text-[13px] rounded-[6px] border border-hx focus-ring font-mono"
              />
            </label>
            <Button onClick={() => void runPairReview()} disabled={reviewing}>
              <Sparkles className="h-3.5 w-3.5" />
              {reviewing ? "Reviewing…" : "Run pair review"}
            </Button>
            {pairReview && (
              <div className="mt-4 p-3 rounded-[8px] border border-hx bg-app-2 text-[12px]">
                <div className="eyebrow text-[10px] mb-1">
                  REVIEWED BY {pairReview.reviewer_provider} · {pairReview.reviewer_model}
                </div>
                <pre className="whitespace-pre-wrap font-mono text-[11.5px] text-ink-2">{pairReview.findings_preview}</pre>
              </div>
            )}
          </Card>
        </div>
      )}
    </AppShell>
  );
}
