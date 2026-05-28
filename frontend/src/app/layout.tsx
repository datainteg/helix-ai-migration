import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Helix Migration — Open-source AI-powered migration & validation platform",
  description:
    "Plan, validate, reconcile, and ship complex enterprise data migrations with multi-agent workflows. Self-hosted, Apache 2.0, bring-your-own LLM.",
};

// UI-039 — declare viewport explicitly so the intent is visible and any future
// regression (e.g. a maximum-scale lock that hurts accessibility) is a diff.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      {/* UI-038 — Geist is loaded via <link> with preconnect rather than a CSS
          `@import` (which blocks CSS parsing). next/font/google does not ship a
          Geist entry for the pinned Next 14.2.35 and adding the `geist` package
          is out of scope (no new deps), so this is the no-dep way to drop the
          render-blocking @import while keeping the typeface identical. */}
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700;800&family=Geist+Mono:wght@400;500;600&display=swap"
        />
      </head>
      <body className="bg-app text-ink antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
