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
  // SC-010: auth now rides on the HttpOnly `helix_token` cookie sent via
  // `credentials: "include"`, not an Authorization header. We no longer read a
  // token from the context (JS cannot read the cookie).
  useAuth(); // keep the provider dependency / re-render on auth change

  const authHeaders = (extra?: Record<string, string>) => ({
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
      fetch(`${API_BASE}${path}`, { credentials: "include", headers: authHeaders() }).then(handleResponse<T>),

    post: <T>(path: string, body?: unknown) =>
      fetch(`${API_BASE}${path}`, {
        method: "POST",
        credentials: "include",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: body ? JSON.stringify(body) : undefined,
      }).then(handleResponse<T>),

    upload: <T>(path: string, formData: FormData) =>
      fetch(`${API_BASE}${path}`, {
        method: "POST",
        credentials: "include",
        headers: authHeaders(),
        body: formData,
      }).then(handleResponse<T>),
  };
}
