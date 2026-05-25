"use client";

import { Info } from "lucide-react";

/**
 * DemoBanner — surfaced at the top of any page that still renders fabricated
 * sample data instead of real backend rows. Required by the 2026-05-25 review
 * "no fictional content presented as real" rule.
 *
 * Remove this banner from a page only when every list/card on it is sourced
 * from a real backend response (or shows an explicit empty state).
 */
export function DemoBanner({
  message = "Sample data shown for layout preview. Wire this page to your backend to see real records.",
}: {
  message?: string;
}) {
  return (
    <div
      role="status"
      className="flex items-start gap-2.5 px-3 py-2 rounded-[8px] border border-hx-2 bg-[var(--con-warn-soft,#fff7e6)] text-[12.5px] text-ink-2"
    >
      <Info className="h-4 w-4 mt-[1px] flex-shrink-0 text-[var(--con-warn,#b45309)]" />
      <span>
        <strong className="font-medium text-ink">Demo data:</strong>&nbsp;{message}
      </span>
    </div>
  );
}
