import { Link, NavLink } from "react-router-dom";
import { Github, Menu, X } from "lucide-react";
import { useState } from "react";

import { NAV, SITE } from "@/data/site-content";

export function Navbar() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 backdrop-blur bg-surface/80 border-b border-zinc-200/70">
      <div className="container-tight flex items-center h-16 gap-6">
        <Link to="/" className="flex items-center gap-2 focus-ring rounded">
          <Logo />
          <span className="text-[15px] font-semibold tracking-tight">Helix Migration</span>
        </Link>
        <nav className="hidden md:flex items-center gap-1 ml-4 flex-1">
          {NAV.map((n) => (
            <NavLink
              key={n.href}
              to={n.href}
              className={({ isActive }) =>
                "px-3 py-1.5 rounded-md text-[13.5px] font-medium transition-colors " +
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
          <Link
            to="/demo"
            className="inline-flex items-center px-3.5 py-1.5 rounded-md text-[13px] font-medium bg-ink text-white hover:bg-zinc-800 focus-ring"
          >
            View demo
          </Link>
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

function Logo() {
  return (
    <div
      className="h-8 w-8 rounded-lg grid place-items-center text-white font-semibold text-[15px] tracking-tight"
      style={{ background: "linear-gradient(135deg,#4F46E5,#06B6D4)", letterSpacing: "-0.04em" }}
      aria-label="Helix Migration logo"
    >
      H
    </div>
  );
}
