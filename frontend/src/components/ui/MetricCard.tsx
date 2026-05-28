import React from "react";
import { cn } from "@/lib/utils";
import { Sparkline } from "./Sparkline";

interface MetricCardProps {
  label: string;
  value: string | number;
  /** Optional secondary line under the metric, e.g. "30-day avg" */
  hint?: React.ReactNode;
  /** Percentage delta — colored arrow + value */
  delta?: number;
  deltaLabel?: string;
  /** Backward-compat legacy props — still accepted */
  spark?: number[];
  sparkColor?: string;
  icon?: React.ReactNode;
  /** Force an accent color on the numeric (e.g. red for failures) */
  accent?: string;
  /** Render a larger numeric for hero placements */
  big?: boolean;
  className?: string;
}

/**
 * Editorial metric cell.
 * Big mono numeric, small uppercase label, optional trend + hint.
 * Often used inside a strip with `divide-x divide-hx` siblings.
 */
export function MetricCard({
  label,
  value,
  hint,
  delta,
  deltaLabel,
  spark,
  sparkColor = "var(--con-brand)",
  icon,
  accent,
  big = false,
  className,
}: MetricCardProps) {
  const dir = delta === undefined ? 0 : delta > 0 ? 1 : delta < 0 ? -1 : 0;
  return (
    <div className={cn("bg-surface border border-hx rounded-[10px] px-5 py-4", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="eyebrow text-[10px]">{label}</div>
          <div
            title={String(value)}
            className={cn(
              "mt-1 font-mono tabular-nums leading-[1.05] font-medium tracking-editorial truncate",
              big ? "text-[32px]" : "text-[24px]"
            )}
            style={{ color: accent || "var(--con-ink-1)" }}
          >
            {value}
          </div>
          {(hint || delta !== undefined) && (
            <div className="mt-1.5 flex items-center gap-2 text-[11px] text-ink-3">
              {delta !== undefined && (
                <span
                  className="font-mono"
                  style={{
                    color: dir > 0 ? "var(--con-ok)" : dir < 0 ? "var(--con-err)" : "var(--con-ink-3)",
                  }}
                >
                  {dir > 0 ? "▲" : dir < 0 ? "▼" : "—"} {Math.abs(delta).toFixed(1)}%
                </span>
              )}
              {hint && <span>{hint}</span>}
              {deltaLabel && <span>{deltaLabel}</span>}
            </div>
          )}
        </div>
        {icon && <div className="text-ink-4">{icon}</div>}
      </div>
      {spark && spark.length > 1 && (
        <div className="mt-3">
          <Sparkline data={spark} color={sparkColor} width={200} height={28} />
        </div>
      )}
    </div>
  );
}

/**
 * Variant that drops the card chrome — for use inside a single horizontally-divided strip.
 * Pair via parent: <div className="grid grid-cols-5 bg-surface border border-hx rounded-[10px] divide-x divide-hx">…</div>
 */
export function MetricCell({
  label,
  value,
  hint,
  delta,
  accent,
  big = false,
  className,
}: MetricCardProps) {
  const dir = delta === undefined ? 0 : delta > 0 ? 1 : delta < 0 ? -1 : 0;
  return (
    // min-w-0 so the cell can shrink inside a reflowed grid (UI-025); the value
    // line truncates instead of forcing the column wider than its track.
    <div className={cn("px-5 py-4 min-w-0", className)}>
      <div className="eyebrow text-[10px]">{label}</div>
      <div
        title={String(value)}
        className={cn(
          "mt-1 font-mono tabular-nums leading-[1.05] font-medium tracking-editorial truncate",
          big ? "text-[32px]" : "text-[24px]"
        )}
        style={{ color: accent || "var(--con-ink-1)" }}
      >
        {value}
      </div>
      {(hint || delta !== undefined) && (
        <div className="mt-1.5 flex items-center gap-2 text-[11px] text-ink-3">
          {delta !== undefined && (
            <span
              className="font-mono"
              style={{
                color: dir > 0 ? "var(--con-ok)" : dir < 0 ? "var(--con-err)" : "var(--con-ink-3)",
              }}
            >
              {dir > 0 ? "▲" : dir < 0 ? "▼" : "—"} {Math.abs(delta).toFixed(1)}%
            </span>
          )}
          {hint && <span>{hint}</span>}
        </div>
      )}
    </div>
  );
}
