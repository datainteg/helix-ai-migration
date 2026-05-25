import { Link } from "react-router-dom";
import { Github, ArrowRight } from "lucide-react";

import { SITE } from "@/data/site-content";

export function CTA() {
  return (
    <section className="py-16 md:py-24 container-tight">
      <div
        className="relative overflow-hidden rounded-2xl px-8 md:px-14 py-14 md:py-20 text-center shadow-hero"
        style={{ background: "linear-gradient(135deg, #4F46E5 0%, #06B6D4 100%)" }}
      >
        <div
          className="absolute inset-0 grid-faint-bg opacity-20 pointer-events-none"
          aria-hidden="true"
        />
        <h2 className="relative text-[28px] md:text-[36px] font-semibold tracking-tight text-white leading-tight max-w-[680px] mx-auto">
          Ship your next migration with Helix.
        </h2>
        <p className="relative mt-4 text-[14.5px] md:text-[15px] text-white/85 leading-relaxed max-w-[560px] mx-auto">
          Self-hosted. Open source. Six BMAD agents and a 13-step pipeline already wired.
        </p>
        <div className="relative mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/demo"
            className="inline-flex items-center gap-2 px-5 h-11 rounded-md bg-white text-ink text-[13.5px] font-semibold hover:bg-zinc-100 focus-ring"
          >
            View demo
            <ArrowRight className="h-4 w-4" />
          </Link>
          <a
            href={SITE.github}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-5 h-11 rounded-md border border-white/40 text-white text-[13.5px] font-semibold hover:bg-white/10 focus-ring"
          >
            <Github className="h-4 w-4" />
            Open on GitHub
          </a>
        </div>
      </div>
    </section>
  );
}
