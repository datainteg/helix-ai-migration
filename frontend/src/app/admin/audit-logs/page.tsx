"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useMemo, useState } from "react";
import { Download, Search } from "lucide-react";
import { AdminShell } from "@/components/layout";
import { Card, Chip, LoadingState, EmptyState, Button, Avatar } from "@/components/ui";
import { formatDate, formatTime } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface AuditEntry {
  id: string;
  action: string;
  entity_type: string;
  entity_id?: string;
  actor_id?: string;
  ip_address?: string;
  created_at: string;
}

// Map an action to a coarse category for the filter pills.
function category(action: string): string {
  const a = action.toLowerCase();
  if (a.includes("login") || a.includes("logout") || a.includes("auth") || a.includes("password")) return "Auth";
  if (a.includes("workflow") || a.includes("approval") || a.includes("migration")) return "Workflow";
  if (a.includes("provider") || a.includes("llm") || a.includes("agent") || a.includes("cost") || a.includes("budget")) return "Provider";
  if (a.includes("role") || a.includes("user") || a.includes("member") || a.includes("invitation")) return "Access";
  return "Other";
}
const FILTERS = ["All", "Auth", "Access", "Workflow", "Provider", "Other"];

async function downloadCsv() {
  const res = await fetch(`${API_BASE}/api/v1/audit-logs/export/csv`, { credentials: "include" });
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "helix-audit-logs.csv";
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

export default function AuditLogsPage() {
  const { token } = useAuth();
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("All");

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/audit-logs?limit=500`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setLogs(Array.isArray(d) ? d : []))
      .finally(() => setLoading(false));
  }, []);

  const actionLabel = (action: string) =>
    action.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const actorLabel = (a?: string) => (a ? `${a.slice(0, 8)}…` : "System");

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return logs.filter((l) => {
      if (filter !== "All" && category(l.action) !== filter) return false;
      if (s && !`${l.action} ${l.entity_type} ${l.entity_id ?? ""} ${l.actor_id ?? ""}`.toLowerCase().includes(s)) return false;
      return true;
    });
  }, [logs, q, filter]);

  return (
    <AdminShell
      title="Audit Logs"
      page="Audit Logs"
      subtitle="Security and activity events across the platform, with full attribution."
      actions={<Button variant="outline" onClick={() => void downloadCsv()}><Download className="h-4 w-4" /> Export CSV</Button>}
    >
      <Card padding="sm">
        <div className="flex flex-wrap gap-2 items-center">
          <label className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-4" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search events…"
              className="w-full h-9 rounded-[8px] bg-app-2 border border-hx pl-9 pr-3 text-[13px] focus-ring"
            />
          </label>
          {FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 h-9 rounded-[8px] text-[12.5px] border ${filter === s ? "bg-[var(--con-brand-soft)] text-[var(--con-brand)] border-hx-2" : "bg-surface text-ink-3 border-hx hover:bg-surface-hi"}`}
            >
              {s}
            </button>
          ))}
        </div>
      </Card>

      {loading ? (
        <LoadingState label="Loading audit logs…" />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={logs.length === 0 ? "No audit logs yet" : "No matching events"}
          description={logs.length === 0 ? "Logs track login events, admin changes, provider modifications, and workflow approvals." : "Try a different search or filter."}
        />
      ) : (
        <Card bodyClassName="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-[13px] border-t border-hx">
              <thead className="bg-surface-hi text-[10.5px] uppercase tracking-[0.08em] text-ink-4 font-mono">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Timestamp</th>
                  <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Actor</th>
                  <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Action</th>
                  <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Resource</th>
                  <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Category</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((log) => (
                  <tr key={log.id} className="border-b border-hx last:border-b-0 hover:bg-surface-hi">
                    <td className="px-4 py-3 font-mono text-[12px] text-ink-3 whitespace-nowrap">{formatDate(log.created_at)} · {formatTime(log.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Avatar name={log.actor_id || "System"} size={20} />
                        <span className="text-ink-2 font-mono text-[12px]" title={log.actor_id}>{actorLabel(log.actor_id)}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-medium text-ink">{actionLabel(log.action)}</td>
                    <td className="px-4 py-3"><Chip tone="default" mono>{log.entity_type}</Chip></td>
                    <td className="px-4 py-3"><Chip tone="default">{category(log.action)}</Chip></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </AdminShell>
  );
}
