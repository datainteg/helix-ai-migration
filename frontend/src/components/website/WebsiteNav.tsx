"use client";

import Link from "next/link";
import { Github, ArrowRight } from "lucide-react";
import { HelixLogo } from "@/components/layout/HelixLogo";
import { Button } from "@/components/ui/Button";

const LINKS = [
  { label: "Product", href: "#product" },
  { label: "Features", href: "#features" },
  { label: "Architecture", href: "#architecture" },
  { label: "Open Source", href: "#open-source" },
  { label: "Docs", href: "https://github.com/datainteg/helix-ai-migration#readme" },
];

export function WebsiteNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-hx-2 bg-white/85 backdrop-blur-md">
      <div className="max-w-[1200px] mx-auto px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-9">
          <Link href="/" className="inline-flex items-center gap-2.5">
            <HelixLogo size={28} />
            <span className="font-semibold text-[16px] tracking-tight">Helix Migration</span>
          </Link>
          <nav className="hidden md:flex gap-7 text-[14px] text-ink-3">
            {LINKS.map((l) => (
              <a key={l.label} href={l.href} className="hover:text-ink transition-colors">
                {l.label}
              </a>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2.5">
          <Link href="/login" className="hidden sm:inline-block text-[13.5px] text-ink-3 hover:text-ink px-2">
            Sign in
          </Link>
          <a
            href="https://github.com/datainteg/helix-ai-migration"
            target="_blank"
            rel="noreferrer"
            className="hidden sm:inline-flex items-center gap-2 h-9 px-3 rounded-lg border border-hx bg-surface text-[13px] text-ink-2 hover:bg-zinc-50"
          >
            <Github className="h-3.5 w-3.5" />
            Star · 2.4k
          </a>
          <Link href="/setup/first-admin">
            <Button size="sm" className="!h-9 !px-3.5">
              Get Started <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      </div>
    </header>
  );
}
