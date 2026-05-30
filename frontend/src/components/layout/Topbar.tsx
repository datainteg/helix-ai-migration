"use client";

import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { AskHelix } from "./AskHelix";
import { NotificationBell } from "@/components/notifications/NotificationBell";

interface TopbarProps {
  /** Breadcrumb items, in order. Last item is shown as the active label. */
  crumbs?: string[];
  /** Optional content placed before the right-side actions */
  extras?: React.ReactNode;
  /** Mobile hamburger click handler — opens the Sidebar drawer */
  onMobileMenuClick?: () => void;
}

/**
 * Calm 44-px topbar: breadcrumbs left, notifications + Ask Helix right.
 * Sticky at top under the page header. On lg- screens shows a hamburger
 * button on the left that toggles the Sidebar drawer.
 */
export function Topbar({ crumbs = [], extras, onMobileMenuClick }: TopbarProps) {
  const trail = ["Helix", ...crumbs];
  return (
    <header className="h-11 flex-shrink-0 border-b border-hx bg-app flex items-center gap-2 sm:gap-4 px-3 sm:px-6 sticky top-0 z-10">
      {/* Mobile hamburger — only visible below lg breakpoint */}
      {onMobileMenuClick && (
        <button
          type="button"
          aria-label="Open navigation menu"
          aria-haspopup="dialog"
          onClick={onMobileMenuClick}
          className="lg:hidden grid place-items-center h-9 w-9 -ml-1 rounded-md text-ink-3 hover:bg-app-2"
        >
          <Menu className="h-[18px] w-[18px]" />
        </button>
      )}

      {/* Breadcrumbs */}
      <nav aria-label="Breadcrumb" className="flex-1 min-w-0 flex items-center gap-2 text-[12px] text-ink-3">
        {trail.map((c, i) => (
          <span key={i} className="inline-flex items-center gap-2 min-w-0">
            {i > 0 && <span aria-hidden className="text-ink-5">›</span>}
            <span
              className={cn(
                "truncate",
                i === trail.length - 1 ? "text-ink font-medium" : "text-ink-3"
              )}
              aria-current={i === trail.length - 1 ? "page" : undefined}
            >
              {c}
            </span>
          </span>
        ))}
      </nav>

      {/* Right actions */}
      <div className="flex items-center gap-1.5">
        {extras}
        <NotificationBell />
        {/* The Ask Helix Help agent — opens a themed chat popup that guides
            users on how Helix works (see AskHelix.tsx). */}
        <AskHelix />
      </div>
    </header>
  );
}
