"use client";

// The marketing/landing content now lives in the separate `website/` project.
// The app root just routes to the right place: dashboard if already signed in,
// otherwise straight to the login page.
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function RootRedirect() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? "/dashboard" : "/login");
  }, [user, loading, router]);

  return (
    <div className="min-h-screen grid place-items-center bg-app">
      <span className="text-[13px] text-ink-3">Loading…</span>
    </div>
  );
}
