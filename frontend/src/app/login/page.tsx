"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { HelixLogo } from "@/components/layout/HelixLogo";
import { Button, ErrorBanner } from "@/components/ui";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-app">
      <div className="hidden lg:flex flex-col justify-between bg-indigo-cyan text-white p-12 relative overflow-hidden">
        <div className="absolute inset-0 hx-grid-bg opacity-10 pointer-events-none" />
        <Link href="/" className="relative z-10 inline-flex items-center gap-2.5 text-white">
          <HelixLogo size={32} />
          <span className="font-semibold text-[17px] tracking-tight">Helix Migration</span>
        </Link>
        <div className="relative z-10 max-w-md">
          <p className="text-[13px] font-medium uppercase tracking-wider text-white/70">Open-source · Self-hosted</p>
          <h1 className="mt-3 text-[34px] font-semibold tracking-tight leading-tight">
            Sign in to your migration command center.
          </h1>
          <p className="mt-4 text-white/80 text-[14px] leading-relaxed">
            Multi-agent workflows. Real-time validation & recon. Developer-grade audit trail.
          </p>
        </div>
        <div className="relative z-10 text-[12px] text-white/70">© 2026 Helix Migration · Apache 2.0</div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm">
          <div className="lg:hidden mb-6">
            <Link href="/" className="inline-flex items-center gap-2.5">
              <HelixLogo size={28} />
              <span className="font-semibold text-[16px] tracking-tight text-ink">Helix Migration</span>
            </Link>
          </div>

          <h2 className="text-[24px] font-semibold tracking-tight text-ink">Welcome back</h2>
          <p className="text-[13.5px] text-ink-3 mt-1">Sign in to continue to your migrations.</p>

          {error && <div className="mt-5"><ErrorBanner message={error} onDismiss={() => setError("")} /></div>}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="email" className="block text-[12.5px] font-medium text-ink-2 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="admin@example.com"
                className="w-full h-10 rounded-lg border border-hx bg-surface px-3.5 text-[13.5px] focus-ring"
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="password" className="block text-[12.5px] font-medium text-ink-2">
                  Password
                </label>
                <Link href="#" className="text-[12px] text-helix-600 hover:underline">
                  Forgot?
                </Link>
              </div>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                className="w-full h-10 rounded-lg border border-hx bg-surface px-3.5 text-[13.5px] focus-ring"
              />
            </div>
            <Button type="submit" loading={loading} className="w-full !h-11">
              Sign In
            </Button>
          </form>

          <p className="mt-6 text-[12.5px] text-ink-3 text-center">
            New to Helix?{" "}
            <Link href="/setup/first-admin" className="text-helix-600 hover:underline font-medium">
              First-admin setup
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
