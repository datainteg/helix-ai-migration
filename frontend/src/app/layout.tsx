import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { Providers } from "./providers";
import { HelixNav } from "@/components/HelixNav";

export const metadata: Metadata = {
  title: "Helix Migration",
  description: "Open-source AI-powered migration and validation platform.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-100">
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
