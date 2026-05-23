"use client";

import { useAuth } from "@/lib/auth-context";
import Link from "next/link";
import { useEffect, useState } from "react";

interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
}

export default function ProjectsPage() {
  const { token } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    fetch(`${API}/api/v1/projects`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : [])
      .then(setProjects)
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <Link href="/projects/new" className="rounded-lg bg-helix-600 px-4 py-2 text-sm font-medium text-white hover:bg-helix-700">
          New Project
        </Link>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading projects...</div>
      ) : projects.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 shadow-sm text-center">
          <p className="text-gray-500">No projects yet. Create your first migration project.</p>
          <Link href="/projects/new" className="mt-4 inline-block text-helix-600 hover:underline text-sm">Create Project</Link>
        </div>
      ) : (
        <div className="space-y-3">
          {projects.map((p) => (
            <Link key={p.id} href={`/projects/${p.id}`} className="block rounded-xl border bg-white p-4 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">{p.name}</p>
                  <p className="text-xs text-gray-500">{p.description || "No description"}</p>
                </div>
                <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">{p.status}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
