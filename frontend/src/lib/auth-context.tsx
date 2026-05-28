"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

interface AuthState {
  /** SC-010: the JWT now lives in an HttpOnly cookie that JS cannot read, so
   * this is NO LONGER the real token — it is a non-secret in-memory presence
   * hint (`"cookie-session"` when authenticated, `null` otherwise) derived from
   * `user`. Many existing call sites gate work on `if (!token)`; keeping a
   * truthy hint preserves that "is logged in" semantic. Auth itself rides on
   * the cookie via `credentials: "include"` on every request — this value is
   * NEVER put into an Authorization header anymore. */
  token: string | null;
  user: { email: string; name: string } | null;
  login: (email: string, password: string) => Promise<void>;
  setupFirstAdmin: (data: FirstAdminData) => Promise<void>;
  /** Re-sync the user from the server after an out-of-band auth step (e.g. the
   * multi-step setup wizard). The cookie is already set by the backend; this
   * just repopulates `user`. Does NOT redirect; caller controls flow. */
  setSession: (token?: string | null, user?: { email: string; name: string } | null) => void;
  logout: () => void;
  loading: boolean;
}

interface FirstAdminData {
  email: string;
  name: string;
  password: string;
  organization_name: string;
  organization_slug: string;
}

const AuthContext = createContext<AuthState | null>(null);
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<{ email: string; name: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // SC-010: the auth token lives in an HttpOnly cookie that JS can't read, so
  // we can no longer gate on localStorage. Authentication state is derived from
  // the server: call /auth/me WITH credentials so the cookie is sent; a 200
  // means we're logged in, anything else means we're not.
  const refreshUser = async (): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setUser({ email: data.email, name: data.name });
        return true;
      }
    } catch {
      /* network error — treat as unauthenticated */
    }
    setUser(null);
    return false;
  };

  useEffect(() => {
    void refreshUser().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loginFn = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      credentials: "include", // receive + store the HttpOnly cookie
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Login failed");
    }
    // The backend has set the HttpOnly cookie. Populate `user` from /auth/me
    // (cookie auth) so the UI shows the real name, not email.split("@")[0].
    const ok = await refreshUser();
    if (!ok) setUser({ email, name: email.split("@")[0] });
    router.push("/dashboard");
  };

  const setupFirstAdmin = async (formData: FirstAdminData) => {
    const res = await fetch(`${API_BASE}/api/v1/auth/first-admin`, {
      method: "POST",
      credentials: "include", // receive + store the HttpOnly cookie
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Setup failed");
    }
    const ok = await refreshUser();
    if (!ok) setUser({ email: formData.email, name: formData.name });
    router.push("/dashboard");
  };

  const logout = () => {
    // SC-010: POST /auth/logout WITH credentials so the backend revokes the
    // token AND clears the HttpOnly cookie. Fire-and-forget — clear local user
    // state regardless of the network result so logout always feels instant.
    void fetch(`${API_BASE}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => {
      /* best-effort: cookie expires at the JWT TTL even if this fails */
    });
    setUser(null);
    router.push("/login");
  };

  const setSession = (_token?: string | null, newUser?: { email: string; name: string } | null) => {
    // SC-010: the cookie is already set by the backend; we only need to refresh
    // local user state. `_token` is accepted for backward call-site compat but
    // ignored (JS can't persist the HttpOnly cookie anyway).
    if (newUser !== undefined) {
      setUser(newUser);
    } else {
      void refreshUser();
    }
  };

  // SC-010: non-secret presence hint so legacy `if (!token)` gates still work.
  // The real JWT is in the HttpOnly cookie; this is never sent as a header.
  const token = user ? "cookie-session" : null;

  return (
    <AuthContext.Provider value={{ token, user, login: loginFn, setupFirstAdmin, setSession, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
