"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

interface AuthState {
  token: string | null;
  user: { email: string; name: string } | null;
  login: (email: string, password: string) => Promise<void>;
  setupFirstAdmin: (data: FirstAdminData) => Promise<void>;
  /** Apply a token captured outside the helper (e.g. multi-step wizard
   * persisting via direct API calls). Does NOT redirect; caller controls flow. */
  setSession: (token: string, user?: { email: string; name: string } | null) => void;
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
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<{ email: string; name: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const stored = localStorage.getItem("helix_token");
    if (stored) {
      setToken(stored);
      fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${stored}` },
      })
        .then((r) => r.ok ? r.json() : null)
        .then((data) => {
          if (data) setUser({ email: data.email, name: data.name });
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  // L-011: propagate token changes across tabs. The `storage` event fires in
  // OTHER tabs when localStorage["helix_token"] is written/removed, so logging
  // in or out in one tab updates the rest without a manual refresh.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== "helix_token") return;
      const next = e.newValue;
      if (!next) {
        // Logged out elsewhere — clear local session.
        setToken(null);
        setUser(null);
        return;
      }
      if (next === token) return; // no-op (we triggered it)
      setToken(next);
      fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${next}` },
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data) setUser({ email: data.email, name: data.name });
        })
        .catch(() => {
          /* best-effort; token still set so requests can proceed */
        });
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [token]);

  const loginFn = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    localStorage.setItem("helix_token", data.access_token);
    setToken(data.access_token);
    // Fetch the real user record so the UI does not fall back to
    // email.split("@")[0] (the placeholder used until /auth/me responds).
    try {
      const meRes = await fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (meRes.ok) {
        const me = await meRes.json();
        setUser({ email: me.email, name: me.name });
      } else {
        setUser({ email, name: email.split("@")[0] });
      }
    } catch {
      setUser({ email, name: email.split("@")[0] });
    }
    router.push("/dashboard");
  };

  const setupFirstAdmin = async (formData: FirstAdminData) => {
    const res = await fetch(`${API_BASE}/api/v1/auth/first-admin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Setup failed");
    }
    const data = await res.json();
    localStorage.setItem("helix_token", data.access_token);
    setToken(data.access_token);
    setUser({ email: formData.email, name: formData.name });
    router.push("/dashboard");
  };

  const logout = () => {
    // SC-010: revoke the token server-side so a copy stolen via XSS cannot
    // outlive the session. Fire-and-forget — clear local state regardless of
    // the network result so logout always feels instant and never blocks.
    const stored = token ?? localStorage.getItem("helix_token");
    if (stored) {
      void fetch(`${API_BASE}/api/v1/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${stored}` },
      }).catch(() => {
        /* best-effort: token still expires at JWT TTL */
      });
    }
    localStorage.removeItem("helix_token");
    setToken(null);
    setUser(null);
    router.push("/login");
  };

  const setSession = (newToken: string, newUser?: { email: string; name: string } | null) => {
    try { localStorage.setItem("helix_token", newToken); } catch { /* SSR safe */ }
    setToken(newToken);
    if (newUser !== undefined) setUser(newUser);
  };

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
