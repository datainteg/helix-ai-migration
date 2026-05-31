"use client";

/**
 * /projects/[id]/cutover — Cutover state-machine console.
 *
 * One page per project that lists in-flight cutovers + advances each through
 * bulk → tail → freeze → diff → flip → done (or rolled_back). Diff recording
 * is gated by state; the UI surfaces the allowed-next set so operators can't
 * even click an illegal transition.
 */

import { useEffect, useId, useState } from "react";
import { useParams } from "next/navigation";
import { Plus, RefreshCw } from "lucide-react";

import { ProjectShell } from "@/components/layout/ProjectShell";
import { useProjectKey } from "@/lib/projects/useProjectKey";
import { Button, Card, Chip, EmptyState, LoadingState, ErrorBanner, Modal } from "@/components/ui";
import { SchemaDriftCard } from "@/components/SchemaDriftCard";
import { useAuth } from "@/lib/auth-context";
import {
  ALLOWED_NEXT,
  CUTOVER_STATE_ORDER,
  Cutover,
  CutoverState,
  createCutover,
  listCutovers,
  recordDiff,
  transitionCutover,
} from "@/lib/cutovers/api";

const STATE_TONE: Record<CutoverState, "default" | "indigo" | "amber" | "ok" | "err"> = {
  bulk: "indigo",
  tail: "indigo",
  freeze: "amber",
  diff: "amber",
  flip: "indigo",
  done: "ok",
  rolled_back: "err",
};

