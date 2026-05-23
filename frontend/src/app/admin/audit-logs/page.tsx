"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";

interface AuditEntry {
  id: string;
  action: string;
  entity_type: string;
  created_at: string;
}

export default function AuditLogsPage() {
  const { token } = useAuth();
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    fetch(`${API}/api/v1/audit-logs`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setLogs)
      .finally(() => setLoading(false));
  }, [token]);

  const actionLabel = (action: string) =>
    action.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading audit logs...</div>
      ) : logs.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 shadow-sm text-center text-gray-500">
          No audit logs yet. Logs track login events, admin changes, provider modifications, and workflow approvals.
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm">
          <div className="divide-y">
            {logs.map((log) => (
              <div key={log.id} className="flex items-center justify-between px-4 py-3 text-sm">
                <div>
                  <span className="font-medium">{actionLabel(log.action)}</span>
                  <span className="ml-2 text-xs text-gray-400">{log.entity_type}</span>
                </div>
                <span className="text-xs text-gray-500">{new Date(log.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
