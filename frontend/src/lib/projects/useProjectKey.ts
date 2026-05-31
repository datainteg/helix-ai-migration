"use client";

/**
 * useProjectKey — resolve the project URL param (which may be a readable slug
 * OR a UUID) to the canonical project.
 *
 * URLs are slug-based (/projects/<slug>/...). The backend's project-fetch
 * resolves slug-or-id, so we fetch once and expose:
 *   - `id`   : the canonical UUID — use this for ALL sub-endpoint calls
 *              (/projects/{id}/requirements, etc.) which key on the real id.
 *   - `key`  : the value to use when building sub-page links (prefer the slug
 *              so navigation keeps readable URLs).
 *   - `project`, `name`, `loading`, `error`, `reload`.
 *
 * Cached per param across the session so sibling pages don't re-fetch.
 */

import { useEffect, useState, useCallback } from "react";

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

const _cache = new Map<string, any>();

export function useProjectKey(param: string | undefined): ResolvedProject {
  const p = param || "";
  const cached = _cache.get(p);
  const [project, setProject] = useState<Record<string, unknown> | null>(cached ?? null);
  const [loading, setLoading] = useState(!cached);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (!p) return;
    setLoading(true); setError("");
    fetch(`${API_BASE}/api/v1/projects/${p}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? "Project not found" : `Failed (${r.status})`))))
      .then((data) => { _cache.set(p, data); setProject(data); })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load project"))
      .finally(() => setLoading(false));
  }, [p]);

  useEffect(() => { if (!cached) load(); /* eslint-disable-next-line */ }, [p]);

  const id = (project?.id as string) || "";
  const slug = (project?.slug as string) || "";
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
