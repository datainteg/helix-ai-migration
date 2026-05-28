import React from "react";
import { cn } from "@/lib/utils";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  title?: React.ReactNode;
  eyebrow?: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  padding?: "none" | "sm" | "md" | "lg";
  bodyClassName?: string;
  /**
   * Heading level to render the `title` as. Defaults to `"h2"` so a typical
   * page with one `<h1>` (PageHero) plus several `<Card>` blocks produces a
   * navigable heading outline for screen readers. Pass `"div"` when the
   * card sits inside content that already has its own h2/h3 above it.
   */
  as?: "h2" | "h3" | "div";
}

const padMap = {
  none: { outer: "", inner: "" },
  sm:   { outer: "p-3.5", inner: "p-3.5" },
  md:   { outer: "p-[18px]", inner: "p-[18px]" },
  lg:   { outer: "p-6", inner: "p-6" },
};

/**
 * Calm, operations-console card.
 * - 10px radius (not 16px)
 * - subtle 1px border, micro-shadow
 * - optional eyebrow + title + description + actions header
 * - `bodyClassName="p-0"` removes inner padding so tables can bleed to edges
 */
export function Card({
  children,
  className,
  title,
  eyebrow,
  description,
  actions,
  padding = "md",
  bodyClassName,
  as: TitleTag = "h2",
}: CardProps) {
  const showHeader = title || actions || eyebrow;
  return (
    <div
      className={cn(
        "card flex flex-col bg-surface border border-hx rounded-[10px] shadow-xs",
        className
      )}
    >
      {showHeader && (
        <div
          className={cn(
            "flex items-start justify-between gap-3",
            padMap[padding].outer,
            "pb-3"
          )}
        >
          <div className="min-w-0">
            {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
            {title && (
              <TitleTag className="text-[14px] font-semibold text-ink tracking-tight m-0">
                {title}
              </TitleTag>
            )}
            {description && (
              <div className="text-[12px] text-ink-3 mt-0.5">{description}</div>
            )}
          </div>
          {actions && (
            <div className="flex items-center gap-1.5 flex-shrink-0">{actions}</div>
          )}
        </div>
      )}
      <div className={cn("flex-1", showHeader ? "px-[18px] pb-[18px] pt-0" : padMap[padding].inner, bodyClassName)}>
        {children}
      </div>
    </div>
  );
}

export function CardSection({
  title,
  eyebrow,
  actions,
  children,
  className,
}: {
  title?: React.ReactNode;
  eyebrow?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("space-y-3", className)}>
      {(title || actions || eyebrow) && (
        <header className="flex items-end justify-between gap-3">
          <div>
            {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
            {title && (
              <h2 className="text-[15px] font-semibold text-ink tracking-tight">
                {title}
              </h2>
            )}
          </div>
          {actions && <div className="flex items-center gap-1.5">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
