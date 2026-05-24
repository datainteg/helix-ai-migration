import { cn } from "@/lib/utils";

type Tone = "ink" | "brand" | "ok" | "warn" | "err" | "info";

const toneClass: Record<Tone, string> = {
  ink:   "bg-ink",
  brand: "bg-[var(--con-brand)]",
  ok:    "bg-[var(--con-ok)]",
  warn:  "bg-[var(--con-warn)]",
  err:   "bg-[var(--con-err)]",
  info:  "bg-[var(--con-info)]",
};

interface ProgressBarProps {
  value: number;        // 0-100
  tone?: Tone | "indigo" | "green" | "amber" | "red"; // legacy tones map to new
  height?: number;
  className?: string;
}

const legacyMap: Record<string, Tone> = {
  indigo: "brand",
  green:  "ok",
  amber:  "warn",
  red:    "err",
};

export function ProgressBar({ value, tone = "ink", height = 4, className }: ProgressBarProps) {
  const t = (legacyMap[tone as string] || tone) as Tone;
  const v = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cn("w-full rounded-full overflow-hidden bg-[rgba(10,10,10,0.06)]", className)}
      style={{ height }}
      role="progressbar"
      aria-valuenow={v}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className={cn("h-full transition-[width] duration-300", toneClass[t])} style={{ width: `${v}%` }} />
    </div>
  );
}
