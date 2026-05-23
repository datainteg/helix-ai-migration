"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";

interface ComponentStatus {
  component: string;
  status: string;
}

export default function SystemHealthPage() {
  const { token } = useAuth();
  const [components, setComponents] = useState<ComponentStatus[]>([]);
  const [loading, setLoading] = useState(true);

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    fetch(`${API}/api/v1/system/health`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.components) setComponents(data.components);
      })
      .finally(() => setLoading(false));
  }, [token]);

  const statusStyle = (s: string) =>
    s === "healthy" ? "bg-green-100 text-green-700" :
    s === "degraded" || s === "down" ? "bg-red-100 text-red-700" :
    "bg-gray-100 text-gray-600";

  const healthyCount = components.filter((c) => c.status === "healthy").length;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">System Health</h1>

      {loading ? (
        <div className="text-center py-12 text-gray-500">Checking system health...</div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-xl border bg-white p-4 shadow-sm text-center">
              <p className="text-xs text-gray-500">Components</p>
              <p className="text-2xl font-bold text-gray-700">{components.length}</p>
            </div>
            <div className="rounded-xl border bg-white p-4 shadow-sm text-center">
              <p className="text-xs text-gray-500">Healthy</p>
              <p className="text-2xl font-bold text-green-600">{healthyCount}</p>
            </div>
            <div className="rounded-xl border bg-white p-4 shadow-sm text-center">
              <p className="text-xs text-gray-500">Issues</p>
              <p className={`text-2xl font-bold ${components.length - healthyCount > 0 ? "text-red-600" : "text-green-600"}`}>
                {components.length - healthyCount}
              </p>
            </div>
          </div>

          <div className="rounded-xl border bg-white shadow-sm">
            <div className="divide-y">
              {components.map((c) => (
                <div key={c.component} className="flex items-center justify-between px-4 py-3">
                  <span className="text-sm font-medium capitalize">{c.component.replace(/_/g, " ")}</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusStyle(c.status)}`}>{c.status}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
