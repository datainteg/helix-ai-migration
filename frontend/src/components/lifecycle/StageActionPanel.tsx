"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Modal, ErrorBanner } from "@/components/ui";
import * as api from "@/lib/lifecycle/api";
import type { MigrationStage } from "@/lib/lifecycle/api";
import { isAgentRunnable } from "./labels";

interface Props {
  projectId: string;        // canonical UUID for API calls
  projectKey: string;       // slug/id for links
  stage: MigrationStage;
  canWrite: boolean;
  canApprove: boolean;
  onChanged: () => void;    // refetch after a successful action
}

type Prompt = { action: string; title: string; label: string; required: boolean; run: (text: string) => Promise<unknown> };

const DONE = ["approved", "completed", "skipped"];

export function StageActionPanel({ projectId, projectKey, stage, canWrite, canApprove, onChanged }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  const [text, setText] = useState("");

  const runnable = isAgentRunnable(stage.assigned_agent);
  const s = stage.status;
  const reviewable = ["generated", "under_review", "resubmitted", "edit_requested"].includes(s);

  async function run(action: string, fn: () => Promise<unknown>) {
    setBusy(action); setErr(null);
    try { await fn(); onChanged(); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(null); }
  }

  function openPrompt(p: Prompt) { setPrompt(p); setText(""); setErr(null); }

  async function submitPrompt() {
    if (!prompt) return;
    if (prompt.required && !text.trim()) { setErr("This field is required."); return; }
    const p = prompt; setPrompt(null);
    await run(p.action, () => p.run(text.trim()));
  }

  const reviewHref = stage.current_artifact_id
    ? `/projects/${projectKey}/artifacts/${stage.current_artifact_id}/review`
    : null;

  return (
    <div className="space-y-3">
      {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}
      <div className="flex flex-wrap gap-2">
        {/* Non-agent stages (sprint execution / sign-off / closure) have no
            artifact to approve — they are completed to advance the lifecycle. */}
        {canWrite && !runnable && (s === "not_started" || s === "running" || s === "failed") && (
          <Button disabled={!!busy} onClick={() => run("complete", async () => {
            await api.completeStage(projectId, stage.stage_key);
          })}>
            {busy === "complete" ? "Completing…" : "Mark Stage Complete"}
          </Button>
        )}

        {/* Run / regenerate (authoring) */}
        {canWrite && runnable && (s === "not_started" || s === "failed") && (
          <Button disabled={!!busy} onClick={() => run("run", () => api.runStageAgent(projectId, stage.stage_key))}>
            {busy === "run" ? "Running…" : "Run Agent"}
          </Button>
        )}
        {canWrite && runnable && (reviewable || s === "rejected") && (
          <Button variant="outline" disabled={!!busy} onClick={() => openPrompt({
            action: "regen", title: "Regenerate artifact", label: "Optional instructions for the agent", required: false,
            run: (t) => api.regenerateStageAgent(projectId, stage.stage_key, t || undefined),
          })}>
            {busy === "regen" ? "Regenerating…" : "Regenerate"}
          </Button>
        )}

        {/* Review / edit */}
        {reviewHref && reviewable && (
          <Button variant="secondary" onClick={() => router.push(reviewHref)}>Open Artifact</Button>
        )}

        {/* Submit / resubmit (authoring) */}
        {canWrite && (s === "generated" || s === "running") && stage.current_artifact_id && (
          <Button variant="outline" disabled={!!busy}
            onClick={() => run("submit", () => api.submitStageForReview(projectId, stage.stage_key, stage.current_artifact_id || undefined))}>
            Submit for Review
          </Button>
        )}
        {canWrite && (s === "edit_requested" || s === "rejected") && (
          <Button variant="outline" disabled={!!busy}
            onClick={() => run("resubmit", () => api.resubmitStage(projectId, stage.stage_key))}>
            Resubmit
          </Button>
        )}

        {/* Approval (reviewer) */}
        {canApprove && reviewable && (
          <Button disabled={!!busy} onClick={() => openPrompt({
            action: "approve", title: "Approve stage", label: "Optional approval note", required: false,
            run: (t) => api.approveStage(projectId, stage.stage_key, t || undefined),
          })}>
            {busy === "approve" ? "Approving…" : "Approve"}
          </Button>
        )}
        {canApprove && reviewable && (
          <Button variant="outline" disabled={!!busy} onClick={() => openPrompt({
            action: "changes", title: "Request changes", label: "What needs to change?", required: true,
            run: (t) => api.requestStageChanges(projectId, stage.stage_key, t),
          })}>
            Request Changes
          </Button>
        )}
        {canApprove && reviewable && (
          <Button variant="danger" disabled={!!busy} onClick={() => openPrompt({
            action: "reject", title: "Reject stage", label: "Reason for rejection", required: true,
            run: (t) => api.rejectStage(projectId, stage.stage_key, t),
          })}>
            Reject
          </Button>
        )}

        {/* Skip optional */}
        {canWrite && stage.is_optional && !DONE.includes(s) && (
          <Button variant="ghost" disabled={!!busy} onClick={() => openPrompt({
            action: "skip", title: "Skip optional stage", label: "Reason for skipping", required: true,
            run: (t) => api.skipStage(projectId, stage.stage_key, t),
          })}>
            Skip Optional Stage
          </Button>
        )}

        {/* Continue */}
        {canWrite && DONE.includes(s) && (
          <Button disabled={!!busy} onClick={() => run("continue", async () => {
            const r = await api.continueAfterApproval(projectId, stage.stage_key);
            if (r.next_stage) router.push(`/projects/${projectKey}/lifecycle/${r.next_stage}`);
          })}>
            {busy === "continue" ? "Continuing…" : "Continue to Next Stage"}
          </Button>
        )}
      </div>

      {prompt && (
        <Modal open title={prompt.title} onClose={() => setPrompt(null)} width="md">
          <div className="space-y-3">
            {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}
            <label className="block text-[12px] text-ink-2">{prompt.label}{prompt.required && " *"}</label>
            <textarea
              className="w-full rounded-md border border-hx bg-app px-3 py-2 text-[13px] text-ink-1 focus:border-helix-400 focus:outline-none"
              rows={4} value={text} onChange={(e) => setText(e.target.value)} autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setPrompt(null)}>Cancel</Button>
              <Button onClick={submitPrompt}>Confirm</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
