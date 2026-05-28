"use client";

/**
 * <SchemaDriftCard projectId sourceRef />
 *
 * Surfaces snapshot history + diff for a single source connection. Lets an
 * operator take a fresh snapshot on demand. Empty payload + JSON paste field
 * supported for off-line testing; in production the snapshot is taken by a
 * scheduled job that hits the connector + posts the JSON here.
 */

import { useEffect, useState } from "react";
import { AlertTriangle, Camera, GitCompare, RefreshCw } from "lucide-react";

import { Button, Card, Chip } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import {
  computeDrift,
  listSnapshots,
  takeSnapshot,
  type SchemaDrift,
  type SchemaSnapshot,
  type SnapshotPayload,
} from "@/lib/schema-drift/api";

interface Props {
  projectId: string;
  sourceRef: string;
  /** Optional inline payload provider — typically a connector-aware caller
   * passes the discovered schema in. When omitted the card lets operators
   * paste JSON manually for ad-hoc snapshots. */
  fetchSchema?: () => Promise<SnapshotPayload>;
}

export function SchemaDriftCard({ projectId, sourceRef, fetchSchema }: Props) {
  const { token } = useAuth();
  const [snapshots, setSnapshots] = useState<SchemaSnapshot[]>([]);
  const [drift, setDrift] = useState<SchemaDrift | null>(null);
  const [loading, setLoading] = useState(true);
  const [taking, setTaking] = useState(false);
  const [error, setError] = useState("");
  const [pasted, setPasted] = useState("");
  const [showPaste, setShowPaste] = useState(false);

  const refresh = async () => {
    // SC-010: auth via the HttpOnly cookie; gate on the required path params only.
    if (!projectId || !sourceRef) return;
    setLoading(true);
    try {
      const [snaps, d] = await Promise.all([
        listSnapshots(token, projectId, sourceRef),
        computeDrift(token, projectId, sourceRef),
      ]);
      setSnapshots(snaps);
      setDrift(d);
      setError("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load drift state");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void refresh(); }, [token, projectId, sourceRef]);

  const onTakeSnapshot = async (payload: SnapshotPayload) => {
    setTaking(true);
    setError("");
    try {
      await takeSnapshot(token, projectId, sourceRef, payload);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Snapshot failed");
    } finally {
      setTaking(false);
    }
  };

  const onConnectorSnapshot = async () => {
    if (!fetchSchema) {
      setShowPaste(true);
      return;
    }
    try {
      const payload = await fetchSchema();
      await onTakeSnapshot(payload);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Schema fetch failed");
    }
  };

  const onPasteSnapshot = async () => {
    try {
      const payload = JSON.parse(pasted) as SnapshotPayload;
      await onTakeSnapshot(payload);
      setPasted("");
      setShowPaste(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? `Paste invalid: ${e.message}` : "Invalid JSON");
    }
  };

  return (
    <Card
      title={<span className="flex items-center gap-2"><GitCompare className="h-4 w-4 text-[var(--con-brand)]" /> Schema drift watcher</span>}
      actions={
        <>
          <Button variant="outline" size="sm" onClick={() => void refresh()}><RefreshCw className="h-3.5 w-3.5" /> Refresh</Button>
          <Button size="sm" onClick={() => void onConnectorSnapshot()} disabled={taking}>
            <Camera className="h-3.5 w-3.5" /> {taking ? "Snapshotting…" : "Take snapshot"}
          </Button>
        </>
      }
    >
      {error && (
        <div className="mb-3 px-3 py-2 rounded-[8px] border border-hx-2 bg-[var(--con-err-soft,#fef2f2)] text-[12.5px] text-ink-2">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 text-[12.5px] text-ink-3 mb-3">
        <span>
          <span className="font-mono text-ink-2">{snapshots.length}</span> snapshot{snapshots.length === 1 ? "" : "s"} for
          {" "}<span className="font-mono">{sourceRef}</span>
        </span>
        {drift?.drift_detected ? (
          <Chip tone="err" dot>drift detected</Chip>
        ) : drift && snapshots.length >= 2 ? (
          <Chip tone="ok" dot>no drift</Chip>
        ) : (
          <Chip tone="default">baseline only</Chip>
        )}
      </div>

      {loading ? (
        <p className="text-[12.5px] text-ink-3">Loading…</p>
      ) : drift?.drift_detected ? (
        <DriftDetails drift={drift} />
      ) : drift?.note ? (
        <p className="text-[12.5px] text-ink-3">{drift.note}</p>
      ) : null}

      {showPaste && (
        <div className="mt-3 p-2 rounded-[8px] border border-hx bg-app-2">
          <p className="text-[11.5px] text-ink-3 mb-1.5">
            Paste snapshot JSON ({"{ \"schemas\": [...], \"tables\": [{schema_name, table_name, columns:[{name,data_type}]}] }"})
          </p>
          <textarea
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            rows={6}
            className="w-full p-2 text-[11.5px] font-mono rounded-[6px] border border-hx bg-surface focus-ring"
            placeholder='{"schemas": ["public"], "tables": [...]}'
          />
          <div className="mt-2 flex gap-2 justify-end">
            <Button size="sm" variant="outline" onClick={() => setShowPaste(false)}>Cancel</Button>
            <Button size="sm" onClick={() => void onPasteSnapshot()}>Record</Button>
          </div>
        </div>
      )}
    </Card>
  );
}

function DriftDetails({ drift }: { drift: SchemaDrift }) {
  return (
    <div className="space-y-3 text-[12.5px]">
      <div className="flex items-start gap-2 px-3 py-2 rounded-[8px] border border-hx-2 bg-[var(--con-warn-soft,#fff7e6)] text-ink-2">
        <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0 text-[var(--con-warn,#b45309)]" />
        <span>
          Source has drifted since the baseline snapshot
          {drift.baseline_taken_at ? <> ({drift.baseline_taken_at.slice(0, 10)})</> : null}.
        </span>
      </div>

      {drift.added_tables.length > 0 && (
        <div>
          <div className="eyebrow text-[10px]">ADDED TABLES</div>
          <ul className="mt-1 font-mono text-[11.5px] text-ink-2 space-y-0.5">
            {drift.added_tables.map((t) => <li key={t}>+ {t}</li>)}
          </ul>
        </div>
      )}
      {drift.removed_tables.length > 0 && (
        <div>
          <div className="eyebrow text-[10px]">REMOVED TABLES</div>
          <ul className="mt-1 font-mono text-[11.5px] text-ink-2 space-y-0.5">
            {drift.removed_tables.map((t) => <li key={t}>- {t}</li>)}
          </ul>
        </div>
      )}
      {drift.column_changes.length > 0 && (
        <div>
          <div className="eyebrow text-[10px]">COLUMN CHANGES</div>
          <ul className="mt-1 font-mono text-[11.5px] text-ink-2 space-y-1">
            {drift.column_changes.map((c) => (
              <li key={`${c.schema}.${c.table}`} className="space-y-0.5">
                <div className="text-ink-3">{c.schema}.{c.table}</div>
                {c.added_columns.length > 0 && <div className="ml-3 text-[var(--con-ok)]">+ {c.added_columns.join(", ")}</div>}
                {c.removed_columns.length > 0 && <div className="ml-3 text-[var(--con-err)]">- {c.removed_columns.join(", ")}</div>}
                {c.type_changes.map((t) => (
                  <div key={t.column} className="ml-3 text-[var(--con-warn)]">~ {t.column}: {t.from} → {t.to}</div>
                ))}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
