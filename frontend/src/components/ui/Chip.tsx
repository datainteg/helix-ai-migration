import React from "react";
import { cn } from "@/lib/utils";

export type ChipTone =
  | "default"
  | "brand"
  | "indigo"      // legacy alias for brand
  | "violet"      // legacy
  | "cyan"        // legacy
  | "ok"
  | "green"       // legacy alias for ok
  | "warn"
  | "amber"       // legacy alias for warn
  | "err"
  | "red"         // legacy alias for err
  | "info"
  | "zinc";

const toneMap: Record<ChipTone, { bg: string; fg: string; dot: string }> = {
  default: { bg: "bg-app-2",                        fg: "text-ink-2",  dot: "bg-ink-4" },
  brand:   { bg: "bg-[var(--con-brand-soft)]",      fg: "text-[var(--con-brand)]", dot: "bg-[var(--con-brand)]" },
  indigo:  { bg: "bg-[var(--con-brand-soft)]",      fg: "text-[var(--con-brand)]", dot: "bg-[var(--con-brand)]" },
  violet:  { bg: "bg-violet-50",                    fg: "text-violet-700", dot: "bg-violet-500" },
  cyan:    { bg: "bg-cyan-50",                      fg: "text-cyan-700",   dot: "bg-cyan-500" },
  ok:      { bg: "bg-[var(--con-ok-soft)]",         fg: "text-ok",   dot: "bg-[var(--con-ok)]" },
  green:   { bg: "bg-[var(--con-ok-soft)]",         fg: "text-ok",   dot: "bg-[var(--con-ok)]" },
  warn:    { bg: "bg-[var(--con-warn-soft)]",       fg: "text-warn", dot: "bg-[var(--con-warn)]" },
  amber:   { bg: "bg-[var(--con-warn-soft)]",       fg: "text-warn", dot: "bg-[var(--con-warn)]" },
  err:     { bg: "bg-[var(--con-err-soft)]",        fg: "text-err",  dot: "bg-[var(--con-err)]" },
  red:     { bg: "bg-[var(--con-err-soft)]",        fg: "text-err",  dot: "bg-[var(--con-err)]" },
  info:    { bg: "bg-[var(--con-info-soft)]",       fg: "text-info", dot: "bg-[var(--con-info)]" },
  zinc:    { bg: "bg-app-2",                        fg: "text-ink-3", dot: "bg-ink-4" },
};

interface ChipProps {
  children: React.ReactNode;
  tone?: ChipTone;
  dot?: boolean;
  pulse?: boolean;
  mono?: boolean;
  className?: string;
}

/**
 * Small status / tag pill.
 * - 4px radius (was full-pill 999px), tighter padding
 * - no border by default — color comes from soft bg + tinted text
 */
export function Chip({ children, tone = "default", dot = false, pulse = false, mono = false, className }: ChipProps) {
  const t = toneMap[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium leading-[1.45]",
        t.bg,
        t.fg,
        mono && "font-mono",
        className
      )}
    >
      {dot && <span className={cn("h-1.5 w-1.5 rounded-full", t.dot, pulse && "animate-pulse-dot")} />}
      {children}
    </span>
  );
}
