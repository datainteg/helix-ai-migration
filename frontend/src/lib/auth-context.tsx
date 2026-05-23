"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

interface AuthState {
  token: string | null;
  user: { email: string; name: string } | null;
  login: (email: string, password: string) => Promise<void>;
  setupFirstAdmin: (data: FirstAdminData) => Promise<void>;
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
    setUser({ email, name: email.split("@")[0] });
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
    localStorage.removeItem("helix_token");
    setToken(null);
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ token, user, login: loginFn, setupFirstAdmin, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
