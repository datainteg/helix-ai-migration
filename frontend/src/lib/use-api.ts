"use client";

import { useAuth } from "./auth-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ApiClient {
  get: <T>(path: string) => Promise<T>;
  post: <T>(path: string, body?: unknown) => Promise<T>;
  upload: <T>(path: string, formData: FormData) => Promise<T>;
}

/**
 * Shared API client hook — eliminates repeated fetch boilerplate across pages.
 * Automatically includes JWT token from AuthContext.
 */
export function useApi(): ApiClient {
  const { token } = useAuth();

  const authHeaders = (extra?: Record<string, string>) => ({
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  });

  const handleResponse = async <T>(res: Response): Promise<T> => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    // 204 No Content (e.g. DELETE) has an empty body — calling .json() would
    // throw "Unexpected end of JSON input". Return undefined for empty bodies.
    if (res.status === 204 || res.headers.get("content-length") === "0") {
      return undefined as T;
    }
    return res.json();
  };

  return {
    get: <T>(path: string) =>
      fetch(`${API_BASE}${path}`, { headers: authHeaders() }).then(handleResponse<T>),

    post: <T>(path: string, body?: unknown) =>
      fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: body ? JSON.stringify(body) : undefined,
      }).then(handleResponse<T>),

    upload: <T>(path: string, formData: FormData) =>
      fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      }).then(handleResponse<T>),
  };
}
