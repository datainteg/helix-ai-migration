"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";
import { Download, Search } from "lucide-react";
import { AdminShell } from "@/components/layout";
import { Card, Chip, LoadingState, EmptyState, Button, Avatar } from "@/components/ui";
import { formatDate, formatTime } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface AuditEntry {
  id: string;
  action: string;
  entity_type: string;
  created_at: string;
  actor?: string;
  status?: string;
}

export default function AuditLogsPage() {
  const { token } = useAuth();
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // SC-010: auth via the HttpOnly cookie (credentials:"include"); no token gate.
    fetch(`${API_BASE}/api/v1/audit-logs`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then(setLogs)
      .finally(() => setLoading(false));
  }, []);

  const actionLabel = (action: string) =>
    action.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <AdminShell
      title="Audit Logs"
      subtitle="Security and activity events across the platform, with full attribution."
      actions={<Button variant="outline"><Download className="h-4 w-4" /> Export CSV</Button>}
    >
      <Card padding="sm">
        <div className="flex flex-wrap gap-2 items-center">
          <label className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-4" />
            <input
              placeholder="Search events…"
              className="w-full h-9 rounded-[8px] bg-app-2 border border-hx pl-9 pr-3 text-[13px] focus-ring"
            />
          </label>
          {["All", "Success", "Failed", "Auth", "Workflow", "Provider"].map((s, i) => (
            <button
              key={s}
              className={`px-3 h-9 rounded-[8px] text-[12.5px] border ${i === 0 ? "bg-[var(--con-brand-soft)] text-[var(--con-brand)] border-hx-2" : "bg-surface text-ink-3 border-hx hover:bg-surface-hi"}`}
            >
              {s}
            </button>
          ))}
        </div>
      </Card>

      {loading ? (
        <LoadingState label="Loading audit logs…" />
      ) : logs.length === 0 ? (
        <EmptyState title="No audit logs yet" description="Logs track login events, admin changes, provider modifications, and workflow approvals." />
      ) : (
        <Card bodyClassName="p-0">
          <table className="w-full text-[13px] border-t border-hx">
            <thead className="bg-surface-hi text-[10.5px] uppercase tracking-[0.08em] text-ink-4 font-mono">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Timestamp</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Actor</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Action</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Resource</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Status</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-hx last:border-b-0 hover:bg-surface-hi">
                  <td className="px-4 py-3 font-mono text-[12px] text-ink-3">{formatDate(log.created_at)} · {formatTime(log.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Avatar name={log.actor || "System"} size={20} />
                      <span className="text-ink-2">{log.actor || "System"}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-medium text-ink">{actionLabel(log.action)}</td>
                  <td className="px-4 py-3"><Chip tone="default" mono>{log.entity_type}</Chip></td>
                  <td className="px-4 py-3">
                    <Chip tone={log.status === "failed" ? "err" : "ok"} dot>{log.status || "success"}</Chip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </AdminShell>
  );
}
