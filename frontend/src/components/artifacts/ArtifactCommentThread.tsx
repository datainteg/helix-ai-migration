"use client";

import { useEffect, useState } from "react";
import { Button, ErrorBanner } from "@/components/ui";
import * as api from "@/lib/lifecycle/api";
import type { ArtifactComment } from "@/lib/lifecycle/api";

interface Props {
  artifactId: string;
  versionId?: string | null;
  canComment: boolean;
}

function fmt(ts: string | null) {
  if (!ts) return "";
  const d = new Date(ts);
  return isNaN(d.getTime()) ? ts : d.toLocaleString();
}

export function ArtifactCommentThread({ artifactId, versionId, canComment }: Props) {
  const [comments, setComments] = useState<ArtifactComment[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function load() {
    api.listArtifactComments(artifactId).then(setComments).catch((e) => setErr(String(e.message || e)));
  }
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [artifactId]);

  async function add() {
    if (!text.trim()) return;
    setBusy(true); setErr(null);
    try {
      await api.addArtifactComment(artifactId, text.trim(), versionId || undefined);
      setText(""); load();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="space-y-3">
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}
      {comments.length === 0 ? (
        <p className="text-[12px] text-ink-3">No comments yet.</p>
      ) : (
        <ul className="space-y-2">
          {comments.map((c) => (
            <li key={c.id} className="rounded-md border border-hx bg-app-2/40 px-3 py-2">
              <div className="flex items-center justify-between text-[11px] text-ink-3">
                <span className="font-mono">{(c.user_id || "system").slice(0, 8)}</span>
                <span>{fmt(c.created_at)}</span>
              </div>
              <p className="mt-1 whitespace-pre-wrap text-[13px] text-ink-1">{c.comment}</p>
            </li>
          ))}
        </ul>
      )}
      {canComment && (
        <div className="space-y-2">
          <textarea
            value={text} onChange={(e) => setText(e.target.value)} rows={3} placeholder="Add a comment…"
            className="w-full rounded-md border border-hx bg-app px-3 py-2 text-[13px] text-ink-1 focus:border-helix-400 focus:outline-none"
          />
          <div className="flex justify-end">
            <Button size="sm" disabled={busy || !text.trim()} onClick={add}>{busy ? "Posting…" : "Comment"}</Button>
          </div>
        </div>
      )}
    </div>
  );
}
