import { Link } from "react-router-dom";
import { Github } from "lucide-react";

import { FOOTER, SITE } from "@/data/site-content";

export function Footer() {
  return (
    <footer className="border-t border-zinc-200 bg-surface mt-24">
      <div className="container-tight py-14 grid grid-cols-2 md:grid-cols-5 gap-8">
        <div className="col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <div className="h-7 w-7 rounded-md grid place-items-center text-white font-semibold text-[13px]" style={{ background: "linear-gradient(135deg,#4F46E5,#06B6D4)", letterSpacing: "-0.04em" }}>
              H
            </div>
            <span className="text-[14px] font-semibold">{SITE.name}</span>
          </div>
          <p className="text-[12.5px] text-ink-3 max-w-xs leading-relaxed">{SITE.tagline}</p>
          <p className="text-[11.5px] text-ink-4 mt-3 font-mono">{SITE.license} · {SITE.domain}</p>
        </div>
        <FooterColumn title="Product"   items={FOOTER.product} />
        <FooterColumn title="Developers" items={FOOTER.developers} />
        <FooterColumn title="Community" items={FOOTER.community} />
      </div>
      <div className="border-t border-zinc-200 bg-zinc-50/60">
        <div className="container-tight py-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-2 text-[11.5px] text-ink-4">
          <span>© {new Date().getFullYear()} Helix Migration · Apache 2.0</span>
          <a href={SITE.github} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 hover:text-ink-3">
            <Github className="h-3.5 w-3.5" />
            github.com/{SITE.repoSlug}
          </a>
        </div>
      </div>
    </footer>
  );
}

function FooterColumn({ title, items }: { title: string; items: { label: string; href: string; external?: boolean }[] }) {
  return (
    <div>
      <p className="eyebrow text-[10px] mb-3">{title}</p>
      <ul className="space-y-2">
        {items.map((it) =>
          it.external ? (
            <li key={it.label}>
              <a href={it.href} target="_blank" rel="noreferrer" className="text-[12.5px] text-ink-3 hover:text-ink">{it.label}</a>
            </li>
          ) : (
            <li key={it.label}>
              <Link to={it.href} className="text-[12.5px] text-ink-3 hover:text-ink">{it.label}</Link>
            </li>
          )
        )}
      </ul>
    </div>
  );
}
