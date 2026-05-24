import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Helix Migration — Open-source AI-powered migration & validation platform",
  description:
    "Plan, validate, reconcile, and ship complex enterprise data migrations with multi-agent workflows. Self-hosted, Apache 2.0, bring-your-own LLM.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-app text-ink antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
