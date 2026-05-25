import { useState } from "react";
import { Link } from "react-router-dom";
import { Github, Copy, Check, ArrowRight } from "lucide-react";

import { SITE, HERO_CTAS, DOCKER_INSTALL } from "@/data/site-content";

export function Hero() {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(DOCKER_INSTALL);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* no-op */
    }
  };

  return (
    <section className="relative overflow-hidden">
      <div className="absolute inset-0 grid-faint-bg pointer-events-none" />
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 0%, rgba(99,102,241,0.10) 0%, rgba(6,182,212,0.05) 40%, transparent 70%)",
        }}
      />
      <div className="relative container-tight pt-20 md:pt-28 pb-16 md:pb-24">
        <div className="max-w-[820px]">
          <div className="eyebrow mb-4">{SITE.tagline}</div>
          <h1 className="text-[34px] md:text-[46px] font-semibold tracking-tight text-ink leading-[1.08]">
            Plan, validate, and reconcile complex enterprise migrations with a multi-agent AI brain.
          </h1>
          <p className="text-[15px] md:text-[16px] text-ink-3 mt-5 leading-relaxed max-w-[640px]">
            {SITE.oneLiner}
          </p>

          <div className="flex flex-wrap items-center gap-3 mt-8">
            <Link
              to={HERO_CTAS.primary.href}
              className="inline-flex items-center gap-2 px-4 h-10 rounded-md bg-ink text-white text-[13.5px] font-medium hover:bg-zinc-800 focus-ring"
            >
              {HERO_CTAS.primary.label}
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to={HERO_CTAS.secondary.href}
              className="inline-flex items-center gap-2 px-4 h-10 rounded-md border border-zinc-300 text-ink-2 text-[13.5px] font-medium hover:bg-zinc-100 focus-ring"
            >
              {HERO_CTAS.secondary.label}
            </Link>
            <a
              href={HERO_CTAS.tertiary.href}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-3 h-10 rounded-md text-ink-3 text-[13.5px] font-medium hover:text-ink hover:bg-zinc-100/70 focus-ring"
            >
              <Github className="h-4 w-4" />
              {HERO_CTAS.tertiary.label}
            </a>
          </div>
        </div>

        <div className="mt-12 md:mt-16 max-w-[760px]">
          <div className="bg-surface border border-zinc-200 rounded-xl shadow-soft overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-200 bg-zinc-50/70">
              <div className="flex items-center gap-2">
                <div className="flex gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-zinc-300" />
                  <span className="h-2.5 w-2.5 rounded-full bg-zinc-300" />
                  <span className="h-2.5 w-2.5 rounded-full bg-zinc-300" />
                </div>
                <span className="ml-2 font-mono text-[11px] text-ink-4">install · ~5 min</span>
              </div>
              <button
                onClick={onCopy}
                className="inline-flex items-center gap-1.5 px-2.5 h-7 rounded-md text-[11.5px] text-ink-3 hover:text-ink hover:bg-zinc-100 focus-ring"
                aria-label="Copy install command"
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <pre className="px-5 py-4 font-mono text-[12.5px] text-ink-2 leading-relaxed whitespace-pre-wrap break-all md:whitespace-pre md:break-normal overflow-x-auto">{DOCKER_INSTALL}</pre>
          </div>
        </div>
      </div>
    </section>
  );
}
