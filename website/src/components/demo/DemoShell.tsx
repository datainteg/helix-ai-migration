import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Bell, Search, Sparkles } from "lucide-react";

import { DEMO_RUN } from "@/data/demo-data";
import { DemoSidebar } from "./DemoSidebar";

interface DemoShellProps {
  title: string;
  description?: string;
  children: ReactNode;
}

/**
 * DemoShell — warm cream chrome that mirrors the Helix Console mock the
 * design system was built against. Cream `#FAFAF7` background, premium
 * radius, real toolbar with search + workflow chip + bell so the demo
 * feels like a live product not a Tailwind tutorial.
 */
export function DemoShell({ title, description, children }: DemoShellProps) {
  return (
    <div className="min-h-[calc(100vh-4rem)]" style={{ background: "#FAFAF7" }}>
      {/* Demo banner — full-width, top of page */}
      <div className="bg-amber-50 border-b border-amber-200 px-6 py-2 text-[12px] text-amber-900 text-center">
        <span className="inline-flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5" />
          Demo data — interactive walkthrough.{" "}
          <Link to="/docs" className="underline font-medium hover:text-amber-950">
            Read docs
          </Link>{" "}
          to see the real product.
        </span>
      </div>

      <div className="container-tight py-6 md:py-10">
        <div className="md:flex md:gap-10">
          <DemoSidebar />
          <div className="flex-1 min-w-0">
            {/* Toolbar — mimics the Helix Console topbar with search + workflow chip */}
            <div className="hidden md:flex items-center gap-3 mb-6 px-1">
              <div className="flex-1 max-w-md relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-4" />
                <input
                  placeholder="Search projects, agents, artifacts…"
                  className="w-full h-9 pl-9 pr-3 rounded-lg bg-surface border border-zinc-200 text-[13px] text-ink placeholder:text-ink-4 focus:outline-none focus:border-zinc-400"
                />
              </div>
              <div className="inline-flex items-center gap-2 px-2.5 h-9 rounded-lg bg-surface border border-zinc-200">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                <span className="font-mono text-[11.5px] text-ink-3">{DEMO_RUN.workflowId}</span>
              </div>
              <button
                aria-label="Notifications"
                className="h-9 w-9 grid place-items-center rounded-lg bg-surface border border-zinc-200 text-ink-3 hover:text-ink hover:bg-surface-muted"
              >
                <Bell className="h-4 w-4" />
              </button>
            </div>

            {/* Page header */}
            <header className="mb-6 px-1">
              <h1 className="text-[24px] md:text-[30px] font-semibold tracking-tight text-ink leading-tight">
                {title}
              </h1>
              {description && (
                <p className="text-[14px] text-ink-3 mt-2 leading-relaxed max-w-3xl">
                  {description}
                </p>
              )}
            </header>

            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
