import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Helix Migration",
  description: "Open-source AI-powered migration and validation platform.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        <nav className="border-b bg-white px-6 py-3 flex items-center gap-6 text-sm">
          <Link href="/" className="font-bold text-helix-700 text-lg">Helix Migration</Link>
          <Link href="/dashboard" className="text-gray-600 hover:text-helix-600">Dashboard</Link>
          <Link href="/projects" className="text-gray-600 hover:text-helix-600">Projects</Link>
          <Link href="/admin" className="text-gray-600 hover:text-helix-600">Admin</Link>
          <div className="ml-auto">
            <Link href="/login" className="text-gray-600 hover:text-helix-600">Login</Link>
          </div>
        </nav>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
