import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Helix Migration",
  description: "Open-source AI-powered migration and validation platform.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        <Providers>
          <AuthProvider>
            <HelixNav />
            <main className="p-6">{children}</main>
          </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}

"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

function HelixNav() {
  const { token, user, logout } = useAuth();
  return (
    <nav className="border-b bg-white px-6 py-3 flex items-center gap-6 text-sm">
      <Link href="/" className="font-bold text-helix-700 text-lg">Helix Migration</Link>
      <Link href="/dashboard" className="text-gray-600 hover:text-helix-600">Dashboard</Link>
      <Link href="/projects" className="text-gray-600 hover:text-helix-600">Projects</Link>
      <Link href="/admin" className="text-gray-600 hover:text-helix-600">Admin</Link>
      <div className="ml-auto flex items-center gap-4">
        {token ? (
          <>
            <span className="text-xs text-gray-500">{user?.email}</span>
            <button onClick={logout} className="text-gray-600 hover:text-red-600">Logout</button>
          </>
        ) : (
          <Link href="/login" className="text-gray-600 hover:text-helix-600">Login</Link>
        )}
      </div>
    </nav>
  );
}
