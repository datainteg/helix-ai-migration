"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";
import { HeartPulse, RefreshCcw } from "lucide-react";
import { AdminShell } from "@/components/layout";
import { Card, MetricCard, StatusBadge, Button, LoadingState } from "@/components/ui";


const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface ComponentStatus {
  component: string;
  status: string;
  latency_ms?: number;
  detail?: string;
}

export default function SystemHealthPage() {
  const { token } = useAuth();
  const [components, setComponents] = useState<ComponentStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // SC-010: auth via the HttpOnly cookie (credentials:"include"); no token gate.
    fetch(`${API_BASE}/api/v1/system/health`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (data?.components) setComponents(data.components); })
      .finally(() => setLoading(false));
  }, []);

  const data: ComponentStatus[] = components;

  const healthy = data.filter((c) => c.status === "healthy").length;
  const issues = data.length - healthy;

  return (
    <AdminShell
      title="System Health"
      page="System Health"
      subtitle="Live status of backend, database, queue, worker, and connector components."
      actions={<Button variant="outline"><RefreshCcw className="h-4 w-4" /> Refresh</Button>}
    >
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <MetricCard label="COMPONENTS" value={data.length} />
        <MetricCard label="HEALTHY" value={healthy} accent="var(--con-ok)" />
        <MetricCard label="ISSUES" value={issues} accent={issues > 0 ? "var(--con-err)" : "var(--con-ok)"} />
        <MetricCard label="OVERALL" value={issues > 0 ? "Degraded" : "OK"} accent={issues > 0 ? "var(--con-warn)" : "var(--con-ok)"} />
      </div>

      {loading ? (
        <LoadingState label="Checking system health…" />
      ) : (
        <Card bodyClassName="p-0">
          <div className="overflow-x-auto table-scroll">
          <table className="w-full text-[13px] border-t border-hx">
            <thead className="bg-surface-hi text-[10.5px] uppercase tracking-[0.08em] text-ink-4 font-mono">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Component</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Detail</th>
                <th className="px-4 py-2.5 text-right font-medium border-b border-hx">Latency</th>
                <th className="px-4 py-2.5 text-left font-medium border-b border-hx">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((c) => (
                <tr key={c.component} className="border-b border-hx last:border-b-0 hover:bg-surface-hi">
                  <td className="px-4 py-3 font-medium text-ink capitalize">
                    <span className="inline-flex items-center gap-2">
                      <HeartPulse className="h-3.5 w-3.5 text-[var(--con-brand)]" />
                      {c.component.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-ink-3 text-[12.5px]">{c.detail || "—"}</td>
                  <td className="px-4 py-3 text-right font-mono text-[12px] text-ink-2">{c.latency_ms ? `${c.latency_ms}ms` : "—"}</td>
                  <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
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
