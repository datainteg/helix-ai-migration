import { useState } from "react";
import { Link } from "react-router-dom";
import { Copy, Check, ArrowRight } from "lucide-react";

import { DOCKER_INSTALL, SITE } from "@/data/site-content";

export function DockerInstall() {
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
    <section className="py-16 md:py-24 container-tight">
      <div className="text-center max-w-[720px] mx-auto">
        <div className="eyebrow mb-3">{SITE.tagline}</div>
        <h2 className="text-[28px] md:text-[34px] font-semibold tracking-tight text-ink leading-tight">
          Get running in under 5 minutes.
        </h2>
        <p className="mt-3 text-[14.5px] text-ink-3 leading-relaxed">
          One repo. One docker-compose. The whole stack — backend, worker, postgres, redis, temporal,
          and the operator UI — on your laptop.
        </p>
      </div>

      <div className="mt-10 max-w-[760px] mx-auto">
        <div className="bg-surface border border-zinc-200 rounded-xl shadow-soft overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-200 bg-zinc-50/70">
            <span className="font-mono text-[11px] text-ink-4">terminal · bash</span>
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

        <div className="mt-5 flex justify-center">
          <Link
            to="/docs/installation"
            className="inline-flex items-center gap-2 px-4 h-10 rounded-md border border-zinc-300 text-ink-2 text-[13.5px] font-medium hover:bg-zinc-100 focus-ring"
          >
            Full installation guide
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </section>
  );
}
