import { Link, NavLink } from "react-router-dom";
import { Github, Menu, X } from "lucide-react";
import { useState } from "react";

import { NAV, SITE, STATIC_DEMO_URL } from "@/data/site-content";
import { BrandMark } from "@/components/layout/BrandMark";

export function Navbar() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 backdrop-blur-xl bg-white/72 border-b border-zinc-200/80">
      <div className="container-tight flex items-center h-16 gap-6">
        <Link to="/" className="flex items-center gap-2 focus-ring rounded">
          <BrandMark className="h-8 w-8 rounded-lg" />
          <span className="text-[15px] font-semibold tracking-tight">{SITE.name}</span>
        </Link>
        <nav className="hidden md:flex items-center gap-1 ml-4 flex-1">
          {NAV.map((n) => (
            <NavLink
              key={n.href}
              to={n.href}
            className={({ isActive }) =>
                "px-3 py-1.5 rounded-full text-[13.5px] font-medium transition-colors " +
                (isActive ? "text-ink bg-zinc-100" : "text-ink-3 hover:text-ink hover:bg-zinc-100/70")
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="hidden md:flex items-center gap-2 ml-auto">
          <a
            href={SITE.github}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[13px] text-ink-3 hover:text-ink hover:bg-zinc-100/70 focus-ring"
          >
            <Github className="h-4 w-4" />
            GitHub
          </a>
          {/* View demo opens the static HTML console mock in a new tab. The
              interactive React walkthrough stays reachable via the NAV link. */}
          <a
            href={STATIC_DEMO_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center px-3.5 py-1.5 rounded-full text-[13px] font-medium bg-gradient-to-r from-brand-600 to-cyan-600 text-white hover:opacity-95 focus-ring"
          >
            View demo
          </a>
        </div>
        <button
          onClick={() => setOpen((v) => !v)}
          className="md:hidden ml-auto p-2 rounded-md text-ink-2 hover:bg-zinc-100"
          aria-label="Toggle menu"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>
      {open && (
        <div className="md:hidden border-t border-zinc-200 bg-surface">
          <div className="container-tight py-3 flex flex-col gap-1">
            {NAV.map((n) => (
              <NavLink
                key={n.href}
                to={n.href}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  "px-3 py-2 rounded-md text-[14px] " +
                  (isActive ? "bg-zinc-100 text-ink" : "text-ink-2 hover:bg-zinc-100/70")
                }
              >
                {n.label}
              </NavLink>
            ))}
            <a
              href={SITE.github}
              target="_blank"
              rel="noreferrer"
              className="px-3 py-2 rounded-md text-[14px] text-ink-2 hover:bg-zinc-100/70 inline-flex items-center gap-2"
            >
              <Github className="h-4 w-4" /> GitHub
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
