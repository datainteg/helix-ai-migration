import React from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "brand" | "secondary" | "outline" | "ghost" | "danger" | "dark";
type Size = "sm" | "md" | "lg" | "icon";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

/**
 * Calm operations-console button.
 * - "primary" is now near-black (operational primary), not gradient brand
 * - "brand" is the indigo variant — use for AI / Ask Helix moments
 * - sizes are smaller across the board (md = 32px, not 40px)
 */
const variantClasses: Record<Variant, string> = {
  primary:
    "bg-ink text-white border border-ink hover:bg-zinc-800",
  brand:
    "bg-[var(--con-brand)] text-white border border-[var(--con-brand)] hover:bg-[#4338CA]",
  secondary:
    "bg-app-2 text-ink-2 border border-hx hover:bg-zinc-100",
  outline:
    "bg-surface text-ink-2 border border-hx-2 hover:bg-app-2",
  ghost:
    "bg-transparent text-ink-2 hover:bg-app-2",
  danger:
    "bg-surface text-err border border-hx-2 hover:bg-err-soft",
  dark:
    "bg-ink text-white border border-ink hover:bg-zinc-800",
};

const sizeClasses: Record<Size, string> = {
  sm:   "h-7 px-2.5 text-[12px] rounded-[7px] gap-1.5",
  md:   "h-8 px-3 text-[12.5px] rounded-[8px] gap-1.5",
  lg:   "h-9 px-4 text-[13px] rounded-[8px] gap-2",
  icon: "h-8 w-8 rounded-[8px]",
};

export function Button({
  variant = "outline",
  size = "md",
  loading = false,
  disabled,
  children,
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center font-medium leading-none transition-colors focus-ring disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap",
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
      {...props}
    >
      {loading && (
        <svg className="motion-safe:animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" aria-hidden>
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  );
}
