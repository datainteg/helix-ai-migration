"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ThemeToggle } from "@/components/ThemeToggle";

export function HelixNav() {
  const { token, user, logout } = useAuth();
  return (
    <nav className="border-b bg-white dark:bg-gray-900 dark:border-gray-800 px-6 py-3 flex items-center gap-6 text-sm">
      <Link href="/" className="font-bold text-helix-700 dark:text-helix-400 text-lg">Helix Migration</Link>
      <Link href="/dashboard" className="text-gray-600 dark:text-gray-400 hover:text-helix-600">Dashboard</Link>
      <Link href="/projects" className="text-gray-600 dark:text-gray-400 hover:text-helix-600">Projects</Link>
      <Link href="/admin" className="text-gray-600 dark:text-gray-400 hover:text-helix-600">Admin</Link>
      <div className="ml-auto flex items-center gap-3">
        <ThemeToggle />
        {token ? (
          <>
            <span className="text-xs text-gray-500 dark:text-gray-400">{user?.email}</span>
            <button onClick={logout} className="text-gray-600 dark:text-gray-400 hover:text-red-600">Logout</button>
          </>
        ) : (
          <Link href="/login" className="text-gray-600 dark:text-gray-400 hover:text-helix-600">Login</Link>
        )}
      </div>
    </nav>
  );
}
