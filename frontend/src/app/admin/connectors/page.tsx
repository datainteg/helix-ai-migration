"use client";

/**
 * /admin/connectors — Connector Management.
 *
 * Lists every connector the platform supports (built-in + custom) from
 * /connectors/registry, with the capabilities each one declares. Real data;
 * read-only catalogue.
 */

import { useEffect, useState } from "react";
import { Check, Minus, Plug } from "lucide-react";

import { AdminShell } from "@/components/layout";
import { Card, Chip, ErrorBanner, LoadingState, EmptyState, Table, THead, TBody, TR, TH, TD } from "@/components/ui";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Connector {
  connector_type: string;
  display_name: string;
  mode: "built_in" | "custom";
  capabilities: Record<string, boolean>;
}

// The capability columns worth surfacing, in display order.
const CAP_COLS: { key: string; label: string }[] = [
  { key: "test_connection", label: "Test" },
  { key: "schema_discovery", label: "Schema" },
  { key: "table_discovery", label: "Tables" },
  { key: "column_discovery", label: "Columns" },
  { key: "row_count", label: "Row count" },
  { key: "table_profile", label: "Profile" },
  { key: "supports_recon", label: "Recon" },
];

export default function ConnectorsAdminPage() {
  const [rows, setRows] = useState<Connector[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/connectors/registry`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`Failed to load connectors (${r.status})`))))
      .then((d: Connector[]) => setRows(Array.isArray(d) ? d : []))
      .catch((e: unknown) => { setErr(e instanceof Error ? e.message : "Failed to load"); setRows([]); });
  }, []);

  const builtIn = (rows ?? []).filter((c) => c.mode === "built_in");
  const custom = (rows ?? []).filter((c) => c.mode === "custom");

  return (
    <AdminShell
      title="Connector Management"
      subtitle="Source and target connectors supported by this deployment, and the capabilities each one provides."
      page="Connector Management"
      actions={rows ? <Chip tone="brand" dot>{rows.length} connectors</Chip> : undefined}
    >
      {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
      {rows === null ? (
        <LoadingState label="Loading connector registry…" />
      ) : rows.length === 0 ? (
        <Card title="Connectors"><EmptyState title="No connectors registered" description="This deployment has no connectors available." /></Card>
      ) : (
        <>
          <CapTable title="Built-in connectors" rows={builtIn} />
          {custom.length > 0 && <CapTable title="Custom connectors" rows={custom} />}
        </>
      )}
    </AdminShell>
  );
}

function CapTable({ title, rows }: { title: string; rows: Connector[] }) {
  if (rows.length === 0) return null;
  return (
    <Card title={title} description="Declared capabilities per connector" bodyClassName="p-0">
      <div className="overflow-x-auto">
        <Table minWidth={760}>
          <THead>
            <TR hover={false}>
              <TH>Connector</TH>
              {CAP_COLS.map((c) => <TH key={c.key} align="center">{c.label}</TH>)}
            </TR>
          </THead>
          <TBody>
            {rows.map((c) => (
              <TR key={c.connector_type}>
                <TD>
                  <div className="flex items-center gap-2.5">
                    <span className="grid place-items-center h-7 w-7 rounded-md bg-app-2 text-ink-3 flex-shrink-0">
                      <Plug className="h-3.5 w-3.5" />
                    </span>
                    <div>
                      <div className="font-medium text-ink">{c.display_name}</div>
                      <div className="font-mono text-[10.5px] text-ink-4">{c.connector_type}</div>
                    </div>
                  </div>
                </TD>
                {CAP_COLS.map((col) => (
                  <TD key={col.key} align="center">
                    {c.capabilities?.[col.key]
                      ? <Check className="h-4 w-4 mx-auto text-[var(--con-ok)]" aria-label="yes" />
                      : <Minus className="h-3.5 w-3.5 mx-auto text-ink-5" aria-label="no" />}
                  </TD>
                ))}
              </TR>
            ))}
          </TBody>
        </Table>
      </div>
    </Card>
  );
}
