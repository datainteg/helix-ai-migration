"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { HelixLogo } from "@/components/layout/HelixLogo";

export default function LoginPage() {
  const { login, demoLogin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const demoEnabled = process.env.NEXT_PUBLIC_DEMO_ENABLED === "true";

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

  const handleDemo = async () => {
    setError("");
    setDemoLoading(true);
    try {
      await demoLogin();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Demo login failed");
    } finally {
      setDemoLoading(false);
    }
  };

  const inputCls =
    "w-full h-11 rounded-lg border border-white/10 bg-white/[0.04] px-3.5 text-[13.5px] text-white " +
    "placeholder-white/30 outline-none transition focus:border-indigo-400/60 focus:bg-white/[0.06] " +
    "focus:ring-2 focus:ring-indigo-500/20";

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden bg-[#06060f] px-4">
      {/* Premium glow mesh */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(55% 45% at 50% -5%, rgba(79,70,229,0.35), transparent 70%)," +
            "radial-gradient(40% 40% at 85% 100%, rgba(6,182,212,0.18), transparent 70%)," +
            "radial-gradient(40% 40% at 10% 90%, rgba(124,58,237,0.16), transparent 70%)",
        }}
      />
      <div className="pointer-events-none absolute inset-0 hx-grid-bg opacity-[0.05]" />
      {/* soft top vignette */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/15 to-transparent" />

      <div className="relative z-10 w-full max-w-[400px]">
        {/* Brand */}
        <div className="flex flex-col items-center mb-7">
          <div className="grid place-items-center h-12 w-12 rounded-2xl bg-white/[0.06] border border-white/10 shadow-lg shadow-black/40">
            <HelixLogo size={26} />
          </div>
          <span className="mt-3.5 text-white font-semibold text-[17px] tracking-tight">Helix Migration</span>
          <span className="mt-1 text-[11.5px] uppercase tracking-[0.18em] text-white/35">
            Open-source · Self-hosted
          </span>
        </div>

        {/* Glass card */}
        <div className="rounded-2xl border border-white/10 bg-white/[0.045] backdrop-blur-2xl shadow-[0_24px_70px_-20px_rgba(0,0,0,0.8)] p-7">
          <h2 className="text-[22px] font-semibold tracking-tight text-white">Welcome back</h2>
          <p className="text-[13px] text-white/45 mt-1">Sign in to your migration command center.</p>

          {error && (
            <div className="mt-5 rounded-lg border border-red-400/25 bg-red-500/10 px-3.5 py-2.5 text-[12.5px] text-red-200">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="email" className="block text-[12px] font-medium text-white/55 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@company.com"
                className={inputCls}
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-[12px] font-medium text-white/55 mb-1.5">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                className={inputCls}
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full h-11 rounded-lg bg-gradient-to-r from-indigo-500 to-cyan-500 text-white text-[14px] font-semibold shadow-lg shadow-indigo-500/25 transition hover:from-indigo-400 hover:to-cyan-400 active:scale-[0.99] disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {loading ? "Signing in…" : "Sign In"}
            </button>
          </form>

          {demoEnabled && (
            <>
              <div className="flex items-center gap-3 my-5">
                <div className="h-px flex-1 bg-white/10" />
                <span className="text-[10.5px] uppercase tracking-wider text-white/30">or</span>
                <div className="h-px flex-1 bg-white/10" />
              </div>
              <button
                type="button"
                onClick={handleDemo}
                disabled={demoLoading}
                className="w-full h-11 rounded-lg border border-white/15 bg-white/[0.03] text-white text-[13.5px] font-medium transition hover:bg-white/[0.07] hover:border-white/25 active:scale-[0.99] disabled:opacity-60"
              >
                {demoLoading ? "Signing in…" : "Login with Demo User"}
              </button>
              <p className="mt-2.5 text-[11.5px] text-white/35 text-center">
                Read-only sandbox with sample data — no account needed.
              </p>
            </>
          )}
        </div>

        <p className="mt-6 text-[12px] text-white/35 text-center">
          New to Helix?{" "}
          <Link href="/setup/first-admin" className="text-indigo-300 hover:text-indigo-200 font-medium">
            First-admin setup
          </Link>
        </p>
        <p className="mt-2 text-[11px] text-white/25 text-center">© 2026 Helix Migration · Apache-2.0</p>
      </div>
    </div>
  );
}
