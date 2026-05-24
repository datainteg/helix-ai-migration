import { cn } from "@/lib/utils";

/**
 * Small keyboard hint, e.g. <Kbd>⌘ K</Kbd>.
 * Uses mono and a 2-px bottom border to look slightly tactile.
 */
export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-[5px] py-px font-mono text-[10.5px] text-ink-3 leading-[1.4]",
        "border border-hx-2 border-b-2 rounded bg-surface",
        className
      )}
    >
      {children}
    </span>
  );
}
