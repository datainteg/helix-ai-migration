"use client";

/**
 * useProjectKey — resolve the project URL param (a readable slug OR a UUID) to
 * the canonical project.
 *
 * URLs are slug-based (/projects/<slug>/...). The backend's project-fetch
 * resolves slug-or-id, so we fetch once and expose:
 *   - `id`   : canonical UUID — use for ALL sub-endpoint calls.
 *   - `key`  : value for building sub-page links (the slug, so URLs stay readable).
 *   - `project`, `name`, `loading`, `error`, `reload`.
 *
 * No cross-render module cache: it would serve stale name/slug after a rename
 * and leak one user's project to another in the same tab. Each hook instance
 * fetches once on mount (cheap GET) and re-fetches when the param changes.
 */

import { useEffect, useState, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface ResolvedProject {
  id: string;          // canonical UUID (for API calls)
  key: string;         // slug if available, else id (for links)
  name: string;
  project: Record<string, unknown> | null;
  loading: boolean;
  error: string;
  reload: () => void;
}

export function useProjectKey(param: string | undefined): ResolvedProject {
  const p = param || "";
  const pathname = usePathname() || "";
  const router = useRouter();
  const [project, setProject] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (!p) return;
    setLoading(true); setError("");
    fetch(`${API_BASE}/api/v1/projects/${encodeURIComponent(p)}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? "Project not found" : `Failed (${r.status})`))))
      .then((data) => setProject(data))
      .catch((e) => { setProject(null); setError(e instanceof Error ? e.message : "Failed to load project"); })
      .finally(() => setLoading(false));
  }, [p]);

  // Re-resolve whenever the param changes.
  useEffect(() => { setProject(null); load(); }, [load]);

  const id = (project?.id as string) || "";
  const slug = (project?.slug as string) || "";

  // Canonicalize the URL to the slug — SEGMENT-AWARE: only rewrite the leading
  // `/projects/<param>` segment, never an arbitrary substring elsewhere in the
  // path (which could corrupt the path or loop). After the replace the route
  // param becomes the slug, so the condition stops firing.
  useEffect(() => {
    if (!slug || !p || p === slug) return;
    const from = `/projects/${p}`;
    if (pathname === from || pathname.startsWith(from + "/")) {
      router.replace(`/projects/${slug}` + pathname.slice(from.length));
    }
  }, [slug, p, pathname, router]);

  return {
    id,
    key: slug || id || p,
    name: (project?.name as string) || "",
    project,
    loading,
    error,
    reload: load,
  };
}
