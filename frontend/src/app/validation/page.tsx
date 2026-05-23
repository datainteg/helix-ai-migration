"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";

interface ValidationCheck {
  name: string;
  status: string;
  count: number;
}

export default function ValidationCenterPage() {
  const { token } = useAuth();
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [checks] = useState<ValidationCheck[]>([
    { name: "Schema Compatibility", status: "passed", count: 12 },
    { name: "Row Count Comparison", status: "passed", count: 4 },
    { name: "Null Detection", status: "warning", count: 3 },
    { name: "Duplicate Check", status: "passed", count: 0 },
    { name: "Business Rule Validation", status: "pending", count: 0 },
  ]);

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/v1/projects`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : [])
      .then(setProjects);
  }, [token]);

  const statusClass = (s: string) =>
    s === "passed" ? "text-green-700 bg-green-50" : s === "warning" ? "text-amber-700 bg-amber-50" : "text-gray-500 bg-gray-50";

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Validation Center</h1>

      <div className="flex items-center gap-4">
        <label className="text-sm font-medium text-gray-700">Project:</label>
        <select
          value={selectedProject}
          onChange={(e) => setSelectedProject(e.target.value)}
          className="rounded-lg border px-3 py-2 text-sm"
        >
          <option value="">Select a project...</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>

      {selectedProject ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-xl border bg-white p-4 shadow-sm">
              <p className="text-xs text-gray-500">Total Checks</p>
              <p className="text-2xl font-bold text-helix-600">{checks.length}</p>
            </div>
            <div className="rounded-xl border bg-white p-4 shadow-sm">
              <p className="text-xs text-gray-500">Passed</p>
              <p className="text-2xl font-bold text-green-600">{checks.filter((c) => c.status === "passed").length}</p>
            </div>
            <div className="rounded-xl border bg-white p-4 shadow-sm">
              <p className="text-xs text-gray-500">Warnings</p>
              <p className="text-2xl font-bold text-amber-600">{checks.filter((c) => c.status === "warning").length}</p>
            </div>
          </div>

          <div className="rounded-xl border bg-white shadow-sm">
            <div className="p-4 border-b">
              <h3 className="font-semibold">Validation Run Summary</h3>
            </div>
            <div className="divide-y">
              {checks.map((check) => (
                <div key={check.name} className="flex items-center justify-between px-4 py-3 text-sm">
                  <span className="font-medium">{check.name}</span>
                  <div className="flex items-center gap-3">
                    {check.count > 0 && <span className="text-xs text-gray-500">{check.count} issues</span>}
                    <span className={`text-xs px-2 py-0.5 rounded ${statusClass(check.status)}`}>{check.status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border bg-white p-12 shadow-sm text-center text-gray-500">
          Select a project to view validation results.
        </div>
      )}
    </div>
  );
}
