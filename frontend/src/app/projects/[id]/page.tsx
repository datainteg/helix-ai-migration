"use client";

import { useAuth } from "@/lib/auth-context";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
}

interface Requirement {
  id: string;
  source_text: string;
  created_at: string;
}

interface WorkflowResult {
  workflow_id: string;
  run_id: string;
  status: string;
  mode: string;
  result?: { outputs: Record<string, unknown>; approval_required: boolean };
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [project, setProject] = useState<Project | null>(null);
  const [requirement, setRequirement] = useState("");
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/v1/projects/${id}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : null)
      .then(setProject);
  }, [id, token]);

  const createRequirement = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/projects/${id}/requirements`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ source_text: requirement }),
      });
      if (!res.ok) throw new Error("Failed");
      const req = await res.json();
      setRequirements((r) => [...r, req]);
      setRequirement("");
    } catch {
      setError("Failed to create requirement");
    } finally {
      setLoading(false);
    }
  };

  const startWorkflow = async (reqId: string) => {
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/projects/${id}/agent-workflows`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ requirement_id: reqId, requirement_text: requirement || undefined }),
      });
      if (!res.ok) throw new Error("Failed");
      setWorkflow(await res.json());
    } catch {
      setError("Failed to start workflow");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/projects" className="text-sm text-helix-600 hover:underline">&larr; Projects</Link>
        <h1 className="text-2xl font-bold text-gray-900">{project?.name || "Project Workspace"}</h1>
      </div>

      {error && <div className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Requirement Intake */}
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h3 className="font-semibold mb-4">Migration Requirement</h3>
          <form onSubmit={createRequirement} className="space-y-3">
            <textarea
              value={requirement}
              onChange={(e) => setRequirement(e.target.value)}
              className="w-full rounded-lg border px-3 py-2 text-sm"
              rows={4}
              placeholder="Describe your migration requirement: source system, target system, business rules, validation expectations..."
              required
            />
            <button type="submit" disabled={loading} className="rounded-lg bg-helix-600 px-4 py-2 text-sm font-medium text-white hover:bg-helix-700 disabled:opacity-50">
              {loading ? "Saving..." : "Save Requirement"}
            </button>
          </form>

          {requirements.length > 0 && (
            <div className="mt-4 space-y-2">
              {requirements.map((r) => (
                <div key={r.id} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                  <span className="truncate flex-1">{r.source_text}</span>
                  <button onClick={() => startWorkflow(r.id)} className="ml-2 rounded bg-helix-600 px-3 py-1 text-xs text-white hover:bg-helix-700">
                    Generate Migration Plan
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Workflow Result */}
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h3 className="font-semibold mb-4">Agent Workflow</h3>
          {workflow ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-gray-500">Status:</span>
                <span className="font-medium text-green-700">{workflow.status}</span>
                <span className="text-xs text-gray-400">({workflow.mode})</span>
              </div>
              {workflow.result && (
                <>
                  <div className="text-sm">
                    <span className="text-gray-500">Approval Required:</span>{" "}
                    <span className={workflow.result.approval_required ? "text-amber-600 font-medium" : "text-green-600"}>
                      {workflow.result.approval_required ? "Yes" : "No"}
                    </span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-gray-500 uppercase">Agent Outputs</p>
                    {Object.entries(workflow.result.outputs).map(([agent, output]) => (
                      <div key={agent} className="rounded border px-3 py-2 text-xs">
                        <span className="font-medium text-helix-700">{agent}</span>
                        <p className="text-gray-600 mt-1">{(output as Record<string, string>).summary || JSON.stringify(output).slice(0, 120)}</p>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-500">Save a requirement and click "Generate Migration Plan" to start the BMAD workflow.</p>
          )}
        </div>
      </div>
    </div>
  );
}
