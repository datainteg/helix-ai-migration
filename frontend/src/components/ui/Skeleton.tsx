import { cn } from "@/lib/utils";

/**
 * Skeleton primitive (UI-046). A neutral placeholder block used on first paint
 * of data-heavy pages so the layout reserves space before data arrives,
 * cutting cumulative layout shift versus a bare spinner.
 *
 * Animation is gated behind `motion-safe:` so it respects prefers-reduced-motion.
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "rounded-md bg-app-2 motion-safe:animate-pulse",
        className
      )}
    />
  );
}

/** A row of skeleton cells sized for the dashboard/projects metric strips. */
export function SkeletonMetricRow({ cells = 5 }: { cells?: number }) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 bg-surface border border-hx rounded-[10px] overflow-hidden"
    >
      {Array.from({ length: cells }).map((_, i) => (
        <div key={i} className="px-4 py-3.5 border-t border-l border-hx first:border-l-0 space-y-2">
          <Skeleton className="h-2.5 w-16" />
          <Skeleton className="h-6 w-24" />
        </div>
      ))}
    </div>
  );
}

/** A stack of skeleton table rows. */
export function SkeletonTable({ rows = 6 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" className="bg-surface border border-hx rounded-[10px] overflow-hidden divide-y divide-[var(--con-line)]">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3">
          <Skeleton className="h-7 w-7 rounded-full" />
          <Skeleton className="h-3 flex-1 max-w-[240px]" />
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-3 w-16 ml-auto" />
        </div>
      ))}
    </div>
  );
}
