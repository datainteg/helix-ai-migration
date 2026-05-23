"use client";

import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function NewProjectPage() {
  const { token } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [migrationType, setMigrationType] = useState("database");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name, description, migration_type: migrationType }),
      });
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || "Failed to create project"); }
      const project = await res.json();
      router.push(`/projects/${project.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto mt-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Project</h1>
      {error && <div className="mb-4 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}
      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border bg-white p-6 shadow-sm">
        <div>
          <label className="block text-sm font-medium mb-1">Project Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required className="w-full rounded-lg border px-4 py-2 text-sm" placeholder="Oracle to Snowflake Migration" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="w-full rounded-lg border px-4 py-2 text-sm" rows={3} placeholder="Migrate CRM and billing data..." />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Migration Type</label>
          <select value={migrationType} onChange={(e) => setMigrationType(e.target.value)} className="w-full rounded-lg border px-4 py-2 text-sm">
            <option value="database">Database Migration</option>
            <option value="etl">ETL Migration</option>
            <option value="cloud">Cloud Migration</option>
            <option value="warehouse">Data Warehouse</option>
          </select>
        </div>
        <button type="submit" disabled={loading} className="w-full rounded-lg bg-helix-600 px-4 py-2 text-white font-medium hover:bg-helix-700 disabled:opacity-50">
          {loading ? "Creating..." : "Create Project"}
        </button>
      </form>
    </div>
  );
}
