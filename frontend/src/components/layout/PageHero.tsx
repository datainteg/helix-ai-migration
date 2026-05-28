import React from "react";
import Link from "next/link";

interface PageHeroProps {
  /** Small uppercase eyebrow line above the title */
  eyebrow?: React.ReactNode;
  /** Large editorial title */
  title: string;
  /** Backward-compat: legacy "subtitle" prop, displayed as description */
  subtitle?: string;
  description?: React.ReactNode;
  /** Inline mono line shown next to the title — e.g. "412 tables · 38.4 TB" */
  metric?: React.ReactNode;
  /** Breadcrumbs above the eyebrow. Each is either a string or a {label, href} object. */
  crumbs?: Array<string | { label: string; href?: string }>;
  /** Right-side action buttons */
  actions?: React.ReactNode;
  /** Legacy prop — kept for compatibility, ignored in redesign */
  withArt?: boolean;
}

/**
 * Editorial page header.
 * - Eyebrow (small mono uppercase)
 * - Large 32px title + optional mono metric line beside it
 * - Description paragraph (max 640px)
 * - Right-side actions
 * - Sits inside main, above the page body. NOT sticky.
 */
export function PageHero({ eyebrow, title, subtitle, description, metric, crumbs, actions }: PageHeroProps) {
  const desc = description ?? subtitle;
  return (
    <div className="px-4 sm:px-6 lg:px-10 pt-8 pb-6 border-b border-hx">
      {crumbs && crumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 mb-3.5 text-[11.5px] text-ink-4">
          {crumbs.map((c, i) => {
            const label = typeof c === "string" ? c : c.label;
            const href = typeof c === "string" ? undefined : c.href;
            const isLast = i === crumbs.length - 1;
            return (
              <span key={i} className="inline-flex items-center gap-1.5">
                {i > 0 && <span className="opacity-50">/</span>}
                {href && !isLast ? (
                  <Link href={href} className="text-ink-4 hover:text-ink-2">
                    {label}
                  </Link>
                ) : (
                  <span className={isLast ? "text-ink-2" : "text-ink-4"}>{label}</span>
                )}
              </span>
            );
          })}
        </nav>
      )}

      <div className="flex items-end justify-between gap-6 flex-wrap">
        <div className="min-w-0 flex-1">
          {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
          <div className="flex items-baseline gap-4 flex-wrap">
            <h1 className="text-[32px] font-medium tracking-editorial leading-[1.1] m-0">{title}</h1>
            {metric && <div className="font-mono tabular-nums text-[14px] text-ink-3">{metric}</div>}
          </div>
          {desc && (
            <div className="mt-2.5 text-[13px] text-ink-3 max-w-[640px]">{desc}</div>
          )}
        </div>
        {actions && <div className="flex gap-2 flex-shrink-0">{actions}</div>}
      </div>
    </div>
  );
}
