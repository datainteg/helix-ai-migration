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

const _cache = new Map<string, any>();

export function useProjectKey(param: string | undefined): ResolvedProject {
  const p = param || "";
  const pathname = usePathname() || "";
  const router = useRouter();
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

  // Canonicalize the URL to the slug: if the user arrived via the UUID (or an
  // old slug) and a slug exists, rewrite the path so the address bar + all
  // in-page links use the readable slug.
  useEffect(() => {
    if (slug && p && p !== slug && pathname.includes(p)) {
      router.replace(pathname.replace(p, slug));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, p, pathname]);
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
