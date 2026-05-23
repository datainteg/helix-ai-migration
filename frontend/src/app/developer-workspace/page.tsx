"use client";

import { useAuth } from "@/lib/auth-context";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

interface Artifact {
  id: string;
  filename: string;
  file_type: string;
  content_hash: string;
  storage_path: string;
  created_at: string;
}

export default function DeveloperWorkspacePage() {
  const { token } = useAuth();
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [selectedProject, setSelectedProject] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    fetch(`${API}/api/v1/projects`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : [])
      .then((projects: { id: string; name: string }[]) => {
        if (projects.length > 0 && !selectedProject) {
          setSelectedProject(projects[0].id);
        }
      });
    setLoading(false);
  }, [token]);

  const fetchArtifacts = async (projectId: string) => {
    if (!projectId || !token) return;
    try {
      const res = await fetch(`${API}/api/v1/projects/${projectId}/artifacts`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setArtifacts(await res.json());
    } catch { /* ignore */ }
  };

  useEffect(() => {
    if (selectedProject) fetchArtifacts(selectedProject);
  }, [selectedProject, token]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !selectedProject) return;

    const ext = file.name.split(".").pop()?.toLowerCase();
    if (ext !== "py" && ext !== "sql") {
      setError("Only .py and .sql files are supported.");
      return;
    }

    setError("");
    setSuccess("");
    setUploading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API}/api/v1/projects/${selectedProject}/artifacts/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail); }
      setSuccess(`Uploaded: ${file.name}`);
      if (fileRef.current) fileRef.current.value = "";
      fetchArtifacts(selectedProject);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Developer Workspace</h1>
          <p className="text-sm text-gray-500 mt-1">
            ⚠️ Generated code and notebook drafts must be reviewed and approved before production use.
          </p>
        </div>
        <Link href="/projects" className="text-sm text-helix-600 hover:underline">View Projects</Link>
      </div>

      {error && <div className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}
      {success && <div className="rounded-lg bg-green-50 px-4 py-2 text-sm text-green-700">{success}</div>}

      {/* Upload Form */}
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <h3 className="font-semibold mb-4">Upload Artifact</h3>
        <form onSubmit={handleUpload} className="flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-700 mb-1">Select Project</label>
            <select
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
              className="w-full rounded-lg border px-3 py-2 text-sm"
            >
              <option value="">Select a project...</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-700 mb-1">File (.py or .sql)</label>
            <input ref={fileRef} type="file" accept=".py,.sql" className="w-full rounded-lg border px-3 py-2 text-sm" required />
          </div>
          <button type="submit" disabled={uploading || !selectedProject} className="rounded-lg bg-helix-600 px-6 py-2 text-sm font-medium text-white hover:bg-helix-700 disabled:opacity-50">
            {uploading ? "Uploading..." : "Upload"}
          </button>
        </form>
      </div>

      {/* Artifact List */}
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <h3 className="font-semibold mb-4">Artifacts ({artifacts.length})</h3>
        {loading ? (
          <p className="text-sm text-gray-500">Loading artifacts...</p>
        ) : artifacts.length === 0 ? (
          <p className="text-sm text-gray-500">No artifacts uploaded yet. Upload a .py or .sql file above.</p>
        ) : (
          <div className="space-y-2">
            {artifacts.map((a) => (
              <div key={a.id} className="flex items-center justify-between rounded-lg border px-4 py-3 text-sm">
                <div>
                  <span className="font-medium">{a.filename}</span>
                  <span className="ml-2 text-xs text-gray-400">.{a.file_type}</span>
                  <span className="ml-2 text-xs text-gray-400">SHA256: {a.content_hash.slice(0, 12)}...</span>
                </div>
                <div className="flex items-center gap-2">
                  <Link href={`/developer-workspace/${a.id}`} className="text-xs text-helix-600 hover:underline">
                    View & Review
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