export default function ProjectCutoverPage() {
  const projectKey = String(useParams<{ id: string }>().id);
  const { id } = useProjectKey(projectKey);
  const { token } = useAuth();
  const [items, setItems] = useState<Cutover[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const refresh = async () => {
    if (!token || !id) return;
    setLoading(true);
    try {
      const rows = await listCutovers(token, String(id));
      setItems(rows);
      setError("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void refresh(); }, [token, id]);

  return (
    <ProjectShell
      projectId={projectKey}
      projectName="Untitled project"
      projectStatus="active"
      subtitle="Cutover orchestration. Plan, run, freeze, diff and flip."
      actions={
        <>
          <Button variant="outline" onClick={() => void refresh()}><RefreshCw className="h-3.5 w-3.5" /> Refresh</Button>
          <Button variant="primary" onClick={() => setShowCreate(true)}><Plus className="h-3.5 w-3.5" /> New cutover</Button>
        </>
      }
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}
      {loading ? (
        <LoadingState label="Loading cutovers…" />
      ) : items.length === 0 ? (
        <EmptyState
          title="No cutovers yet"
          description="A cutover row records the bulk-load → tail-sync → freeze → diff → flip transition for one source/target pair."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((c) => (
            <div key={c.id} className="flex flex-col gap-3">
              <CutoverCard c={c} onChange={refresh} setError={setError} />
              {/* Drift watcher per cutover. Source mutations during the
                  tail-sync window are the single biggest gotcha; surface
                  them next to the state machine so operators see the alert
                  before they advance to flip. */}
              <SchemaDriftCard projectId={c.project_id} sourceRef={c.source_ref} />
            </div>
          ))}
        </div>
      )}
      <CreateCutoverModal
        open={showCreate}
        projectId={String(id)}
        onClose={() => setShowCreate(false)}
        onCreated={async () => { setShowCreate(false); await refresh(); }}
      />
    </ProjectShell>
  );
}

function CutoverCard({ c, onChange, setError }: { c: Cutover; onChange: () => Promise<void>; setError: (s: string) => void }) {
  const { token } = useAuth();
  const allowed = ALLOWED_NEXT[c.state] ?? [];

  const onTransition = async (next: CutoverState) => {
    if (!token) return;
    try {
      await transitionCutover(token, c.id, next);
      await onChange();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Transition failed");
    }
  };

  return (
    <Card>
      <div className="flex flex-wrap gap-3 items-center justify-between">
        <div className="min-w-0">
          <div className="text-[10.5px] uppercase tracking-[0.08em] text-ink-4 font-mono">
            {c.source_ref} → {c.target_ref}
          </div>
          <div className="font-mono text-[12px] text-ink-3 truncate">{c.id}</div>
        </div>
        <Chip tone={STATE_TONE[c.state]} dot>{c.state}</Chip>
      </div>
      <div className="mt-3 grid grid-cols-3 sm:grid-cols-6 gap-2">
        {CUTOVER_STATE_ORDER.map((s) => {
          const ts = c.timestamps[s];
          return (
            <div key={s} className={`px-2 py-1 rounded-md border ${ts ? "border-hx-2 bg-surface-hi" : "border-hx text-ink-4"}`}>
              <div className="text-[10px] uppercase tracking-wider font-mono">{s}</div>
              <div className="text-[10.5px] text-ink-3 truncate">{ts ? new Date(ts).toLocaleString() : "—"}</div>
            </div>
          );
        })}
      </div>
      {c.diff_summary && (
        <div className="mt-3 text-[12.5px] text-ink-3">
          Pre-flip diff: source <span className="font-mono">{c.diff_summary.source_count}</span>
          {" / "}target <span className="font-mono">{c.diff_summary.target_count}</span>
          {" — "}
          <span className="font-mono">{c.diff_summary.diff_pct.toFixed(4)}%</span> diff over {c.diff_summary.sample_size} rows.
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {c.state === "diff" && !c.diff_summary && (
          <RecordDiffInline cutoverId={c.id} onSaved={onChange} setError={setError} />
        )}
        {allowed.map((s) => (
          <Button
            key={s}
            variant={s === "rolled_back" ? "danger" : (s === "done" ? "primary" : "outline")}
            onClick={() => void onTransition(s)}
            disabled={s === "flip" && !c.diff_summary}
            title={s === "flip" && !c.diff_summary ? "Record pre-flip diff first" : undefined}
          >
            → {s}
          </Button>
        ))}
        {allowed.length === 0 && (
          <span className="text-[12px] text-ink-4">Terminal state</span>
        )}
      </div>
    </Card>
  );
}

function RecordDiffInline({ cutoverId, onSaved, setError }: { cutoverId: string; onSaved: () => Promise<void>; setError: (s: string) => void }) {
  const { token } = useAuth();
  const [src, setSrc] = useState("");
  const [tgt, setTgt] = useState("");
  const [sample, setSample] = useState("100");
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!token) return;
    const srcN = Number(src);
    const tgtN = Number(tgt);
    const sampleN = Number(sample);
    if (!Number.isFinite(srcN) || !Number.isFinite(tgtN) || !Number.isFinite(sampleN)) {
      setError("Enter numeric source_count, target_count, sample_size");
      return;
    }
    const diff = srcN === 0 ? (tgtN === 0 ? 0 : 100) : (Math.abs(srcN - tgtN) / srcN) * 100;
    setSaving(true);
    try {
      await recordDiff(token, cutoverId, {
        source_count: srcN,
        target_count: tgtN,
        diff_pct: diff,
        sample_size: sampleN,
      });
      await onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Diff record failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="w-full flex flex-wrap gap-2 items-end p-2 rounded-md border border-hx bg-app-2">
      <span className="text-[10px] uppercase tracking-wider font-mono text-ink-3 self-center">PRE-FLIP DIFF</span>
      <Input label="source" value={src} onChange={setSrc} />
      <Input label="target" value={tgt} onChange={setTgt} />
      <Input label="sample" value={sample} onChange={setSample} />
      <Button onClick={() => void submit()} disabled={saving}>{saving ? "Saving…" : "Record"}</Button>
    </div>
  );
}

function Input({ label, value, onChange }: { label: string; value: string; onChange: (s: string) => void }) {
  const id = useId();
  return (
    <div className="flex flex-col">
      <label htmlFor={id} className="text-[9.5px] uppercase tracking-wider font-mono text-ink-4">{label}</label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-24 h-8 px-2 text-[12.5px] rounded-[6px] border border-hx bg-surface text-ink focus-ring"
      />
    </div>
  );
}

function CreateCutoverModal({ open, projectId, onClose, onCreated }: { open: boolean; projectId: string; onClose: () => void; onCreated: () => Promise<void> }) {
  const { token } = useAuth();
  const [src, setSrc] = useState("");
  const [tgt, setTgt] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const baseId = useId();
  const srcId = `${baseId}-src`;
  const tgtId = `${baseId}-tgt`;
  const notesId = `${baseId}-notes`;

  // Reset state when reopened.
  useEffect(() => {
    if (open) {
      setSrc(""); setTgt(""); setNotes("");
      setSaving(false); setErr("");
    }
  }, [open]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    if (!src.trim() || !tgt.trim()) {
      setErr("Source + target are required");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      await createCutover(token, projectId, {
        source_ref: src.trim(),
        target_ref: tgt.trim(),
        notes: notes.trim() || undefined,
      });
      await onCreated();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Create failed");
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="New cutover" width="md">
      <form onSubmit={submit} className="flex flex-col gap-3">
        {err && <ErrorBanner message={err} />}
        <div className="flex flex-col gap-1">
          <label htmlFor={srcId} className="text-[10px] uppercase tracking-wider font-mono text-ink-4">
            SOURCE REF <span aria-hidden className="text-err">*</span>
            <span className="sr-only">(required)</span>
          </label>
          <input id={srcId} value={src} onChange={(e) => setSrc(e.target.value)} required aria-required autoFocus placeholder="oracle://ar/ar_payment" className="h-8 px-2 text-[13px] rounded-[6px] border border-hx bg-surface focus-ring" />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={tgtId} className="text-[10px] uppercase tracking-wider font-mono text-ink-4">
            TARGET REF <span aria-hidden className="text-err">*</span>
            <span className="sr-only">(required)</span>
          </label>
          <input id={tgtId} value={tgt} onChange={(e) => setTgt(e.target.value)} required aria-required placeholder="snowflake://AR.PAYMENT" className="h-8 px-2 text-[13px] rounded-[6px] border border-hx bg-surface focus-ring" />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={notesId} className="text-[10px] uppercase tracking-wider font-mono text-ink-4">NOTES</label>
          <textarea id={notesId} value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className="p-2 text-[12.5px] rounded-[6px] border border-hx bg-surface focus-ring resize-none" />
        </div>
        <div className="flex gap-2 justify-end mt-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={saving}>{saving ? "Creating…" : "Create"}</Button>
        </div>
      </form>
    </Modal>
  );
}
