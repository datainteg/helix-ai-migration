/**
 * @deprecated (M-017) — Use the `useApi()` hook from `@/lib/use-api` instead.
 *
 * This module predates the React-Query-integrated client and is no longer
 * imported anywhere in the app (verified). It is retained only so any stray
 * external reference keeps compiling. The two implementations have been kept
 * behaviourally identical (empty-body/204 guard + thrown Error on non-2xx);
 * the ONLY intentional difference is token sourcing — this client takes the
 * token as an explicit argument, whereas `useApi()` reads it from AuthContext.
 *
 * Do not add new call sites. New code should call `useApi()`.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// 204 No Content (and other empty bodies) would make res.json() throw
// "Unexpected end of JSON input". Guarded the same way as use-api.ts.
async function parseBody(res: Response) {
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined;
  }
  return res.json();
}

// Mirror use-api.ts's error envelope handling: prefer the API's `detail`
// message, fall back to the status code.
async function throwForStatus(res: Response): Promise<never> {
  const err = await res.json().catch(() => ({ detail: res.statusText }));
  throw new Error(err.detail || `HTTP ${res.status}`);
}

/** @deprecated Use `useApi().get` from `@/lib/use-api`. */
export async function apiGet(path: string, token?: string) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) return throwForStatus(res);
  return parseBody(res);
}

/** @deprecated Use `useApi().post` from `@/lib/use-api`. */
export async function apiPost(path: string, body: unknown, token?: string) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  });
  if (!res.ok) return throwForStatus(res);
  return parseBody(res);
}
