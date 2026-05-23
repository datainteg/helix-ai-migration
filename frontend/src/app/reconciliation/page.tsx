"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ReconSummary {
  source_count: number;
  target_count: number;
  matched_count: number;
  mismatched_count: number;
  missing_count: number;
  extra_count: number;
  recon_score: number;
}

const DEMO_RECON: ReconSummary = {
  source_count: 10420,
  target_count: 10398,
  matched_count: 10350,
  mismatched_count: 48,
  missing_count: 22,
  extra_count: 0,
  recon_score: 0.994,
};

export default function ReconciliationPage() {
  const { token } = useAuth();
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [recon] = useState<ReconSummary>(DEMO_RECON);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/v1/projects`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : [])
      .then(setProjects);
  }, [token]);

  const pct = (n: number, total: number) => total ? ((n / total) * 100).toFixed(2) : "0";

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Reconciliation Dashboard</h1>

      <div className="flex items-center gap-4">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Project:</label>
        <select
          value={selectedProject}
          onChange={(e) => setSelectedProject(e.target.value)}
          className="rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm"
        >
          <option value="">Select a project...</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>

      {selectedProject ? (
        <div className="space-y-4">
          <div className="rounded-xl border dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm text-center">
            <p className="text-sm text-gray-500 dark:text-gray-400">Reconciliation Score</p>
            <p className={`text-4xl font-bold ${recon.recon_score >= 0.99 ? "text-green-600" : recon.recon_score >= 0.95 ? "text-amber-600" : "text-red-600"}`}>
              {(recon.recon_score * 100).toFixed(1)}%
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {[
              { label: "Source Records", value: recon.source_count, color: "text-gray-700 dark:text-gray-200" },
              { label: "Target Records", value: recon.target_count, color: "text-gray-700 dark:text-gray-200" },
              { label: "Matched", value: recon.matched_count, color: "text-green-600", pct: pct(recon.matched_count, recon.source_count) },
              { label: "Mismatched", value: recon.mismatched_count, color: recon.mismatched_count > 0 ? "text-red-600" : "text-green-600", pct: pct(recon.mismatched_count, recon.source_count) },
              { label: "Missing (Source)", value: recon.missing_count, color: recon.missing_count > 0 ? "text-amber-600" : "text-green-600", pct: pct(recon.missing_count, recon.source_count) },
              { label: "Extra (Target)", value: recon.extra_count, color: recon.extra_count > 0 ? "text-amber-600" : "text-green-600", pct: pct(recon.extra_count, recon.target_count) },
            ].map((m) => (
              <div key={m.label} className="rounded-xl border dark:border-gray-800 bg-white dark:bg-gray-900 p-4 shadow-sm">
                <p className="text-xs text-gray-500 dark:text-gray-400">{m.label}</p>
                <p className={`text-2xl font-bold ${m.color}`}>{m.value.toLocaleString()}</p>
                {"pct" in m && <p className="text-xs text-gray-400 dark:text-gray-500">{m.pct}%</p>}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-xl border dark:border-gray-800 bg-white dark:bg-gray-900 p-12 shadow-sm text-center text-gray-500 dark:text-gray-400">
          Select a project to view reconciliation results.
        </div>
      )}
    </div>
  );
}
